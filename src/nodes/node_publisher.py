"""
Node 7: 小红书自动发布节点 (MCP 驱动)
职责：调用 xiaohongshu-mcp 工具，将图文内容发布到小红书
"""
import os
import logging
import asyncio
from typing import List, Tuple
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from src.state import AgentState
from src.utils.text_sanitize import sanitize_title, sanitize_content, normalize_tags

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:18060/mcp"
TITLE_MAX_CHARS = 20
CONTENT_MAX_CHARS = 1000


def _truncate_text(text: str, max_len: int) -> str:
    if not text:
        return ""
    return text[:max_len]

async def _publish_to_xhs_mcp_http(
    url: str,
    title: str,
    content: str,
    images: List[str],
    tags: List[str],
    retries: int = 1,
) -> Tuple[bool, str | None]:
    """通过 MCP Streamable HTTP 客户端调用发布工具"""
    last_err: str | None = None

    for attempt in range(retries + 1):
        try:
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    login_status = await session.call_tool("check_login_status", {})
                    if "未登录" in str(login_status.content):
                        logger.error("小红书未登录，请先运行登录工具扫描二维码")
                        return False, "not_logged_in"

                    abs_images = [os.path.abspath(img) for img in images]
                    logger.info("正在发布至小红书: %s", title)
                    publish_result = await session.call_tool("publish_content", {
                        "title": title,
                        "content": content,
                        "images": abs_images,
                        "tags": tags,
                        "is_original": True
                    })
                    logger.info("MCP 返回结果: %s", publish_result.content)
                    return True, None
        except Exception as e:
            last_err = str(e)
            logger.warning("发布异常(第 %d 次): %s", attempt + 1, last_err)
            if attempt < retries:
                await asyncio.sleep(1.0)

    return False, last_err


def node_publisher(state: AgentState) -> dict:
    """LangGraph Node 7 - 自动化发布"""
    logger.info("=" * 60)
    logger.info("Node 7: 开始小红书自动化发布")
    logger.info("=" * 60)

    xhs_post = state.get("xhs_post", {})
    images = state.get("images", [])

    if not xhs_post or not images:
        logger.warning("无文案或图片素材，跳过发布")
        return {"error_log": "Missing post or images"}

    title = xhs_post.get("title", "今日 AI 科技专刊")
    content = xhs_post.get("content", "")
    tags = xhs_post.get("tags", [])

    # 二次清洗，避免 Markdown 符号与重复标签
    title = sanitize_title(title, TITLE_MAX_CHARS)
    content = sanitize_content(content, CONTENT_MAX_CHARS, remove_hashtags=True)
    tags = normalize_tags(tags)

    # 强约束：小红书标题<=20字，正文<=1000字
    if len(title) > TITLE_MAX_CHARS:
        logger.warning("标题超限(%s>%s)，将自动截断。", len(title), TITLE_MAX_CHARS)
        title = _truncate_text(title, TITLE_MAX_CHARS)
    if len(content) > CONTENT_MAX_CHARS:
        logger.warning("正文超限(%s>%s)，将自动截断。", len(content), CONTENT_MAX_CHARS)
        content = _truncate_text(content, CONTENT_MAX_CHARS)

    url = os.getenv("XHS_MCP_URL", DEFAULT_URL).strip()
    retries = int(os.getenv("XHS_MCP_RETRIES", "1"))

    # 运行异步发布任务
    try:
        loop = asyncio.get_running_loop()
        # 已有事件循环（通常在异步环境）
        import nest_asyncio
        nest_asyncio.apply()
        success, _ = loop.run_until_complete(
            _publish_to_xhs_mcp_http(url, title, content, images, tags, retries)
        )
    except RuntimeError:
        # 当前线程没有事件循环（Python 3.11+ 常见）
        success, _ = asyncio.run(
            _publish_to_xhs_mcp_http(url, title, content, images, tags, retries)
        )

    if success:
        logger.info("小红书图文发布成功")
        return {"error_log": None}
    else:
        logger.error("小红书图文发布失败")
        return {"error_log": "Publishing failed"}
