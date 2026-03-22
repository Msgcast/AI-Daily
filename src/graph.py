"""
LangGraph 工作流组装
当前为里程碑2版本：加入了 Generative UI Node (gen_ui)
"""
import logging
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.nodes.node_fetcher import node_fetcher
from src.nodes.node_scorer import node_scorer
from src.nodes.node_dedup import node_dedup
from src.nodes.node_summarizer import node_summarizer
from src.nodes.node_xhs_writer import node_xhs_writer
from src.nodes.node_gen_ui import node_gen_ui
from src.nodes.node_image_gen import node_image_gen
from src.nodes.node_publisher import node_publisher

logger = logging.getLogger(__name__)

# 完整节点顺序（用于 partial graph 截断）
NODE_ORDER = ["fetcher", "scorer", "dedup", "summarizer", "xhs_writer", "gen_ui", "image_gen", "publisher"]

NODE_FUNCS = {
    "fetcher": node_fetcher,
    "scorer": node_scorer,
    "dedup": node_dedup,
    "summarizer": node_summarizer,
    "xhs_writer": node_xhs_writer,
    "gen_ui": node_gen_ui,
    "image_gen": node_image_gen,
    "publisher": node_publisher,
}


def build_graph():
    """
    构建完整的 AI 资讯日报工作流
    数据流: Node1(抓取) → Node2(打分) → Node3(去重) → Node4(汇总) → Node5(撰写) → Node5.5(UI生成) → Node6(绘图) → Node7(发布)
    """
    graph = StateGraph(AgentState)

    # 注册节点
    for name, func in NODE_FUNCS.items():
        graph.add_node(name, func)

    # 连接节点（线性流程），使用精简的自动链式绑定规避错误
    graph.set_entry_point(NODE_ORDER[0])
    for i in range(len(NODE_ORDER) - 1):
        graph.add_edge(NODE_ORDER[i], NODE_ORDER[i + 1])
    graph.add_edge(NODE_ORDER[-1], END)

    return graph.compile()


def build_partial_graph(stop_node: str):
    """
    构建截断到指定节点的部分工作流（用于单节点/阶段测试）
    stop_node: 执行到该节点后停止（含该节点）
    """
    if stop_node not in NODE_ORDER:
        raise ValueError(f"未知节点: {stop_node}，可用节点: {NODE_ORDER}")

    stop_idx = NODE_ORDER.index(stop_node)
    nodes_to_run = NODE_ORDER[: stop_idx + 1]

    graph = StateGraph(AgentState)
    for name in nodes_to_run:
        graph.add_node(name, NODE_FUNCS[name])

    graph.set_entry_point(nodes_to_run[0])
    for i in range(len(nodes_to_run) - 1):
        graph.add_edge(nodes_to_run[i], nodes_to_run[i + 1])
    graph.add_edge(nodes_to_run[-1], END)

    logger.info(f"[PartialGraph] 构建截断图: {' → '.join(nodes_to_run)}")
    return graph.compile()


# 单例，避免重复构建
app = build_graph()
