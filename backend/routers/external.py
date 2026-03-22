from fastapi import APIRouter, HTTPException
import httpx
import logging
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

router = APIRouter(prefix="/api/external", tags=["external"])
logger = logging.getLogger(__name__)

@router.get("/deepseek/balance")
async def get_deepseek_balance():
    """获取 DeepSeek API 账户余额与用量信息"""
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 DEEPSEEK_API_KEY")
    
    # 根据 DeepSeek 文档，余额查询接口通常在根域名下
    url = "https://api.deepseek.com/user/balance"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"DeepSeek Balance API Error: {resp.status_code} - {resp.text}")
                return {"is_available": False, "error": f"API Error: {resp.status_code}"}
            
            data = resp.json()
            # 预期结构: {"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "10.00", ...}]}
            return {
                "is_available": data.get("is_available", False),
                "balance_infos": data.get("balance_infos", [])
            }
    except Exception as e:
        logger.error(f"Failed to fetch DeepSeek balance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/xhs/login_status")
async def get_xhs_login_status():
    """验证小红书当前账号登录是否有效"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import os

    # 这里复用 node_publisher 的逻辑
    url = os.getenv("XHS_MCP_URL", "http://127.0.0.1:18060/mcp")
    
    try:
        # 短超时设置，避免阻塞
        async with streamable_http_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                login_status = await session.call_tool("check_login_status", {})
                
                # 更加稳定地解析 MCP 返回的内容
                def extract_text(item):
                    if hasattr(item, "text"): return str(item.text)
                    if isinstance(item, dict) and "text" in item: return str(item["text"])
                    s = str(item)
                    # 兜底：如果直接 str() 出来的带有 MCP 对象特征，尝试截断
                    if "annotations=" in s:
                         import re
                         match = re.search(r"text='(.*?)'", s)
                         if match: return match.group(1).replace("\\n", "\n")
                         return s.split(", annotations=")[0].strip(" []'\"").replace("TextContent(text=", "")
                    return s

                full_text = ""
                content_list = login_status.content if isinstance(login_status.content, list) else [login_status.content]
                for item in content_list:
                    full_text += extract_text(item)

                is_logged_in = "未登录" not in full_text and "error" not in full_text.lower()
                
                # 尝试解析用户名
                user_name = "Session OK"
                if is_logged_in:
                    # 针对不同的打印格式做兼容
                    if "已登录到" in full_text:
                        name_part = full_text.split("已登录到")[-1].split("\n")[0].strip(" :：")
                        if name_part: user_name = name_part
                    elif "已登录" in full_text:
                        name_part = full_text.split("已登录")[-1].split("\n")[0].strip(" :：")
                        if name_part: user_name = name_part
                    elif "你可以使用其他功能了" in full_text:
                         user_name = "Logged In"

                return {
                    "is_logged_in": is_logged_in,
                    "user_name": user_name,
                    "raw_status": full_text.strip()
                }
    except Exception as e:
        logger.warning(f"XHS MCP Status Check Failed: {str(e)}")
        return {
            "is_logged_in": False,
            "error": "MCP 服务不可达",
            "detail": str(e)
        }
