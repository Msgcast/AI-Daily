"""
Node 5.5: Generative UI 生成节点 (Agent Art Director)
职责：根据当天新闻主题与情感色彩，利用大模型和 Tailwind CSS 动态生成 HTML 艺术排版。如果在执行中出错，则返回空列表，由后续节点进行无缝降级。
"""
import os
import logging
import json
from contextlib import contextmanager
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src.config import GEMINI_API_KEY, HTTP_PROXY, HTTPS_PROXY
from src.state import AgentState

logger = logging.getLogger(__name__)

class UIResult(BaseModel):
    mood: str = Field(description="新闻的情感偏型，如 HIGH_TECH(深蓝赛博), CRITICAL(深红警告), CAPITAL(老钱商业), DEFAULT(浅色经典)")
    html_source: str = Field(description="能在浏览器直接运行的 1200x1600 尺寸的完整 HTML 网页源码文档，基于 Tailwind CSS")

SYSTEM_PROMPT = """你是一位顶级的“AI 前端艺术总监”。你的任务是对传入的新闻内容进行极致的《Generative UI 设计生成》。

要求：
1. 提取新闻的核心意图和情感，用作风格定义（但只能作为局部的点缀色）。
2. 在一张 1200x1600 (3:4) 尺寸的绝对容器内，产出完整 HTML 海报源码。
3. 框架库：仅可使用引入的 Tailwind CSS。
4. 移动端克制审美纪律（Mobile-First Impeccable Principles，极度重要）：
   - 【拒绝花哨】强制使用白底或极浅素色（如 Paper 白、浅灰、奶白）为主背景！彻底抛弃暗黑模式与光污染。所有特殊的情感色（比如暴跌对应深红，突破对应深蓝）只能作为少量的点缀（比如实线边框、角标、小标签），杜绝视觉疲劳。
   - 【巨型字号】面向手机屏幕，画面文字屏占比必须极大！主标题必须粗体且 >70px，正文必须 >28px，辅助标注绝不可小于 24px。绝对禁止蚂蚁字！
   - 【消灭留白】解决“留白过多、比例失调”的问题，将 1200x1600 的画面完全被大色块、巨大的文字、硬朗的分割线和撑满边界的内容区所填充，保持高密度信息压迫感。
   - 【学术报刊感】打破纯居中，采用类似《华尔街日报》或顶级商业研报的强网格、非对称、带实心边框的克制排版风格。不要任何模糊阴影，用硬边（Hard-edges）。
5. 源码必须从 `<!DOCTYPE html>` 开始，可直接独立渲染运行。

输出的必须为包含 `mood` 和 `html_source` 字段的严格 JSON。
{format_instructions}"""

parser = JsonOutputParser(pydantic_object=UIResult)

ui_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "背景简报：\n{summary}\n今天的主题内容数据块为：\n{card_data}\n\n请打破这套数据格式的死板局限，将其转化为极具艺术张力的动态 HTML 生成页。"),
]).partial(format_instructions=parser.get_format_instructions())

def node_gen_ui(state: AgentState) -> dict:
    """LangGraph Node 5.5 - 动态海报生成器"""
    logger.info("=" * 60)
    logger.info("▶ Node 5.5: 开始 Generative UI 动态代码生成 (Art Director)")
    logger.info("=" * 60)

    card_data_list = state.get("card_data_list", [])
    master_summary = state.get("master_summary", "")
    
    if not card_data_list:
        return {"generated_html_list": []}

    @contextmanager
    def _with_gemini_proxy():
        keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        saved = {k: os.environ.get(k) for k in keys}
        try:
            if HTTP_PROXY:
                os.environ["HTTP_PROXY"] = HTTP_PROXY
                os.environ["HTTPS_PROXY"] = HTTPS_PROXY
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
        temperature=0.9,
        max_retries=1,
        timeout=120,
        client_args=client_args,
    )

    generated_html_list = []
    
    try:
        chain = ui_prompt | llm | parser
        with _with_gemini_proxy():
            # 为保证速度，目前最多只对前 3 张卡执行动态生成
            for i, card in enumerate(card_data_list[:3]):
                logger.info(f"  [Art Director] 正在构思生成第 {i+1} 张海报结构代码...")
                result = chain.invoke({
                    "summary": master_summary, 
                    "card_data": json.dumps(card, ensure_ascii=False)
                })
                html = result.get("html_source", "")
                mood = result.get("mood", "UNKNOWN")
                logger.info(f"  [✓] 赋予视觉流派: {mood}，前端代码构建成功。")
                if html:
                    generated_html_list.append(html)
                    
        return {"generated_html_list": generated_html_list}

    except Exception as e:
        logger.error(f"  [错误] Generative UI 请求异常: {e}。将触发下一环节的标准模板降级。")
        return {"generated_html_list": []}
