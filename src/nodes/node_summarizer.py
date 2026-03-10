"""
Node 4: 精品汇总生成节点
职责：使用 DeepSeek-V3 对精品文章进行 Map-Reduce 汇总，
      生成结构化的"今日 AI 大事件"日报
"""
import logging
import os
from typing import Optional

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, HTTP_PROXY
from src.state import AgentState, ScoredArticle

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Map 阶段 Prompt：单篇 -> 核心结论（70字以内）
# ─────────────────────────────────────────────────────────────
MAP_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是 AI 资讯浓缩专家，用最精炼的语言提取资讯核心价值。"),
    ("human", """请将以下 AI 资讯浓缩为一句话核心结论（70字以内），
要求：说明是什么事件 + 关键数据或影响 + 为什么重要

来源: {source}  |  分类: {category}  |  评分: {score}/10
标题: {title}
摘要: {summary}

只输出浓缩后的一句话，不要其他内容。"""),
])

# ─────────────────────────────────────────────────────────────
# Reduce 阶段 Prompt：多条结论 -> 结构化日报
# ─────────────────────────────────────────────────────────────
REDUCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是顶级 AI 科技媒体的总编辑，每天为数十万对 AI 感兴趣的年轻读者整理最重要的资讯。
你的风格：简洁有力、去除废话、让读者一眼看到重点、用词让人眼前一亮。"""),
    ("human", """根据以下今日精品 AI 资讯，生成一份结构化日报：

{bullet_summaries}

请按照以下结构输出，使用 Markdown 格式：

## 今日 AI 圈一句话定调
（一句话点明今天 AI 圈的整体氛围或最大变量，语气有力，50字内）

## 重磅事件 TOP3
（按重要程度排序，每个事件包含：
- **事件标题**（吸睛，带emoji）
- 核心内容（100字，讲清楚发生了什么、数据/影响）
- 为什么重要（30字，站在普通用户视角解释意义）
）

## 快讯速览
（其余事件的一句话列表，每条以 "-" 开头，带来源平台标注）

## 今日关键词
（3-5个关键词，用 # 标注，如 #GPT-5 #多模态 #开源大模型）
"""),
])


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


def _get_llm(temperature: float = 0.3, use_proxy: bool = False) -> ChatOpenAI:
    http_client = _build_http_client(use_proxy)
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature,
        http_client=http_client,
    )


def _map_article_to_bullet(llm_direct, llm_proxy, article: ScoredArticle) -> str:
    """Map 阶段：将单篇文章压缩为一句话核心结论"""
    try:
        chain = MAP_PROMPT | llm_direct
        result = chain.invoke({
            "source": article["source"],
            "category": article["category"],
            "score": article["score"],
            "title": article["title"],
            "summary": article["summary"][:500],
        })
        bullet = result.content.strip()
        logger.debug(f"  Map ->[{article['score']}分] {bullet[:60]}...")
        return f"[{article['score']}分]{article['category']}·{article['source']}] {bullet}"
    except Exception as e:
        if llm_proxy is not None and _is_conn_err(e):
            logger.warning("  [Map重试] 直连失败，改用代理重试一次")
            try:
                chain = MAP_PROMPT | llm_proxy
                result = chain.invoke({
                    "source": article["source"],
                    "category": article["category"],
                    "score": article["score"],
                    "title": article["title"],
                    "summary": article["summary"][:500],
                })
                bullet = result.content.strip()
                return f"[{article['score']}分]{article['category']}·{article['source']}] {bullet}"
            except Exception as e2:
                logger.warning(f"  [Map失败] {article['title'][:40]}... -> {e2}")
        else:
            logger.warning(f"  [Map失败] {article['title'][:40]}... -> {e}")
        return f"[{article['score']}分]{article['source']}] {article['title']}"


def node_summarizer(state: AgentState) -> dict:
    """LangGraph Node 4 - Map-Reduce 精品汇总"""
    logger.info("=" * 60)
    logger.info("▶ Node 4: 开始 Map-Reduce 精品日报生成")
    logger.info("=" * 60)

    events = state.get("deduped_events", [])
    if not events:
        logger.warning("  ⚠️ 没有可汇总的精品文章")
        master_summary = "今日暂无满足条件的精品 AI 资讯。"
        return {"master_summary": master_summary}

    logger.info(f"  待汇总精品文章: {len(events)} 篇\n")

    llm_fast_direct = _get_llm(temperature=0.1, use_proxy=False)
    llm_fast_proxy = _get_llm(temperature=0.1, use_proxy=True) if HTTP_PROXY else None
    llm_strong_direct = _get_llm(temperature=0.5, use_proxy=False)
    llm_strong_proxy = _get_llm(temperature=0.5, use_proxy=True) if HTTP_PROXY else None

    try:
        # —— Map 阶段：逐篇压缩 ——
        logger.info("  [Map阶段] 逐篇提炼核心结论...")
        bullet_list = []
        for i, article in enumerate(events, 1):
            logger.info(f"  Map [{i}/{len(events)}]: {article['title'][:50]}...")
            bullet = _map_article_to_bullet(llm_fast_direct, llm_fast_proxy, article)
            bullet_list.append(bullet)

        bullet_summaries = "\n".join([f"{i+1}. {b}" for i, b in enumerate(bullet_list)])

        # —— Reduce 阶段：整合生成日报 ——
        logger.info(f"\n  [Reduce阶段] 整合 {len(bullet_list)} 条结论，生成结构化日报...")
        try:
            reduce_chain = REDUCE_PROMPT | llm_strong_direct
            result = reduce_chain.invoke({"bullet_summaries": bullet_summaries})
            master_summary = result.content.strip()
        except Exception as e:
            if llm_strong_proxy is not None and _is_conn_err(e):
                logger.warning("  [Reduce重试] 直连失败，改用代理重试一次")
                try:
                    reduce_chain = REDUCE_PROMPT | llm_strong_proxy
                    result = reduce_chain.invoke({"bullet_summaries": bullet_summaries})
                    master_summary = result.content.strip()
                except Exception as e2:
                    logger.error(f"  Reduce 失败: {e2}")
                    master_summary = "日报生成失败，以下为原始精品列表：\n" + bullet_summaries
            else:
                logger.error(f"  Reduce 失败: {e}")
                master_summary = "日报生成失败，以下为原始精品列表：\n" + bullet_summaries

        logger.info("\n✅ Node 4 完成: 日报生成成功")
        logger.info(f"   日报长度: {len(master_summary)} 字")

        return {"master_summary": master_summary}
    finally:
        for llm in [llm_fast_direct, llm_fast_proxy, llm_strong_direct, llm_strong_proxy]:
            if llm and getattr(llm, "http_client", None):
                try:
                    llm.http_client.close()
                except Exception:
                    pass
