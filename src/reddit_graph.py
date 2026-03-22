"""
Reddit 专题工作流组装 (reddit_graph)
职责：实现从 Reddit RSS 抓取到 AI 智选、翻译、渲染及发布的完整闭环。
与 build_graph (AI 资讯日报) 保持数据隔离。
"""
import logging
from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.nodes.node_reddit_fetcher import node_reddit_fetcher
from src.nodes.node_reddit_filter import node_reddit_filter
from src.nodes.node_reddit_transformer import node_reddit_transformer
from src.nodes.node_image_gen import node_image_gen
from src.nodes.node_publisher import node_publisher

logger = logging.getLogger(__name__)

# Reddit 专题核心节点顺序
REDDIT_NODE_ORDER = [
    "reddit_fetcher", 
    "reddit_filter", 
    "reddit_transformer", 
    "reddit_image_gen", 
    "reddit_publisher"
]

REDDIT_NODE_FUNCS = {
    "reddit_fetcher": node_reddit_fetcher,
    "reddit_filter": node_reddit_filter, # DeepSeek 智选过滤
    "reddit_transformer": node_reddit_transformer, # Gemini 爆款翻译
    "reddit_image_gen": node_image_gen, # 优先匹配 reddit_card.html
    "reddit_publisher": node_publisher, # 发布到小红书
}

def build_reddit_graph():
    """
    构建【Reddit热议】专题工作流
    流程: 嗅探智选题目 -> AI质检过滤 -> 爆款双语翻译 -> 全真UI渲染 -> 一键发布
    """
    graph = StateGraph(AgentState)

    # 注册节点
    for name, func in REDDIT_NODE_FUNCS.items():
        graph.add_node(name, func)

    # 线性连接
    graph.set_entry_point(REDDIT_NODE_ORDER[0])
    for i in range(len(REDDIT_NODE_ORDER) - 1):
        graph.add_edge(REDDIT_NODE_ORDER[i], REDDIT_NODE_ORDER[i + 1])
    graph.add_edge(REDDIT_NODE_ORDER[-1], END)

    logger.info("✅ [RedditGraph] 已成功组装『Reddit热议』全链路专题工作流")
    return graph.compile()

# 导出实例
reddit_app = build_reddit_graph()
