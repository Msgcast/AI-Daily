"""
Reddit Pipeline Test Script (No Publish)
Run fetcher -> filter -> transformer -> image_gen
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Ensure project path is visible
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure src is visible
sys.path.append(os.path.join(ROOT, "src"))

from src.nodes.node_reddit_fetcher import node_reddit_fetcher
from src.nodes.node_reddit_filter import node_reddit_filter
from src.nodes.node_reddit_transformer import node_reddit_transformer
from src.nodes.node_image_gen import node_image_gen

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def test_reddit_flow_no_publish():
    load_dotenv()
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("🚨 [Error]: Please set GOOGLE_API_KEY in .env!")
        return

    state = {
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

    print("\n🚀 Step 1: Fetching Reddit content...")
    state.update(node_reddit_fetcher(state))
    
    # In case fetcher fails, use a mock update to proceed
    if not state.get("reddit_submission"):
        print("   ⚠️ Fetcher returned no data. Using mock data.")
        state["reddit_submission"] = {
            "title": "What's a truth about life that most people refuse to accept?",
            "author": "Soul_Searcher",
            "score": "12.5k",
            "link": "https://reddit.com/r/AskReddit/mock",
            "comments": [
                {
                    "author": "Practical_Hope",
                    "score": "8.2k",
                    "body": "No one is coming to save you. You are the only person responsible for your happiness and success. Stop waiting for a miracle. " * 5,
                    "order": 1
                }
            ]
        }

    print("\n🚀 Step 2: Filtering content...")
    state.update(node_reddit_filter(state))
    
    print("\n🚀 Step 3: Transforming/Translating...")
    state.update(node_reddit_transformer(state))
    
    print("\n🚀 Step 4: Generating images...")
    
    print("\n--- Card Index Data Check ---")
    for i, card in enumerate(state.get("card_data_list", [])):
        print(f"Card {i}: badge={card.get('badge_number')}, user={card.get('user_name')}, is_title={card.get('is_title_page')}")
    
    state.update(node_image_gen(state))

    print("\n" + "="*50)
    print("✅ Testing completed!")
    print(f"Generated {len(state.get('images', []))} images.")
    for img in state.get('images', []):
        print(f" - {img}")
    print("="*50)

if __name__ == "__main__":
    test_reddit_flow_no_publish()
