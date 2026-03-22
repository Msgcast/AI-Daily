"""
Node: Reddit 内容质量打分节点 (node_reddit_filter)
职责：使用 DeepSeek-V3 对经过物理预洗的评论进行深度打分，
     筛选出最具互动潜力、能引起深度讨论的金句评论。
"""
import logging
import json
import httpx
from pydantic import BaseModel, Field
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.state import AgentState
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, HTTP_PROXY

logger = logging.getLogger(__name__)

# --- 打分模型 ---
class CommentScore(BaseModel):
    score: int = Field(description="评分 1-10，10位最高")
    reason: str = Field(description="打分理由（中文）")

class RedditFilterResult(BaseModel):
    selected_indices: List[int] = Field(description="入选的评论索引列表（从 0 开始）")

# --- 提示词 ---
FILTER_SYSTEM_PROMPT = """你是一位精准的“人类情感分析师”和“小红书爆款内容筛选官”。
你的任务是从一批 Reddit 评论中，选出最能引起小红书女性用户、学生群体或职场新人共鸣的内容。

### 筛选标准（10分制）：
1. **反直觉/洞察力**（4分）：观点是否新颖？是否揭示了某种不为人知的生活真相？
2. **共情张力**（3分）：是否包含真实动人的故事或深刻的情绪？
3. **话题延伸性**（3分）：该评论是否能在小红书评论区引发新一轮的讨论？

### 任务：
找出并返回排名前 8 的评论索引，确保这些评论不仅高质量，而且内容各异（避免重复观点）。
如果你认为值得入选的评论不足 8 条，按实际情况返回。

请只输出 JSON 格式，格式如下：
{{"selected_indices": [0, 2, 5, ...]}}"""

FILTER_USER_PROMPT = """原贴话题：{title}

待筛选评论列表：
{comments_text}"""

def node_reddit_filter(state: AgentState) -> dict:
    """
    LangGraph Node - Reddit 评论智能筛选
    """
    logger.info("=" * 60)
    logger.info("▶ Node: 开始 AI 智能筛选高质量评论 (DeepSeek)")
    logger.info("=" * 60)

    rs = state.get("reddit_submission")
    if not rs or not rs.get("comments"):
        return {"error_log": "No comments to filter"}

    comments = rs["comments"]
    
    # 1. 组装待筛选文本
    formatted_comments = ""
    for i, c in enumerate(comments):
        formatted_comments += f"[{i}] Author: {c['author']}\nContent: {c['body']}\n\n"

    # 2. 初始化 DeepSeek (复用日报系统的配置)
    http_client = httpx.Client(proxy=HTTP_PROXY) if HTTP_PROXY else None
    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.3,
        http_client=http_client
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", FILTER_SYSTEM_PROMPT),
        ("human", FILTER_USER_PROMPT),
    ])

    try:
        logger.info("  [⚡] 正在请求 DeepSeek 进行深度内容价值评估...")
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({
            "title": rs["title"],
            "comments_text": formatted_comments
        })

        selected_indices = result.get("selected_indices", [])
        filtered_comments = [comments[i] for i in selected_indices if i < len(comments)]

        logger.info(f"  [✓] 筛选完成: 原始 {len(comments)} 条 -> 智选 {len(filtered_comments)} 条优质讨论。")
        
        # 更新 state 中的评论列表为筛选后的精品
        rs["comments"] = filtered_comments
        return {"reddit_submission": rs}

    except Exception as e:
        logger.error(f"  [X] AI 筛选异常: {e}")
        # 降级：如果 AI 筛选失败，默认保留前 8 条，不阻塞任务
        rs["comments"] = comments[:8]
        return {"reddit_submission": rs}
