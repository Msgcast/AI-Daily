"""
Node: Reddit 内容转换节点 (node_reddit_transformer)
职责：使用 Gemini 将采集到的 Reddit 英文内容进行小红书化的翻译与排版，
     将每一条高赞评论拆分为独立的卡片数据。
"""
import os
import logging
from contextlib import contextmanager
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import re
from typing import List

from src.config import GEMINI_API_KEY, HTTP_PROXY, HTTPS_PROXY
from src.state import AgentState

logger = logging.getLogger(__name__)

# --- 定义单页卡片结构 ---
class RedditCardData(BaseModel):
    user_name: str = Field(description="Reddit 用户名，如 u/username")
    score: str = Field(description="点赞数，如 12.5K")
    original_text: str = Field(description="英文原文评论")
    translated_text: str = Field(description="翻译后的感性中文")

class RedditTransformationResult(BaseModel):
    xhs_title: str = Field(description="小红书爆款标题")
    xhs_content: str = Field(description="小红书正文描述文案")
    translated_title: str = Field(description="原帖题目的中文翻译")
    cards: List[RedditCardData] = Field(description="转换后的 10-15 张单页评论卡片数据")

# --- 提示词设计 ---
SYSTEM_PROMPT = """你是一位顶级的“信达雅”双语翻译专家，同时深谙 Reddit 社区文化。

### 你的核心任务：
将 Reddit 上的高质量评论进行【精准、深刻、忠实】的翻译。

### 角色纪律：
1. **忠实原意**：绝对禁止过度修饰、禁止为了迎合小红书风格而过度改写。Reddit 的美感在于真实。请保留原句的冷幽默、深刻或朴素的语气。
2. **小红书发布规范（强制执行）**：
    - **xhs_title**: 必须严格遵循格式：Reddit热议：{{选题翻译}}。**总字数严控在 20 字以内**。
   - **xhs_content**: 必须包含：“整理了reddit上关于{{选题描述}}的真实分享” 以及 “欢迎大家在评论区留言进行讨论”。保持语气真诚、极简。
3. **分片策略（极重要）**：如果一个评论的内容经过翻译后，中文部分明显超过了 150 字（或英文超过 400 个字母），请**不要删减它**。相反，你应该将其拆分为两项或多项连续的 `RedditCardData` 对象。
   - **标识要求**：严禁在 `translated_text` 或 `original_text` 内部包含任何手动编号（如 "#1"、"Part 1"、"3 - Part 1"）。**绝对禁止**手动输出任何类似于 “#X - Part Y” 的前缀。
   - **正确位置**：如果进行了分片，请务必在 `user_name` 字段的末尾添加分段标识（例如：`u/username - Part 1`）。
4. **格式控制**：必须输出满足 RedditCardData 结构的 JSON 列表。

{format_instructions}"""

USER_PROMPT = """请将以下 Reddit 抓取素材进行转换与深度翻译。

素材详情：
【原贴题目】: {title}
【原贴链接】: {link}
【高赞评论】: {comments_json}

要求：为每一条高赞评论生成一个对应的卡片数据结构。"""

parser = JsonOutputParser(pydantic_object=RedditTransformationResult)

def node_reddit_transformer(state: AgentState) -> dict:
    """
    LangGraph Node - Reddit 内容转换与翻译
    """
    logger.info("=" * 60)
    logger.info("▶ Node: 开始执行 Reddit 内容 AI 级翻译与转换")
    logger.info("=" * 60)

    reddit_submission = state.get("reddit_submission")
    if not reddit_submission:
        logger.error("  [X] 未发现 reddit_submission 数据，跳过转换。")
        return {"error_log": "No reddit data present in state"}

    # 1. 初始化大模型
    client_args = {"proxy": HTTP_PROXY} if HTTP_PROXY else None
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=GEMINI_API_KEY,
        temperature=0.8,
        timeout=120,
        client_args=client_args
    )

    # 2. 组装请求
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ]).partial(format_instructions=parser.get_format_instructions())

    import json
    chain = prompt | llm | parser

    # 获取代理上下文（确保环境稳定）
    @contextmanager
    def _with_proxy():
        keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        saved = {k: os.environ.get(k) for k in keys}
        try:
            if HTTP_PROXY:
                for k in keys: os.environ[k] = HTTP_PROXY
            yield
        finally:
            for k, v in saved.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v

    try:
        with _with_proxy():
            logger.info("  [⚡] 正在调用 Gemini 进行跨语境爆款翻译...")
            result = chain.invoke({
                "title": reddit_submission['title'],
                "link": reddit_submission['link'],
                "comments_json": json.dumps(reddit_submission['comments'], ensure_ascii=False)
            })

        logger.info(f"  [✓] 转换完成，已生成 {len(result.get('cards', []))} 张评论卡片。")

        # 3. 数据映射与持久化
        # 将结果存入 xhs_post 和 card_data_list (复用原系统的渲染通道)
        # 注意：card_data_list 每一项在后续 node_image_gen 中会作为排版数据
        
        # 将首页（题目页）作为第一张卡片
        title_card = {
            "is_title_page": True,
            "title_en": reddit_submission['title'],
            "title_cn": result.get("translated_title"),
            "author": reddit_submission['author'],
            "score": f"{reddit_submission.get('score', 0)}",
            "type": "REDDIT_TOP_TOPIC"
        }

        final_cards = [title_card]
        # 合并评论卡片
        for i, card in enumerate(result.get("cards", []), 1):
            # 强化清洗：从开头移除模型可能幻觉出的 "#1 - Part 1", "Part 2:", "#8 - Part 2" 等前缀
            def clean_hallucination(text):
                if not text: return text
                return re.sub(r'^(#\d+\s*-\s*|Part\s*\d+\s*[：:-]\s*|#+\s*\d+\.\s*|Part\s*\d+\s*)', '', text, flags=re.IGNORECASE).strip()

            final_cards.append({
                "is_title_page": False,
                "badge_number": i,  # 显式传入页码索引
                "user_name": card.get("user_name"),
                "score": card.get("score"),
                "original_text": clean_hallucination(card.get("original_text")),
                "translated_text": clean_hallucination(card.get("translated_text"))
            })

        return {
            "xhs_post": {
                "title": result.get("xhs_title"),
                "content": result.get("xhs_content"),
                "tags": ["Reddit", "人性", "深度思考", "双语", "Reddit搬运"]
            },
            "card_data_list": final_cards
        }

    except Exception as e:
        logger.error(f"  [X] Transformer 转换异常: {e}")
        return {"error_log": f"Reddit transformation error: {e}"}
