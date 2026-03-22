"""
Node: Reddit RSS 嗅探节点 (node_reddit_fetcher) - 方案 A (RSS 改良版)
职责：无需 API 密钥，直接通过 Reddit 公开 RSS 抓取高赞讨论题目及部分高赞评论。
"""
import logging
import feedparser
import httpx
import re
import random
from src.state import AgentState
from src.config import HTTP_PROXY, FETCH_HOURS

logger = logging.getLogger(__name__)

# 配置需要嗅探的 Subreddit 列表
REDDIT_SOURCES = [
    "https://www.reddit.com/r/AskReddit/top/.rss?t=day",
    "https://www.reddit.com/r/Life/top/.rss?t=day",
    "https://www.reddit.com/r/NoStupidQuestions/top/.rss?t=all&limit=20",
    "https://www.reddit.com/r/AskOldPeopleAdvice/top/.rss?t=day",
    "https://www.reddit.com/r/AskChinese/top/.rss?t=day"
]

def _select_best_topic_with_ai(titles_data: list) -> dict:
    """使用 DeepSeek 从候选标题中避开重复，智选符合小红书的高价值选题"""
    from langchain_openai import ChatOpenAI
    from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, HTTP_PROXY
    import random
    
    if not titles_data: return None
    
    # 打乱顺序，避免每次都看第一条
    random.shuffle(titles_data)
    candidates = titles_data[:12]
    
    logger.info(f"  [⚡] 智选筛选池 (12个随机Top话题)...")
    
    formatted_titles = ""
    for i, t in enumerate(candidates):
        formatted_titles += f"[{i}] {t['title']}\n"

    # --- 新增：查重逻辑 (获取最近 5 天已发布的模型) ---
    recent_titles = []
    try:
        from sqlmodel import Session, select
        from backend.database import engine
        from backend.models import TaskRecord
        from datetime import datetime, timedelta
        
        with Session(engine) as session:
            five_days_ago = datetime.utcnow() - timedelta(days=5)
            # 查找最近 5 天内成功发布的 reddit_hot 记录
            stmt = select(TaskRecord).where(
                TaskRecord.mode == "reddit_hot",
                TaskRecord.status == "success",
                TaskRecord.finished_at >= five_days_ago
            )
            records = session.exec(stmt).all()
            # 提取标题（xhs_title 通常包含选题核心）
            recent_titles = [r.xhs_title for r in records if r.xhs_title]
    except Exception as e:
        logger.warning(f"  [!] 无法加载历史记录进行去重: {e}")

    try:
        llm = ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.7, # 增加随机性
            http_client=httpx.Client(proxy=HTTP_PROXY) if HTTP_PROXY else None
        )
        
        system_prompt = f"""你是一位小红书爆款内容总编。
请从以下话题中选出一个最具备【认知觉醒、自律成长、人生智慧、人性真相】属性的话题。

### 历史发布记录（请绝对避开）：
{recent_titles if recent_titles else "暂无"}

### 任务规则：
1. 请对比候选话题与历史记录，坚决排除内容雷同、选题重复的话题。
2. 坚决避开：两性关系、性幻想、低俗话题、政治新闻、纯搞笑。
3. 优先选择：那些能让人“刷新认知”、“感到扎心”或“学到生活真相”的内容。
只返回该话题的索引数字（例如 5），不要任何多余解释。"""
        
        resp = llm.invoke([
            ("system", system_prompt),
            ("human", f"候选话题如下：\n{formatted_titles}")
        ])
        
        match = re.search(r'(\d+)', resp.content)
        idx = int(match.group(1)) if match else 0
        return candidates[idx] if idx < len(candidates) else candidates[0]
    except Exception as e:
        logger.warning(f"  [!] AI 选题失败，使用备份策略: {e}")
        return candidates[0]

