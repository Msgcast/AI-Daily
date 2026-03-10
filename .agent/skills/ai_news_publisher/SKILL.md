---
name: AI新闻发布智能体 (AI News Publishing Agent)
description: 一个全自动、全链路的AI资讯日报生产与发布系统。基于 LangChain + LangGraph 框架，每日自动从多平台嗅探最新精品AI资讯 → 智能打分汇总 → 生成小红书爆款图文 → 一键发布。
---

# AI 新闻发布智能体 — 技能说明书

## 项目目标

构建一套完整的"AI日报"自动化发布流水线，覆盖以下四个核心阶段：

1. **资讯嗅探与汇总** — 从多个优质 RSS 源抓取过去 24 小时的 AI 资讯，通过 AI 打分、去重、汇总，产出精品资讯摘要
2. **小红书爆款文案生成** — 基于精品摘要，生成符合小红书平台调性的爆款图文内容（结构化 Pydantic 输出）
3. **AI 生图** — 根据文案内容，生成封面图 + 结构化信息卡片图
4. **图文发布** — 调用小红书 MCP 工具完成图文自动发布

---

## 系统架构（LangGraph 状态机）

```
定时触发器 (APScheduler)
    │
    ▼
Node 1: 多源 RSS 抓取 (feedparser)
    │
    ▼
Node 2: AI 打分与过滤 (DeepSeek-V3, 快速批量)
    │
    ▼
Node 3: 聚类去重 (Embedding + Chroma 向量库)
    │
    ▼
Node 4: Map-Reduce 精品汇总 (DeepSeek-V3, 强力归纳)
    │
    ▼
Node 5: 小红书文案与 HTML 生成 (Gemini-3-Flash-Preview)
    │
    ▼
Node 6: Playwright 截图 (无头浏览器渲染)
    │
    ▼
Node 7: Human-in-the-loop 人工审核 (待实现)
    │
    ▼
Node 8: MCP 图文发布 (小红书 MCP Tool)
```

---

## 项目文件结构

```
Agent_hello/
├── .agent/
│   └── skills/
│       └── ai_news_publisher/
│           └── SKILL.md          # 本文件
├── src/
│   ├── __init__.py
│   ├── config.py                 # 配置管理 (API Key, RSS源, 阈值等)
│   ├── state.py                  # LangGraph 全局 State 定义
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── node_fetcher.py       # Node 1: RSS 抓取
│   │   ├── node_scorer.py        # Node 2: AI 打分过滤
│   │   ├── node_dedup.py         # Node 3: 聚类去重
│   │   ├── node_summarizer.py    # Node 4: 精品汇总
│   │   ├── node_xhs_writer.py    # Node 5: 小红书文案
│   │   ├── node_image_gen.py     # Node 6: AI 生图
│   │   ├── node_human_review.py  # Node 7: 人工审核
│   │   └── node_publisher.py     # Node 8: MCP 发布
│   ├── graph.py                  # LangGraph 工作流组装
│   └── main.py                   # 入口 + 定时调度
├── requirements.txt
├── .env                          # 环境变量 (API Keys)
└── README.md
```

---

## 核心技术选型

| 组件 | 选型 | 说明 |
|---|---|---|
| 工作流引擎 | LangGraph | 状态机、Human-in-loop、断点恢复 |
| LLM | DeepSeek-V3 & Gemini 2.0/3.0 | 打分汇总(DS) / 创意写作与HTML(Gemini) |
| 浏览器截图 | Playwright | 用于将生成的 HTML 渲染为小红书卡片 |
| 代理管理 | Clash (7897) | 贯穿全流程的 API 连通性保障 |
| 发布 | 小红书 MCP | 封装为 LangChain Tool |

---

## 四个精选 RSS 数据源

| 平台 | RSS 地址 | 特点 |
|---|---|---|
| HuggingFace Blog | `https://huggingface.co/blog/feed.xml` | 最权威的 AI 模型发布平台 |
| Hacker News (AI) | `https://hnrss.org/newest?q=AI+LLM&points=50` | 极客社区，信噪比高 |
| VentureBeat AI | `https://venturebeat.com/category/ai/feed/` | 主流科技媒体，行业动态 |
| MIT Technology Review | `https://www.technologyreview.com/feed/` | 顶级学术+产业结合媒体 |

---

## 评分标准（AI 打分节点）

文章评分采用 1-10 分制，通过以下维度综合评估：

- **热度与话题性**（权重40%）：是否有病毒式传播潜力，是否是当下热议话题
- **技术突破性**（权重30%）：是否涉及新模型、新能力、新 benchmark
- **大众可读性**（权重20%）：普通用户能否理解，是否有趣
- **时效性**（权重10%）：是否是最新发生的事件

**过滤阈值：≥ 7 分的文章进入汇总阶段**

---

## 里程碑进度

- [x] **里程碑 1**：打通主数据流（RSS抓取 → AI打分 → 汇总摘要输出）
- [x] **里程碑 2**：小红书文案生成 + HTML 自动化截图生图（Gemini + Playwright）
- [ ] **里程碑 3**：引入 LangGraph 状态机持久化 + Chroma 向量去重
- [ ] **里程碑 4**：MCP 发布 + APScheduler 定时触发
- [ ] **里程碑 5**：生产优化（监控、A/B测试、信宿优化）

---

## 开发约定

1. **API Key 安全**：所有 Key 必须存放在 `.env` 文件中，不得硬编码在代码里
2. **异常处理**：每个节点必须有 try-except，单个数据源失败不影响整体流程
3. **日志规范**：使用 Python `logging` 模块，区分 DEBUG/INFO/ERROR 级别
4. **去重策略**：每次运行时，跳过 3 天内已经处理过的相同链接
5. **成本意识**：打分节点 batch 处理，减少 API 调用次数
