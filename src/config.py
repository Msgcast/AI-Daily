"""
配置管理模块
所有参数均从 .env 文件加载，不在代码中硬编码敏感信息
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# LLM 配置 (DeepSeek-V3)
# ──────────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-chat"          # deepseek-v3 对应的 model id

# ──────────────────────────────────────────────
# Google / Gemini API (用于 HTML 生成)
# ──────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_API_KEY = GOOGLE_API_KEY  # 复用同一个 KEY

# ──────────────────────────────────────────────
# 代理设置 (Clash 7897)
# ──────────────────────────────────────────────
HTTP_PROXY = os.getenv("HTTP_PROXY", "http://127.0.0.1:7897")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "http://127.0.0.1:7897")

# 注意：不在全局环境中强制设置代理。
# Gemini 需要代理时在调用处临时注入，避免影响 DeepSeek 等直连服务。

# ──────────────────────────────────────────────
# 多维度 RSS 数据源扩充与分类
# ──────────────────────────────────────────────
RSS_SOURCES = [
    # ── 1. 大模型动态 (主流大厂与核心资讯) ──
    {
        "name": "机器之心",
        "category": "大模型动态",
        "url": "https://www.jiqizhixin.com/rss",
        "description": "国内最前沿的AI科技媒体",
    },
    {
        "name": "OpenAI Blog",
        "category": "大模型动态",
        "url": "https://openai.com/news/rss.xml",
        "description": "OpenAI 官方动态与发布",
    },
    {
        "name": "TechCrunch AI",
        "category": "大模型动态",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "description": "全面深入的AI商业与动态新闻",
    },

    # ── 2. 开发工具更新 (实用工具、框架迭代) ──
    {
        "name": "HuggingFace Blog",
        "category": "开发工具更新",
        "url": "https://huggingface.co/blog/feed.xml",
        "description": "最权威的模型发布与开源工具社区",
    },
    {
        "name": "VentureBeat AI",
        "category": "开发工具更新",
        "url": "https://venturebeat.com/category/ai/feed/",
        "description": "涉及大量 AI 企业级工具与技术迭代",
    },

    # ── 3. GitHub 开源热榜 (开源趋势) ──
    # 由于直接抓取热榜较难，这里用 HackerNews Show HN 中关于 AI 的高赞项目作为替代
    {
        "name": "Show HN - AI",
        "category": "GitHub开源热榜",
        "url": "https://hnrss.org/show?q=AI",
        "description": "HackerNews 上的 AI 开源项目展示",
    },

    # ── 4. 前沿研究 (学术、论文、硬核技术深度) ──
    {
        "name": "arXiv CS.AI",
        "category": "前沿研究",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "description": "arXiv 上最新的人工智能方向学术论文",
    },
    {
        "name": "MIT Tech Review AI",
        "category": "前沿研究",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
        "description": "顶级学术与产业结合科技深度文章",
    },
    {
        "name": "Hacker News AI Research",
        "category": "前沿研究",
        "url": "https://hnrss.org/newest?q=LLM",
        "description": "黑客社区关于大言语模型的最新硬核讨论",
    },
]

# ──────────────────────────────────────────────
# 过滤与汇总参数
# ──────────────────────────────────────────────
SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "7"))   # AI打分阈值 (1-10)
FETCH_HOURS = int(os.getenv("FETCH_HOURS", "24"))          # 抓取时间窗口（小时）
MAX_ARTICLES_PER_SOURCE = 15                                # 每个源最多抓取的文章数
MAX_PREMIUM_ARTICLES = 20                                   # 进入汇总阶段的最大文章数