def _fetch_rss(url: str):
    """带代理的 RSS 抓取"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        with httpx.Client(proxy=HTTP_PROXY, headers=headers, timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return feedparser.parse(resp.content)
    except Exception as e:
        logger.error(f"  [X] RSS 抓取异常 ({url}): {e}")
        return None

def _clean_content(html: str):
    """深度清洗 Reddit RSS：移除 HTML、引用(Blockquote)及低价值链接"""
    if not html: return ""
    
    # 1. 移除引用块 (Reddit RSS 中引用内容通常在 <blockquote> 中，这是导致楼中楼回复感的核心原因)
    text = re.sub(r'<blockquote>.*?</blockquote>', '', html, flags=re.DOTALL)
    
    # 2. 移除作者及元数据链接
    text = re.sub(r'submitted by.*?<a.*?/u/.*?>.*?</a>', '', text)
    text = re.sub(r'<a.*?>\[link\]</a>', '', text)
    text = re.sub(r'<a.*?>\[comments\]</a>', '', text)
    
    # 3. 剥离所有剩余 HTML 标签并处理实体
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 4. 移除多余空白
    return text.strip()

def _is_high_quality_comment(text: str, entry_link: str = "") -> bool:
    """物理层预洗：过滤短评、长评及可能的非首层楼评论"""
    if not text or len(text) < 40: 
        return False
    if len(text) > 800: 
        return False
    
    # 判定规则：Reddit RSS 的评论链接中，
    # 首层评论通常不包含深度路径或具有特定的 URL 特征。
    # 此外，如果内容以 "Replying to" 或大量引用开头，则排除。
    if "context=3" in entry_link or "context=2" in entry_link:
        return False

    words = text.split()
    if len(words) < 8:
        return False
        
    return True

def node_reddit_fetcher(state: AgentState) -> dict:
    """
    LangGraph Node - Reddit RSS 嗅探器 (方案 A)
    """
    logger.info("=" * 60)
    logger.info("▶ Node: 开始执行 Reddit RSS 方案 A 嗅探 (无需 API 密钥)")
    logger.info("=" * 60)

    all_potential_posts = []

    # 1. 嗅探各大 Subreddit 的 Top 排行榜
    for rss_url in REDDIT_SOURCES:
        feed = _fetch_rss(rss_url)
        if not feed or not feed.entries: continue
        
        for entry in feed.entries:
            # 简单判断是否包含“高赞”标识（Reddit RSS 标题常含 score info，或至少是 Top 榜单）
            # 方案 A 默认 Top 榜单均为高质量
            all_potential_posts.append({
                "title": entry.title,
                "link": entry.link,
                "author": entry.author if hasattr(entry, 'author') else "unknown"
            })

    # 2. 挑选评分最高的第一个贴子（Top 榜首通常极具爆款潜质）
    # --- 升级：使用 DeepSeek 智选标题 ---
    top_post = _select_best_topic_with_ai(all_potential_posts[:10])
    
    if not top_post:
        logger.warning("  ⚠️ 未发现任何 Reddit 热门讨论。")
        return {"error_log": "No recent top Reddit posts found via RSS"}

    logger.info(f"  [✓] AI 锁定爆款选题: {top_post['title']}")
    
    # 3. 核心黑科技：对单帖再次发起 RSS 请求以获取“讨论评论”
    # Reddit 贴子链接加 .rss 即可看到评论 XML
    comments_rss_url = top_post['link'] + ".rss?sort=top"
    logger.info(f"  [⚡] 正在嗅探讨论串详情: {comments_rss_url}")
    
    comments_feed = _fetch_rss(comments_rss_url)
    comments_data = []

    if comments_feed and len(comments_feed.entries) > 1:
        # entries[0] 通常是主贴本身，从 [1:] 开始是评论
        valid_comments = []
        for entry in comments_feed.entries[1:]:
            link = getattr(entry, 'link', '')
            body_raw = entry.summary if hasattr(entry, 'summary') else ""
            
            # 策略：如果 entry 的 ID 或 Link 深度超过阈值，往往是楼中楼。
            # 物理层面深度检测：Reddit RSS 评论链接结构
            body = _clean_content(body_raw)
            
            # --- 物理层预洗：只保留【首层】且有厚度的评论 ---
            if _is_high_quality_comment(body, link):
                valid_comments.append({
                    "author": entry.author if hasattr(entry, 'author') else "anonymous",
                    "body": body
                })
        
        # 仅取前 20 条进入后续 AI 打分环节
        for i, comment in enumerate(valid_comments[:20]):
            # 生成虚拟的高赞数字，增加小红书排版的视觉真实感
            fake_score = f"{random.randint(5, 25)}.{random.randint(0, 9)}k"
            
            comments_data.append({
                "author": comment["author"],
                "body": comment["body"],
                "order": i + 1,
                "score": fake_score
            })
    
    logger.info(f"  [✓] 物理预洗完成: 从原始讨论中筛选出 {len(comments_data)} 条候选高质量评论。")

    return {
        "reddit_submission": {
            "title": top_post['title'],
            "author": top_post['author'],
            "link": top_post['link'],
            "comments": comments_data
        }
    }
