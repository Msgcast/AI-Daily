"""
Node 5: 小红书文案与杂志卡片数据生成节点
职责：使用 Gemini 3 产出爆款文案，并为 3-5 张卡片提供结构化“杂志排版”填充数据
"""
import logging
import os
from contextlib import contextmanager
from typing import List
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src.config import GEMINI_API_KEY, HTTP_PROXY, HTTPS_PROXY
from src.state import AgentState
from src.utils.text_sanitize import sanitize_title, sanitize_content, normalize_tags

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 杂志卡片单页结构 (4+8 布局所需数据)
# ─────────────────────────────────────────────────────────────
class CardMidItem(BaseModel):
    icon: str = Field(description="FontAwesome 图标类名，如 'fa-bolt', 'fa-microchip'")
    text: str = Field(description="简短关键词，2-6字")

class MagazineCardData(BaseModel):
    header_title_en: str = Field(description="页面主标题(英文)，如 'AI REVOLUTION'")
    header_subtitle_en: str = Field(description="副标题(英文)，如 'MAPPING THE FUTURE'")
    left_philosophical_quote: str = Field(description="左侧 4 栏的视觉金句，需深刻且相关，20字以内")
    right_main_title: str = Field(description="右侧 8 栏的新闻/主题大标题")
    right_main_content: str = Field(description="右侧 8 栏的核心干货，采用 HTML 标签如<p>或<li>排版，字数150-250字")
    mid_cards: List[CardMidItem] = Field(description="中段 3 个技术点位的小卡片信息")
    footer_statement: str = Field(description="底部深色区域的结论性短句，15-20字")

class XHSArticleResult(BaseModel):
    title: str = Field(description="小红书爆款标题")
    content: str = Field(description="小红书正文排版")
    tags: List[str] = Field(description="5-8个话题标签")
    cards: List[MagazineCardData] = Field(description="3-5张杂志卡片的具体结构化数据")


# ─────────────────────────────────────────────────────────────
# Prompt 模板
# ─────────────────────────────────────────────────────────────
XHS_SYSTEM_PROMPT = """你是一位顶尖的杂志排版总监与科技专栏作者。
你的任务是将今日 AI 圈资讯转化为 3-5 张具有强烈视觉冲击力的数字杂志"卡片"。

你的设计基调是：
1. **非对称美学**：左侧4栏放灵魂金句，右侧8栏放干货。
2. **中英对比**：Header 部分使用质感极高的英文，正文使用中文。
3. **高密度事实**：每一页卡片都要填入具体的新事实、数据或逻辑拆解，拒绝水文。

强约束：
1) 标题必须不超过 20 个汉字（含标点）。
2) 正文必须不超过 1000 个汉字（含标点），超出会导致发布失败。
3) 标题与正文禁止出现 Markdown 符号（例如 **、#、`、>、-、*），不要分点编号，不要“AI味”套话。

请严格按照 JSON 格式输出，不要附加任何解释。\n{format_instructions}"""

XHS_USER_PROMPT = """请根据以下材料，策划今日的《AI 科技专刊》：

{summary}"""

parser = JsonOutputParser(pydantic_object=XHSArticleResult)

xhs_prompt = ChatPromptTemplate.from_messages([
    ("system", XHS_SYSTEM_PROMPT),
    ("human", XHS_USER_PROMPT),
]).partial(format_instructions=parser.get_format_instructions())


def node_xhs_writer(state: AgentState) -> dict:
    """LangGraph Node 5 - 生成小红书文案与卡片数据"""
    logger.info("=" * 60)
    logger.info("▶ Node 5: 开始生成小红书文案与杂志风格卡片数据")
    logger.info("=" * 60)

    master_summary = state.get("master_summary", "")
    if not master_summary:
        logger.warning("  ⚠️ 无可用素材，跳过文案生成")
        return {"xhs_post": {}, "card_data_list": []}

    @contextmanager
    def _with_gemini_proxy():
        keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        saved = {k: os.environ.get(k) for k in keys}
        try:
            if HTTP_PROXY:
                os.environ["HTTP_PROXY"] = HTTP_PROXY
                os.environ["HTTPS_PROXY"] = HTTPS_PROXY
                os.environ["http_proxy"] = HTTP_PROXY
                os.environ["https_proxy"] = HTTPS_PROXY
            yield
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    client_args = {"proxy": HTTP_PROXY} if HTTP_PROXY else None

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=GEMINI_API_KEY,
        temperature=0.7,
        max_retries=2,
        timeout=120,
        client_args=client_args,
    )

    now_str = datetime.now().strftime("%Y-%m-%d")

    try:
        logger.info(f"  正在调用 {llm.model} 生成文案与卡片数据...")
        chain = xhs_prompt | llm | parser
        with _with_gemini_proxy():
            result = chain.invoke({"summary": master_summary})
        logger.info(f"  LLM 生成成功，解析 {len(result.get('cards', []))} 个卡片数据")

        raw_title = result.get("title", "")
        raw_content = result.get("content", "")

        # 再次清洗，确保长度与风格约束
        title = sanitize_title(raw_title, 20)
        content = sanitize_content(raw_content, 1000, remove_hashtags=True)

        xhs_post = {
            "title": title,
            "content": content,
            "tags": normalize_tags(result.get("tags", []))
        }

        raw_cards = result.get("cards", [])
        card_data_list = []
        for i, card in enumerate(raw_cards):
            card["version"] = f"{i+1}.0.0"
            card["date"] = now_str
            card_data_list.append(card)

        logger.info(f"✅ 文案与 {len(card_data_list)} 张杂志数据生成完毕")
        return {
            "xhs_post": xhs_post,
            "card_data_list": card_data_list
        }

    except Exception as e:
        logger.error(f"[错误] 小红书文案生成失败: {e}")
        if "429" in str(e):
            logger.error("  原因：Gemini 接口触发频控(429 - Overloaded/Quota Exceeded)，请稍后重试。")
        return {"xhs_post": {}, "card_data_list": []}
