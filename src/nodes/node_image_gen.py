"""
Node 6: Playwright 杂志卡片渲染节点
职责：如果 Node 5.5 返回了 Generative HTML 源码则优先直接截图渲染，如果返回空（遇到生成异常或降级），则用备用的 Jinja2 经典静态模板填充数据。
"""
import os
import logging
from datetime import datetime
from jinja2 import Template
from playwright.sync_api import sync_playwright

from src.state import AgentState

logger = logging.getLogger(__name__)

IMAGE_DIR = os.path.join(os.getcwd(), "image")
TEMPLATE_DIR = os.path.join(os.getcwd(), "templates")

def _get_template_config():
    """根据日期决定降级使用的经典模版及其对应的分辨率"""
    day_of_year = datetime.now().timetuple().tm_yday
    if day_of_year % 2 != 0:
        return {
            "name": "magazine_v1.html",
            "width": 1200,
            "height": 1600,
            "label": "经典3:4竖屏(V1)"
        }
    else:
        return {
            "name": "magazine_v2.html",
            "width": 1200,
            "height": 1600,
            "label": "艺术竖屏(V2)"
        }

def _render_jinja_fallback(browser, card_data: dict, idx: int, template_name: str, width: int, height: int, timestamp: str) -> str | None:
    """填充降级/指定模版并截图"""
    file_path = os.path.join(IMAGE_DIR, f"card_{timestamp}_{idx:02d}.png")
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    
    try:
        if not os.path.exists(template_path):
            logger.error(f"  [✗] 找不到指定模版: {template_path}")
            return None
            
        with open(template_path, "r", encoding="utf-8") as f:
            template = Template(f.read())
        rendered_html = template.render(**card_data)
        
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(rendered_html)
        page.wait_for_timeout(3000) # 给远程字体和 Tailwind 加载时间
        page.screenshot(path=file_path, full_page=False)
        page.close()
        return file_path if os.path.exists(file_path) else None
    except Exception as e:
        logger.error(f"  [✗] 模版渲染异常 ({template_name}): {e}")
        return None

def node_image_gen(state: AgentState) -> dict:
    """LangGraph Node 6 - 网页渲染与截图保存"""
    logger.info("=" * 60)
    # 默认分辨率配置
    width, height = 1200, 1600
    
    # 获取默认降级配置
    default_config = _get_template_config()
    target_template = state.get("template_name")

    # 自动识别 Reddit 模式
    if "reddit_submission" in state:
        target_template = "reddit_card.html"
        logger.info(f"  [⚡] 自动识别到 Reddit 模式，切换 Template 为: {target_template}")
    
    # 最终确定渲染模板名
    if not target_template:
        target_template = default_config["name"]
        logger.info(f"  [ℹ️] 使用系统默认轮换模板: {target_template}")
    else:
        logger.info(f"  [ℹ️] 使用指定模板进行渲染: {target_template}")

    # 获取需要渲染的数据列表
    card_data_list = state.get("card_data_list", [])
    generated_html_list = state.get("generated_html_list", [])
    
    if not card_data_list and not generated_html_list:
        logger.warning("  ⚠️ 无任何排版数据或 HTML，跳过渲染")
        return {"images": []}

    os.makedirs(IMAGE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_images = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # --- 策略 A: 优先使用 Generative UI (通常用于 AI 日报动态创新) ---
        if generated_html_list:
            logger.info(f"  🌟 检测到 {len(generated_html_list)} 张大模型动态生成的源码，启动优先渲染模式...")
            for i, html_source in enumerate(generated_html_list, 1):
                try:
                    file_path = os.path.join(IMAGE_DIR, f"magazine_{timestamp}_genUI_{i:02d}.png")
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_content(html_source)
                    page.wait_for_timeout(3000) 
                    page.screenshot(path=file_path, full_page=False)
                    page.close()
                    if os.path.exists(file_path):
                        generated_images.append(file_path)
                        logger.info(f"    [✓] AI 动态海报 {i} 渲染成功")
                except Exception as e:
                    logger.error(f"    [✗] AI 动态海报 {i} 渲染崩溃: {e}")
                    
        # --- 策略 B: 使用经典/指定 Jinja 模板 (Reddit 专题主要走这条路径) ---
        if not generated_images and card_data_list:
            logger.info(f"  🛡️ 启动模板渲染模式: {target_template}")
            for i, data in enumerate(card_data_list, 1):
                path = _render_jinja_fallback(browser, data, i, target_template, width, height, timestamp)
                if path:
                    generated_images.append(path)
                    logger.info(f"    [✓] 静态海报 {i} 渲染成功")
                    
        browser.close()
            
    logger.info(f"\n✅ Node 6 结束: 成功导出 {len(generated_images)} 张最终长图")
    return {"images": generated_images}
