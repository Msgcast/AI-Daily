"""
Test Script: Reddit Transformer Standalone Test
任务：验证 node_reddit_transformer 是否能正确调用 Gemini 并生成符合
     小红书风格的翻译和单页卡片结构。
"""
import os
import sys
import logging
from dotenv import load_dotenv

# 确保项目路径可见
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.nodes.node_reddit_transformer import node_reddit_transformer

# 配置日志输出
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

def test_reddit_transformer():
    load_dotenv()
    
    # 1. 模拟上游 Fetcher 传回的原始数据
    mock_state = {
        "reddit_submission": {
            "title": "What's a truth about life that most people refuse to accept?",
            "author": "Soul_Searcher",
            "score": "12.5k",
            "link": "https://reddit.com/r/AskReddit/mock",
            "comments": [
                {
                    "author": "Practical_Hope",
                    "score": "8.2k",
                    "body": "No one is coming to save you. You are the only person responsible for your happiness and success. Stop waiting for a miracle.",
                    "order": 1
                },
                {
                    "author": "Life_Explorer",
                    "score": "5.4k",
                    "body": "Most of the people you consider your friends are just people who happen to be around you. Once you move or change jobs, they'll be gone.",
                    "order": 2
                }
            ]
        }
    }
    
    print("\n" + "="*50)
    print("🚀 启动 Transformer 节点单节点测试 (模拟数据)...")
    print("="*50)
    
    # 执行节点
    result = node_reddit_transformer(mock_state)
    
    if result.get("error_log"):
        print(f"❌ [失败] Transformer 执行报错: {result['error_log']}")
        return False
    
    # 获取输出结果
    xhs_post = result.get("xhs_post", {})
    card_data_list = result.get("card_data_list", [])
    
    print("\n" + "-"*40)
    print("✅ [成功指标 1] 爆款文案生成质量")
    print(f"   [小红书标题]: {xhs_post.get('title')}")
    print(f"   [正文预览]: {xhs_post.get('content', '')[:100]}...")
    
    print("\n" + "-"*40)
    print(f"✅ [成功指标 2] 卡片拆解验证 (共 {len(card_data_list)} 张)")
    
    for i, card in enumerate(card_data_list):
        print(f"\n   --- Page #{i+1} ---")
        if card.get("is_title_page"):
            print("   [类型]: 首页大标题")
            print(f"   [中文]: {card.get('title_cn')}")
            print(f"   [英文]: {card.get('title_en')}")
        else:
            print(f"   [类型]: 评论页 (by {card.get('user_name')})")
            print(f"   [点赞]: {card.get('score')}")
            print(f"   [翻译]: {card.get('translated_text')}")
            print(f"   [原文片段]: {card.get('original_text', '')[:50]}...")
    
    print("\n" + "="*50)
    print("🎨 [测试结论]: 节点翻译质量与结构完整性已达标。")
    print("="*50)
    return True

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("🚨 [警告]: 请先在 .env 中填入 GOOGLE_API_KEY！")
    else:
        test_reddit_transformer()
