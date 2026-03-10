"""
LangGraph 全局 State 定义
每个 Node 只修改它负责的字段，其余字段保持不变
"""
from typing import TypedDict, Optional


class ArticleItem(TypedDict):
    """单篇文章的数据结构"""
    title: str          # 文章标题
    summary: str        # 文章摘要（RSS 提供的原始摘要）
    link: str           # 原文链接
    published: str      # 发布时间（字符串格式）
    source: str         # 来源平台名称
    category: str       # 文章来源大类


class ScoredArticle(TypedDict):
    """打分后的文章数据结构"""
    title: str
    summary: str
    link: str
    published: str
    source: str
    score: int          # AI 打出的热度评分 (1-10)
    score_reason: str   # 打分理由（中文，30字内）
    category: str       # 分类标签


class AgentState(TypedDict):
    """LangGraph 全局状态"""
    # ── Node 1: RSS 抓取 输出 ──
    raw_articles: list[ArticleItem]

    # ── Node 2: AI打分过滤 输出 ──
    scored_articles: list[ScoredArticle]
    premium_articles: list[ScoredArticle]   # 高分精品文章

    # ── Node 3 (预留): 聚类去重 输出 ──
    deduped_events: list[ScoredArticle]

    # ── Node 4: 精品汇总 输出 ──
    master_summary: str                      # 结构化精品日报摘要

    # ── Node 5: 小红书文案 输出 ──
    xhs_post: dict                           # 小红书文案结构 (title, content, tags)
    card_data_list: list[dict]               # 每一页卡片对应的结构化填充数据 (3-5页)
    
    # ── Node 6: Playwright 截图 输出 ──
    images: list[str]                        # 本地存放的截图路径列表

    # ── 流程控制 ──
    error_log: Optional[str]                 # 异常记录
