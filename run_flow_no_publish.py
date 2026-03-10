"""Run pipeline nodes 1-6 (no publish) with verbose logs and outputs."""
import sys
import os
import logging
from datetime import datetime
from pathlib import Path

from langgraph.graph import StateGraph, END

from src.state import AgentState
from src.nodes.node_fetcher import node_fetcher
from src.nodes.node_scorer import node_scorer
from src.nodes.node_dedup import node_dedup
from src.nodes.node_summarizer import node_summarizer
from src.nodes.node_xhs_writer import node_xhs_writer
from src.nodes.node_image_gen import node_image_gen


def _setup_logging(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    # Reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def build_graph_no_publish():
    graph = StateGraph(AgentState)
    graph.add_node("fetcher", node_fetcher)
    graph.add_node("scorer", node_scorer)
    graph.add_node("dedup", node_dedup)
    graph.add_node("summarizer", node_summarizer)
    graph.add_node("xhs_writer", node_xhs_writer)
    graph.add_node("image_gen", node_image_gen)

    graph.set_entry_point("fetcher")
    graph.add_edge("fetcher", "scorer")
    graph.add_edge("scorer", "dedup")
    graph.add_edge("dedup", "summarizer")
    graph.add_edge("summarizer", "xhs_writer")
    graph.add_edge("xhs_writer", "image_gen")
    graph.add_edge("image_gen", END)

    return graph.compile()


def _write_markdown_report(output_dir: Path, state: dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "run_no_publish_report.md"

    raw_articles = state.get("raw_articles", [])
    scored_articles = state.get("scored_articles", [])
    premium_articles = state.get("premium_articles", [])
    master_summary = state.get("master_summary", "")
    xhs_post = state.get("xhs_post", {})
    images = state.get("images", [])

    lines = []
    lines.append(f"# Run Report (no publish)\n")
    lines.append(f"- Raw articles: {len(raw_articles)}")
    lines.append(f"- Scored articles: {len(scored_articles)}")
    lines.append(f"- Premium articles: {len(premium_articles)}\n")

    if premium_articles:
        lines.append("## Premium Articles (Top 10)\n")
        for i, a in enumerate(premium_articles[:10], 1):
            lines.append(f"{i}. [{a['score']}分] {a['title']} ({a['source']})")
        lines.append("")

    if master_summary:
        lines.append("## Master Summary\n")
        lines.append(master_summary)
        lines.append("")

    if xhs_post:
        lines.append("## XHS Draft\n")
        lines.append(f"**标题**：{xhs_post.get('title', '')}")
        lines.append("")
        lines.append(xhs_post.get("content", ""))
        lines.append("")
        lines.append("**标签**：" + " ".join(xhs_post.get("tags", [])))
        lines.append("")

    if images:
        lines.append("## Images\n")
        for img in images:
            lines.append(f"- {img}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"Run nodes 1-6 (no publish). Time: {run_time}")

    log_path = Path(os.getcwd()) / "run_no_publish.log"
    _setup_logging(log_path)

    initial_state = {
        "raw_articles": [],
        "scored_articles": [],
        "premium_articles": [],
        "deduped_events": [],
        "master_summary": "",
        "images": [],
        "xhs_post": {},
        "card_data_list": [],
        "error_log": None,
    }

    app = build_graph_no_publish()
    final_state = app.invoke(initial_state)

    report_path = _write_markdown_report(Path(os.getcwd()), final_state)

    logging.info("Run completed.")
    logging.info("Summary length: %s", len(final_state.get("master_summary", "")))
    logging.info("Images: %s", len(final_state.get("images", [])))
    logging.info("Report: %s", report_path)


if __name__ == "__main__":
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
