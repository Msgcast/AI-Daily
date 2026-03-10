"""
Node 1: 多源 RSS 抓取节点
职责：从配置的 4 个 RSS 源抓取过去 N 小时的 AI 资讯文章
"""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from src.config import RSS_SOURCES, FETCH_HOURS, MAX_ARTICLES_PER_SOURCE, HTTP_PROXY, HTTPS_PROXY
from src.state import AgentState, ArticleItem

logger = logging.getLogger(__name__)


@contextmanager
def _with_rss_proxy():
    """仅在 RSS 抓取时临时注入代理环境变量。"""
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


def _parse_published_time(entry) -> datetime | None:
    """解析 RSS 条目的发布时间，返回 UTC 时区感知的 datetime"""
    import calendar

    # feedparser 会尝试解析 entry.published_parsed (struct_time, UTC)
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = calendar.timegm(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    # 备用：updated_parsed
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            ts = calendar.timegm(entry.updated_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    return None


def _clean_html(text: str) -> str:
    """简单去除 HTML 标签，保留纯文本"""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]  # 截断过长摘要，节省后续 Token


def _looks_like_feed(content: bytes) -> bool:
    head = content[:2000].lower()
    return b"<rss" in head or b"<feed" in head or b"<rdf" in head


def _fix_xml_encoding(content: bytes) -> bytes:
    try:
        head = content[:200].decode("ascii", errors="ignore")
    except Exception:
        return content
    if "encoding=\"us-ascii\"" in head.lower():
        return content.replace(b'encoding="us-ascii"', b'encoding="utf-8"', 1)
    return content


def _fetch_feed_content(source_url: str) -> tuple[bytes | None, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    proxy = HTTP_PROXY or None
    try:
        with httpx.Client(
            proxy=proxy,
            headers=headers,
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            resp = client.get(source_url)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "")
    except Exception as e:
        logger.warning(f"[警告] RSS 抓取失败({source_url}): {e}")
        return None, ""


def _fetch_single_source(source: dict, cutoff_time: datetime) -> list[ArticleItem]:
    """
    抓取单个 RSS 源的文章

    Args:
        source: RSS 源配置 dict，含 name/url/description
        cutoff_time: 截止时间，只返回此时间之后的文章

    Returns:
        ArticleItem 列表
    """
    articles: list[ArticleItem] = []
    source_name = source["name"]
    source_cat = source.get("category", "综合资讯")
    source_url = source["url"]

    try:
        logger.info(f"[抓取] 正在抓取: {source_name}")
        
        # 增加超时限制，防止卡死
        import socket
        socket.setdefaulttimeout(15)
        
        content, _content_type = _fetch_feed_content(source_url)
        if content:
            content = _fix_xml_encoding(content)
            if not _looks_like_feed(content):
                logger.warning(f"[警告] {source_name} 返回内容疑似非 RSS/Atom，已跳过")
                return []
            feed = feedparser.parse(content)
        else:
            with _with_rss_proxy():
                feed = feedparser.parse(source_url)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"[警告] {source_name} RSS 解析有异常: {feed.bozo_exception}")

        # 如果没有 entries 且有异常，记录
        if not feed.entries and hasattr(feed, "bozo_exception") and feed.bozo_exception:
            logger.error(f"[错误] {source_name} 抓取无内容且有异常: {feed.bozo_exception}")
            return []

        entries = feed.entries[:MAX_ARTICLES_PER_SOURCE]

        for entry in entries:
            # ── 时效性过滤 ──
            pub_time = _parse_published_time(entry)
            if pub_time and pub_time < cutoff_time:
                continue  # 超出时间窗口，跳过

            # ── 提取字段 ──
            title = getattr(entry, "title", "").strip()
            if not title:
                continue

            # 摘要优先取 summary，其次取 content
            summary = ""
            if hasattr(entry, "summary"):
                summary = _clean_html(entry.summary)
            elif hasattr(entry, "content") and entry.content:
                summary = _clean_html(entry.content[0].get("value", ""))

            link = getattr(entry, "link", "")
            published = pub_time.strftime("%Y-%m-%d %H:%M UTC") if pub_time else "Unknown"

            articles.append(ArticleItem(
                title=title,
                summary=summary,
                link=link,
                published=published,
                source=source_name,
                category=source_cat,
            ))

        logger.info(f"[抓取] {source_name}: 获取到 {len(articles)} 篇有效文章")

    except Exception as e:
        logger.error(f"[错误] 抓取 {source_name} 失败: {e}")

    return articles


def node_fetcher(state: AgentState) -> dict:
    """
    LangGraph Node 1 - RSS 多源抓取
    并行抓取所有配置的 RSS 源，整合结果写入 state.raw_articles
    """
    logger.info("=" * 60)
    logger.info("▶ Node 1: 开始多源 RSS 资讯抓取")
    logger.info("=" * 60)

    # 计算时间截止窗口（UTC）
    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(hours=FETCH_HOURS)
    logger.info(f"  时间窗口: 过去 {FETCH_HOURS} 小时 (截止: {cutoff_time.strftime('%Y-%m-%d %H:%M UTC')})")
    logger.info(f"  配置数据源数量: {len(RSS_SOURCES)} 个\n")

    all_articles: list[ArticleItem] = []

    for source in RSS_SOURCES:
        articles = _fetch_single_source(source, cutoff_time)
        all_articles.extend(articles)

    logger.info(f"\n✅ Node 1 完成: 共抓取 {len(all_articles)} 篇文章")

    return {"raw_articles": all_articles}
