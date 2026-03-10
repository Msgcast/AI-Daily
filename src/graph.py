"""
LangGraph 工作流组装
当前为里程碑1版本：Fetch → Score → Dedup(占位) → Summarize
"""
import logging
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.nodes.node_fetcher import node_fetcher
from src.nodes.node_scorer import node_scorer
from src.nodes.node_dedup import node_dedup
from src.nodes.node_summarizer import node_summarizer
from src.nodes.node_xhs_writer import node_xhs_writer
from src.nodes.node_image_gen import node_image_gen
from src.nodes.node_publisher import node_publisher

logger = logging.getLogger(__name__)


def build_graph():
    """
    构建完整的 AI 资讯日报工作流
    数据流: Node1(抓取) → Node2(打分) → Node3(去重) → Node4(汇总) → Node5(撰写) → Node6(绘图) → Node7(发布)
    """
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("fetcher", node_fetcher)
    graph.add_node("scorer", node_scorer)
    graph.add_node("dedup", node_dedup)
    graph.add_node("summarizer", node_summarizer)
    graph.add_node("xhs_writer", node_xhs_writer)
    graph.add_node("image_gen", node_image_gen)
    graph.add_node("publisher", node_publisher)

    # 连接节点（线性流程）
    graph.set_entry_point("fetcher")
    graph.add_edge("fetcher", "scorer")
    graph.add_edge("scorer", "dedup")
    graph.add_edge("dedup", "summarizer")
    graph.add_edge("summarizer", "xhs_writer")
    graph.add_edge("xhs_writer", "image_gen")
    graph.add_edge("image_gen", "publisher")
    graph.add_edge("publisher", END)

    return graph.compile()



# 单例，避免重复构建
app = build_graph()
