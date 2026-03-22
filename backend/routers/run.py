"""
发布控制路由
POST /api/run/full        - 完整流程（返回 task_id）
POST /api/run/node/{name} - 单节点测试
GET  /api/run/status/{task_id} - 查询状态
GET  /api/run/log/{task_id}    - SSE 实时日志流
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import engine
from backend.models import TaskRecord
from backend.services import runner

router = APIRouter(prefix="/api/run", tags=["run"])

class RunRequest(BaseModel):
    sources_override: Optional[list] = None

# --- 传统 AI 资讯日报 ---
@router.post("/news")
def run_news(req: RunRequest = RunRequest()):
    """启动官方：【每日AI资讯】全链路发布模式"""
    task_id = runner.start_task(topic="daily_news", sources_override=req.sources_override)
    return {"task_id": task_id, "label": "每日AI资讯", "status": "running"}

# --- 新增 Reddit 热议 ---
@router.post("/reddit")
def run_reddit():
    """启动：【Reddit热议】全链路发布模式"""
    task_id = runner.start_task(topic="reddit_hot")
    return {"task_id": task_id, "label": "Reddit热议", "status": "running"}


@router.get("/status/{task_id}")
def get_status(task_id: str):
    with Session(engine) as session:
        stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
        record = session.exec(stmt).first()
        if not record:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {
            "task_id": record.task_id,
            "status": record.status,
            "mode": record.mode,
            "node_name": record.node_name,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "error_log": record.error_log,
        }


@router.get("/log/{task_id}")
async def stream_log(task_id: str):
    """SSE 实时日志流"""

    async def event_generator():
        log_q = runner.get_log_queue(task_id)
        if log_q is None:
            # 查数据库中已完成的任务
            with Session(engine) as session:
                stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
                record = session.exec(stmt).first()
                if record and record.run_log:
                    for line in record.run_log.split("\n"):
                        yield f"data: {json.dumps({'log': line})}\n\n"
                yield f"data: {json.dumps({'event': 'done'})}\n\n"
            return

        while True:
            try:
                msg = log_q.get(timeout=0.1)
                if msg == "__END__":
                    yield f"data: {json.dumps({'event': 'done'})}\n\n"
                    break
                yield f"data: {json.dumps({'log': msg})}\n\n"
            except Exception:
                await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
