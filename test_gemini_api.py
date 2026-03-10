"""Test Gemini API connectivity and basic generation."""
import os
import sys
import logging
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import GEMINI_API_KEY, HTTP_PROXY

LOG_PATH = os.path.join(os.getcwd(), "test_gemini.log")


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


def main():
    setup_logging()
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    model = os.getenv("GEMINI_TEST_MODEL", "gemini-3-flash-preview")
    timeout = int(os.getenv("GEMINI_TEST_TIMEOUT", "20"))
    client_args = {"proxy": HTTP_PROXY} if HTTP_PROXY else None

    logging.info("Gemini test start. Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Model: %s", model)
    logging.info("Timeout: %s", timeout)
    logging.info("Proxy: %s", HTTP_PROXY or "<none>")

    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY is empty")
        return 1

    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
        max_retries=0,
        timeout=timeout,
        client_args=client_args,
    )

    try:
        res = llm.invoke("Say 'ok' in one word.")
        logging.info("Response: %s", res.content)
        logging.info("Gemini test OK")
        return 0
    except Exception as e:
        logging.error("Gemini test failed: %s", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
