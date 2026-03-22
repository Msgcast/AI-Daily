"""
定时调度路由
GET    /api/schedule         - 获取所有任务
POST   /api/schedule         - 创建/更新
DELETE /api/schedule/{job_id} - 删除
POST   /api/schedule/{job_id}/toggle - 暂停/恢复
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import ScheduleJob
from backend.services import scheduler as sched_svc

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class ScheduleCreate(BaseModel):
    name: str
    topic: str = "daily_news"             # daily_news / reddit_hot
    cron_expr: Optional[str] = None       # e.g. "0 8 * * *"
    interval_hours: Optional[float] = None
    enabled: bool = True


@router.get("")
def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(ScheduleJob)).all()
    result = []
    for job in jobs:
        next_run = sched_svc.get_next_run(job.job_id)
        result.append({
            "id": job.id,
            "job_id": job.job_id,
            "name": job.name,
            "topic": job.topic,
            "cron_expr": job.cron_expr,
            "interval_hours": job.interval_hours,
            "enabled": job.enabled,
            "last_run": job.last_run.isoformat() if job.last_run else None,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return result


@router.post("")
def create_or_update_job(data: ScheduleCreate, session: Session = Depends(get_session)):
    if not data.cron_expr and not data.interval_hours:
        raise HTTPException(status_code=400, detail="必须提供 cron_expr 或 interval_hours")

    job_id = str(uuid.uuid4())
    job = ScheduleJob(
        job_id=job_id,
        name=data.name,
        topic=data.topic,
        cron_expr=data.cron_expr,
        interval_hours=data.interval_hours,
        enabled=data.enabled,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    if data.enabled:
        sched_svc.add_or_update_job(job)

    return {"job_id": job_id, "name": job.name, "status": "created"}


@router.delete("/{job_id}")
def delete_job(job_id: str, session: Session = Depends(get_session)):
    stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
    job = session.exec(stmt).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    sched_svc.remove_job(job_id)
    session.delete(job)
    session.commit()
    return {"status": "deleted"}


@router.post("/{job_id}/toggle")
def toggle_job(job_id: str, session: Session = Depends(get_session)):
    stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
    job = session.exec(stmt).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    job.enabled = not job.enabled
    session.add(job)
    session.commit()

    if job.enabled:
        sched_svc.add_or_update_job(job)
    else:
        sched_svc.pause_job(job_id)

    return {"job_id": job_id, "enabled": job.enabled}
