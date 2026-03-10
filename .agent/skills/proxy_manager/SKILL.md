---
name: 代理管理工具 (Proxy Manager)
description: 专门管理网络代理配置，特别是针对本地 Clash (7897端口) 的适配，确保 Gemini 等海外 API 的连通性。
---

# 代理管理工具

## 功能描述
本工具用于在 Python 环境中全局配置 HTTP/HTTPS 代理。主要针对本地运行的 Clash 客户端（端口 7897）。

## 核心配置
- **HTTP_PROXY**: `http://127.0.0.1:7897`
- **HTTPS_PROXY**: `http://127.0.0.1:7897`

## 使用方法
在 Python 启动文件的顶部引入以下代码段：

```python
import os

def setup_proxy():
    """配置本地 Clash 代理"""
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
    print("✅ 代理已配置: 127.0.0.1:7897")

# 在 main.py 或相关逻辑开始前调用
setup_proxy()
```

## 注意事项
1. 确保 Clash 开启了 **System Proxy** 或 **Allow LAN** 以及正确的 **Port (7897)**。
2. 对于部分库（如 `httpx`, `requests`），环境变量会自动生效。
3. 对于特定 SDK（如 Google Generative AI），建议使用带有 `proxies` 参数的 transport 或者是全局环境变量。
