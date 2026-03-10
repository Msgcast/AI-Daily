"""
主入口文件
运行完整的 AI 资讯日报工作流（里程碑1）
"""
import logging
import sys
from datetime import datetime

# 强制输出 utf-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.rule import Rule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
# 让 httpx / httpcore 的日志不要太啰嗦
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from src.graph import app

console = Console()


def run():
    """执行一次完整的 AI 资讯日报生成流程"""
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    console.print()
    console.print(Panel(
        f"[bold cyan]🤖 AI 资讯智能体[/bold cyan]\n"
        f"[dim]里程碑 1 — RSS 抓取 → AI打分 → 精品汇总[/dim]\n"
        f"[dim]运行时间: {run_time}[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()

    # 执行 LangGraph 工作流
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

    final_state = app.invoke(initial_state)

    # 输出统计信息
    console.print()
    console.print(Rule("[bold yellow]📊 运行统计[/bold yellow]"))
    console.print(f"  [dim]原始抓取文章:[/dim] [bold]{len(final_state.get('raw_articles', []))}[/bold] 篇")
    console.print(f"  [dim]AI 打分完成:[/dim] [bold]{len(final_state.get('scored_articles', []))}[/bold] 篇")
    console.print(f"  [dim]精品文章 (≥7分):[/dim] [bold green]{len(final_state.get('premium_articles', []))}[/bold green] 篇")
    console.print()

    # 输出精品文章得分排行
    premium = final_state.get("premium_articles", [])
    if premium:
        console.print(Rule("[bold yellow]🏆 精品文章排行榜[/bold yellow]"))
        for i, article in enumerate(premium[:10], 1):
            score_color = "green" if article['score'] >= 9 else "yellow" if article['score'] >= 8 else "white"
            console.print(
                f"  [{i:02d}] [{score_color}]{article['score']}分[/{score_color}] "
                f"[cyan]{article['category']}[/cyan] "
                f"[dim]{article['source']}[/dim]\n"
                f"       [bold]{article['title'][:70]}[/bold]\n"
                f"       [dim italic]{article['score_reason']}[/dim italic]\n"
            )

    # 输出最终日报
    master_summary = final_state.get("master_summary", "")
    if master_summary:
        console.print()
        console.print(Rule("[bold magenta]📰 今日 AI 精品日报[/bold magenta]"))
        console.print()
        console.print(Markdown(master_summary))
    # 输出小红书文案与排版
    xhs_post = final_state.get("xhs_post", {})
    images = final_state.get("images", [])
    if xhs_post:
        console.print()
        console.print(Rule("[bold red]💌 小红书爆款文案[/bold red]"))
        console.print(f"[bold]标题: [/bold] [red]{xhs_post.get('title', '')}[/red]\n")
        console.print(xhs_post.get('content', ''))
        console.print("\n[dim]话题标签: [/dim]" + " ".join(xhs_post.get('tags', [])))
        console.print(Rule("[bold blue]🖼️ 配图生成结果[/bold blue]"))
        if images:
            for img in images:
                console.print(f"  ✅ 成功保存: [green]{img}[/green]")
        else:
            console.print("[yellow]⚠️ 未成功生成或保存图片，请检查日志[/yellow]")

    console.print()
    console.print(Panel(
        "[green]✅ 里程碑 2 (小红书排版与配图) 完成！[/green]\n"
        "[dim]图片已存放在项目 image/ 目录下。[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    run()
