"""
Node 3 (预留占位): 聚类去重节点
里程碑2才会完整实现，当前版本直接透传精品文章
"""
import logging
from src.state import AgentState

logger = logging.getLogger(__name__)


def node_dedup(state: AgentState) -> dict:
    """
    LangGraph Node 3 - 聚类去重（里程碑2实现）
    当前版本：直接透传 premium_articles，无去重逻辑
    """
    premium = state.get("premium_articles", [])
    logger.info(f"▶ Node 3 (去重占位): 透传 {len(premium)} 篇精品文章")
    return {"deduped_events": premium}
