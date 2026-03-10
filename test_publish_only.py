"""Standalone MCP publish test (no generation)."""
import os
import sys
import glob
import logging
from datetime import datetime
from typing import List

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

LOG_PATH = os.path.join(os.getcwd(), "publish_only.log")


def setup_logging():
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def list_images(image_dir: str) -> List[str]:
    patterns = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(image_dir, p)))
    files = [os.path.abspath(f) for f in files]
    files.sort()
    return files


def safe_len(text: str) -> int:
    return len(text or "")


async def main_async():
    url = os.getenv("XHS_MCP_URL", "http://127.0.0.1:18060/mcp").strip()
    retries = int(os.getenv("XHS_MCP_RETRIES", "1"))

    image_dir = os.path.join(os.getcwd(), "image")
    images = list_images(image_dir)

    title = "测试发布"
    content = "这是MCP发布节点测试内容。\n#测试 #AI"
    tags = ["测试", "AI"]

    logging.info("Publish-only test start. Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("MCP URL: %s", url)
    logging.info("Retries: %s", retries)
    logging.info("Image dir: %s", image_dir)
    logging.info("Images found: %s", len(images))
    if images:
        logging.info("Images: %s", ", ".join(images))
    else:
        logging.warning("No images found. Publish may fail.")

    logging.info("Title len=%s, Content len=%s", safe_len(title), safe_len(content))

    for attempt in range(retries + 1):
        try:
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    login_status = await session.call_tool("check_login_status", {})
                    logging.info("Login status: %s", login_status.content)
                    if "未登录" in str(login_status.content):
                        logging.error("Not logged in. Please login via xiaohongshu-login.")
                        return

                    publish_result = await session.call_tool("publish_content", {
                        "title": title,
                        "content": content,
                        "images": images,
                        "tags": tags,
                        "is_original": True
                    })
                    logging.info("Publish result: %s", publish_result.content)
                    return
        except Exception as e:
            logging.error("Publish exception (attempt %s): %s", attempt + 1, e)
            if attempt >= retries:
                raise


def main():
    setup_logging()
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    import asyncio
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
