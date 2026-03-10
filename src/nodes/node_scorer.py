"""
Node 2: AI 智能打分与过滤节点
职责：使用 DeepSeek-V3 对每篇文章打分，筛选出热门、够热度的精品资讯
"""
import json
import logging
import os
from typing import Optional

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    SCORE_THRESHOLD, MAX_PREMIUM_ARTICLES, HTTP_PROXY
)
from src.state import AgentState, ArticleItem, ScoredArticle

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Pydantic 结构化输出模型
# ─────────────────────────────────────────────────────────────
class ArticleScoreResult(BaseModel):
    """AI 对单篇文章的打分结果"""
    score: int = Field(
        description="综合热度评分，1-10分",
        ge=1, le=10
    )
    score_reason: str = Field(
        description="打分理由，用中文，40字以内，聚焦于为什么这篇内容值得关注"
    )
    sub_category: str = Field(
        description="细分类型，如: 模型发布 | 工具推荐 | 爆款开源 | 安全伦理 | 产业融资",
        default=""
    )


# ─────────────────────────────────────────────────────────────
# Prompt 模板
# ─────────────────────────────────────────────────────────────
SCORING_SYSTEM_PROMPT = """你是一位资深 AI 科技媒体主编，擅长判断一篇 AI 资讯是否能引爆传播、勾起大众兴趣。

你的评分维度（满分 10 分）：
- **热度与话题性**（3分）：有没有病毒传播潜力？是否是当下最热议的话题？（如 GPT-5 发布、AI 取代某职业等）
- **技术突破性**（3分）：是否有新模型、新能力、新benchmark突破？是否颠覆认知？
- **大众可读性**（2分）：普通用户能否看懂并感到兴奋或焦虑？
- **时效性**（2分）：是否是近24小时的最新事件？

评分标准：
- 9-10分：现象级事件（如 GPT-5 发布、AI彻底击败人类某领域）
- 7-8分：重要事件（主流大模型重大更新、行业巨头AI战略、重要工具发布）
- 5-6分：有价值的技术进展（新论文、小模型发布、工具迭代）
- 1-4分：普通资讯、重复内容、软文广告、财报数据等

请只输出 JSON 格式的评分，不要附加任何解释。
{format_instructions}"""

SCORING_USER_PROMPT = """请评价以下 AI 资讯：

大类标签: {category}
来源平台: {source}
标题: {title}
摘要: {summary}"""

parser = JsonOutputParser(pydantic_object=ArticleScoreResult)

scoring_prompt = ChatPromptTemplate.from_messages([
    ("system", SCORING_SYSTEM_PROMPT),
    ("human", SCORING_USER_PROMPT),
]).partial(format_instructions=parser.get_format_instructions())


def _is_conn_err(err: Exception) -> bool:
    msg = str(err)
    return (
        "Connection error" in msg
        or "ConnectError" in msg
        or "WinError 10013" in msg
        or "访问权限" in msg
    )


def _build_http_client(use_proxy: bool) -> Optional[httpx.Client]:
    if use_proxy and HTTP_PROXY:
        return httpx.Client(proxy=HTTP_PROXY, timeout=httpx.Timeout(30.0))
    return None


def _get_llm(use_proxy: bool) -> ChatOpenAI:
    http_client = _build_http_client(use_proxy)
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.1,
        max_tokens=256,
        model_kwargs={"response_format": {"type": "json_object"}},
        http_client=http_client,
    )


def _score_single_article(llm, article: ArticleItem) -> ScoredArticle:
    chain = scoring_prompt | llm | parser
    payload = {
        "category": article.get("category", ""),
        "source": article["source"],
        "title": article["title"],
        "summary": article["summary"][:600],
    }
    result = chain.invoke(payload)

    return ScoredArticle(
        title=article["title"],
        summary=article["summary"],
        link=article["link"],
        published=article["published"],
        source=article["source"],
        score=int(result.get("score", 0)),
        score_reason=result.get("score_reason", ""),
        category=article.get("category", "综合"),
    )


def node_scorer(state: AgentState) -> dict:
    """
    LangGraph Node 2 - AI 智能打分与过滤
    """
    logger.info("=" * 60)
    logger.info("▶ Node 2: 开始 AI 智能打分与过滤")
    logger.info("=" * 60)

    raw_articles = state.get("raw_articles", [])
    if not raw_articles:
        logger.warning("  ⚠️ 没有可打分的文章，跳过此节点")
        return {"scored_articles": [], "premium_articles": []}

    logger.info(f"  待打分文章: {len(raw_articles)} 篇\n")

    force_proxy = os.getenv("DEEPSEEK_USE_PROXY", "").strip().lower() in ("1", "true", "yes")
    llm_direct = _get_llm(use_proxy=False)
    llm_proxy = _get_llm(use_proxy=True) if HTTP_PROXY else None

    scored_articles: list[ScoredArticle] = []

    try:
        for i, article in enumerate(raw_articles, 1):
            title_preview = article["title"][:50]
            logger.info(f"  [{i:02d}/{len(raw_articles):02d}] 打分中: {title_preview}...")

            try:
                if force_proxy and llm_proxy is not None:
                    scored = _score_single_article(llm_proxy, article)
                else:
                    scored = _score_single_article(llm_direct, article)
            except Exception as e:
                if (not force_proxy) and llm_proxy is not None and _is_conn_err(e):
                    logger.warning("  [打分重试] 直连失败，改用代理重试一次")
                    try:
                        scored = _score_single_article(llm_proxy, article)
                    except Exception as e2:
                        logger.warning(f"  [打分失败] '{article['title'][:40]}...' -> {e2}")
                        scored = None
                else:
                    logger.warning(f"  [打分失败] '{article['title'][:40]}...' -> {e}")
                    scored = None

            if scored:
                scored_articles.append(scored)
                logger.info(
                    f"         → 评分: {scored['score']}/10 | "
                    f"类别: {scored['category']} | "
                    f"理由: {scored['score_reason']}"
                )
    finally:
        if getattr(llm_direct, "http_client", None):
            try:
                llm_direct.http_client.close()
            except Exception:
                pass
        if llm_proxy and getattr(llm_proxy, "http_client", None):
            try:
                llm_proxy.http_client.close()
            except Exception:
                pass

    scored_articles.sort(key=lambda x: x["score"], reverse=True)
    premium_articles = [
        a for a in scored_articles
        if a["score"] >= SCORE_THRESHOLD
    ][:MAX_PREMIUM_ARTICLES]

    logger.info(f"\n✅ Node 2 完成:")
    logger.info(f"   打分完成: {len(scored_articles)} 篇")
    logger.info(f"   精品文章 (≥{SCORE_THRESHOLD}分): {len(premium_articles)} 篇")
    if premium_articles:
        logger.info("   TOP 3 文章:")
        for i, a in enumerate(premium_articles[:3], 1):
            logger.info(f"     {i}. [{a['score']}分] {a['title'][:60]}")

    return {
        "scored_articles": scored_articles,
        "premium_articles": premium_articles,
    }
