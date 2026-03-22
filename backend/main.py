"""
FastAPI 主应用入口
- 挂载所有路由
- 启动时初始化数据库、加载定时任务、载入默认数据源
- 静态文件服务 frontend/
"""
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# 确保项目根目录在 Python 路径中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

from backend.database import create_db_and_tables, engine
from backend.models import RssSource
from backend.routers import run, schedule, records, sources, external
from backend.services import scheduler as sched_svc
from src.config import RSS_SOURCES as DEFAULT_RSS_SOURCES

app = FastAPI(title="AI 资讯智能体后台", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(run.router)
app.include_router(schedule.router)
app.include_router(records.router)
app.include_router(sources.router)
app.include_router(external.router)


@app.get("/api/image")
async def serve_image(path: str):
    """本地图片文件服务（Pipeline 生成的配图）"""
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    import os
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(abs_path)



@app.on_event("startup")
def on_startup():
    # 1. 建表
    create_db_and_tables()

    # 2. 若数据源表为空，导入默认配置
    from sqlmodel import Session, select
    with Session(engine) as session:
        count = session.exec(select(RssSource)).all()
        if not count:
            for s in DEFAULT_RSS_SOURCES:
                session.add(RssSource(
                    name=s["name"],
                    category=s.get("category", "综合资讯"),
                    url=s["url"],
                    description=s.get("description", ""),
                ))
            session.commit()
            logging.getLogger(__name__).info(f"已导入 {len(DEFAULT_RSS_SOURCES)} 个默认数据源")

    # 3. 启动调度器并恢复任务
    sched_svc.start_scheduler()
    sched_svc.load_jobs_from_db()


@app.on_event("shutdown")
def on_shutdown():
    if sched_svc.scheduler.running:
        sched_svc.scheduler.shutdown(wait=False)


# 静态前端文件
FRONTEND_DIR = os.path.join(ROOT, "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
