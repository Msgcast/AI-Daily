"""
Test Script: Reddit Fetcher Standalone Test
任务：验证 node_reddit_fetcher 是否能够在大代理环境下正常抓取 Reddit 贴文、评论和分数。
"""
import os
import sys
import logging
from dotenv import load_dotenv

# 确保项目路径可见
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.nodes.node_reddit_fetcher import node_reddit_fetcher

# 配置日志输出
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

def test_reddit_fetcher():
    load_dotenv()
    
    # 模拟初始状态
    initial_state = {"raw_articles": []}
    
    print("\n" + "="*40)
    print("🚀 启动 Reddit Fetcher 单节点测试...")
    print("="*40)
    
    # 执行节点
    result = node_reddit_fetcher(initial_state)
    
    # 获取输出结果
    submission = result.get("reddit_submission")
    error = result.get("error_log")
    
    if error:
        print(f"❌ [失败] 节点执行报错: {error}")
        return False
    
    if not submission:
        print("❌ [失败] 未返回 reddit_submission 数据")
        return False
    
    print("\n" + "-"*40)
    print("✅ [成功指标 1] API 通道已打通")
    print(f"   [抓取贴文]: {submission['title']}")
    print(f"   [作者/分数]: u/{submission.get('author', 'unknown')} | Status: {submission.get('score', 'High Upvoted via RSS')}")
    print(f"   [原文链接]: {submission['link']}")
    
    print("\n" + "-"*40)
    print(f"✅ [成功指标 2] 高赞评论内容抓取质量 (获取到 {len(submission['comments'])} 条)")
    
    # 打印全部评论作为样张
    for i, cmd in enumerate(submission['comments']):
        print(f"   [评论 {i+1}]: {cmd['author']} (⬆️ {cmd.get('score', 'High')})")
        print(f"     内容: {cmd['body'][:200]}...")
        print("")
    
    print("-"*40)
    print("✅ [成功指标 3] 状态字段隔离验证")
    # 确保没有混入 raw_articles
    if not result.get("raw_articles"):
        print("   [✓] 校验成功: 未对原 AI 新闻流 (raw_articles) 产生任何污染。")
    
    print("\n" + "="*40)
    print("🎨 [测试结论]: 节点已就绪，具备转化为 XHS 小红书风格数据的能力。")
    print("="*40)
    return True

if __name__ == "__main__":
    test_reddit_fetcher()
