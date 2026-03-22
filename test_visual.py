"""
Final Test Script: Reddit Full Pipeline with Filter & Scorer
任务：端到端模拟从抓取到【AI 筛选】、AI 翻译、最后到真实图片渲染。
验证 node_reddit_filter (DeepSeek) 是否起作用。
"""
import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# 确保项目路径可见
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.nodes.node_reddit_fetcher import node_reddit_fetcher
from src.nodes.node_reddit_filter import node_reddit_filter
from src.nodes.node_reddit_transformer import node_reddit_transformer
from src.nodes.node_image_gen import node_image_gen

# 配置日志输出
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

def test_full_pipeline():
    load_dotenv()
    
    # 1. 模拟初始状态（抓取）
    state = {"raw_articles": []}
    
    print("\n" + "="*60)
    print("🚀 启动 [Reddit智选版] 全链路视觉渲染测试...")
    print("="*60)
    
    # 执行 1: 抓取 (包含基础物理预洗)
    state.update(node_reddit_fetcher(state))
    if "error_log" in state:
        print(f"❌ 抓取失败: {state['error_log']}")
        return
    
    # 获取抓取到的原始评论数量
    raw_count = len(state["reddit_submission"]["comments"])
    print(f"  [Fetcher] 已物理筛选出 {raw_count} 条较长评论。")

    # 执行 1.5: AI 智能筛选 (DeepSeek)
    state.update(node_reddit_filter(state))
    if "error_log" in state:
        print(f"❌ 筛选失败: {state['error_log']}")
        return
    
    filtered_count = len(state["reddit_submission"]["comments"])
    print(f"  [Scorer] DeepSeek 智选出 {filtered_count} 条精品评论。")

    # 执行 2: 转换 (此时已包含虚拟点赞数和翻译)
    state.update(node_reddit_transformer(state))
    if "error_log" in state:
        print(f"❌ 转换失败: {state['error_log']}")
        return

    # 3. 准备渲染数据
    if "card_data_list" in state:
        for i, card in enumerate(state["card_data_list"]):
            card["page_index"] = i 

    # 4. 执行渲染
    print("\n" + "-"*40)
    print("🎨 正在调用 Playwright 渲染智选后的卡片...")
    
    result = node_image_gen(state)
    
    if "error_log" in result:
        print(f"❌ 渲染失败: {result['error_log']}")
        return

    image_paths = result.get("images", [])
    print("\n" + "="*60)
    print(f"✅ [大功告成] 全链路成功！已智选并生成 {len(image_paths)} 张精品素材。")
    print("============================================================")
    print("💡 提示：请去 image 目录下查看这些图片，特别是翻译的走心程度！")

if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY") or not os.getenv("GOOGLE_API_KEY"):
        print("🚨 [警告]: 请先在 .env 中填入 DEEPSEEK_API_KEY 和 GOOGLE_API_KEY！")
    else:
        test_full_pipeline()
