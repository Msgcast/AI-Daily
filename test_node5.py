
import os
import logging
from src.state import AgentState
from src.nodes.node_xhs_writer import node_xhs_writer
from src.config import HTTP_PROXY, HTTPS_PROXY, GEMINI_API_KEY
import asyncio

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_node5():
    # Construct a sample state with a large summary
    state = AgentState(
        master_summary="这是一个非常长的测试摘要。" * 150 # Make it somewhat large
    )
    print("Testing Node 5 with gemini-3-flash-preview...")
    result = node_xhs_writer(state)
    print("Result:", result)

if __name__ == "__main__":
    if "XHS_PROXY" in os.environ:
        del os.environ["XHS_PROXY"]
    test_node5()
