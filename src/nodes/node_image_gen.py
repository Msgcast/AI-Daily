"""
Node 6: Playwright 杂志卡片渲染节点
职责：根据日期轮换模版，利用 Jinja2 填充数据，并使用 Playwright 截图
"""
import os
import logging
from datetime import datetime
from jinja2 import Template
from playwright.sync_api import sync_playwright

from src.state import AgentState

logger = logging.getLogger(__name__)

# 路径与模版配置
IMAGE_DIR = os.path.join(os.getcwd(), "image")
TEMPLATE_DIR = os.path.join(os.getcwd(), "templates")

def _get_template_config():
    """根据日期决定使用的模版及其对应的分辨率"""
    day_of_year = datetime.now().timetuple().tm_yday
    
    # 隔日轮换逻辑：偶数天用 V1 (横屏)，奇数天用 V2 (竖屏)
    # 你也可以根据需求改为日期：datetime.now().day % 2
    if day_of_year % 2 == 0:
        return {
            "name": "magazine_v1.html",
            "width": 1200,
            "height": 675,
            "label": "杂志V1 (经典横屏)"
        }
    else:
        return {
            "name": "magazine_v2.html",
            "width": 1200,
            "height": 1450,
            "label": "琉光手稿V2 (艺术竖屏)"
        }

def _render_and_screenshot(card_data: dict, idx: int, config: dict) -> str | None:
    """填充选定的模版并截图"""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    file_path = os.path.join(IMAGE_DIR, f"magazine_{idx:02d}.png")
    template_path = os.path.join(TEMPLATE_DIR, config["name"])
    
    try:
        if not os.path.exists(template_path):
            logger.error(f"  [✗] 找不到模版: {template_path}")
            return None
            
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
            
        template = Template(template_content)
        rendered_html = template.render(**card_data)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": config["width"], "height": config["height"]})
            page.set_content(rendered_html)
            
            # 等待确保 WebFonts 加载完成
            page.wait_for_timeout(2000) 
            
            page.screenshot(path=file_path, full_page=False)
            browser.close()
            
            if os.path.exists(file_path):
                logger.info(f"  [✓] {config['label']} 渲染成功: {file_path}")
                return file_path
    except Exception as e:
        logger.error(f"  [✗] 渲染截图异常: {e}")
        return None


def node_image_gen(state: AgentState) -> dict:
    """LangGraph Node 6 - 杂志模版填充与截图"""
    logger.info("=" * 60)
    logger.info("▶ Node 6: 开始填充杂志模版并截图 (样式轮换)")
    logger.info("=" * 60)

    card_data_list = state.get("card_data_list", [])
    if not card_data_list:
        logger.warning("  ⚠️ 无可用卡片数据，跳过渲染")
        return {"images": []}

    # 获取今日模版配置
    config = _get_template_config()
    logger.info(f"  📅 今日应用风格: {config['label']} ({config['width']}x{config['height']})")
    logger.info(f"  待处理任务: {len(card_data_list)} 页")
    
    generated_images = []
    for i, data in enumerate(card_data_list, 1):
        logger.info(f"  [{i}/{len(card_data_list)}] 渲染中...")
        path = _render_and_screenshot(data, i, config)
        if path:
            generated_images.append(path)
            
    logger.info(f"\n✅ Node 6 结束: 成功保存 {len(generated_images)} 张图片至 image/ 目录")
    return {"images": generated_images}
