"""
稿件记录路由
GET /api/records          - 分页列表
GET /api/records/{id}     - 详情（含完整正文、图片路径、日志）
GET /api/records/stats    - 统计数据（供 Dashboard 使用）
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from backend.database import get_session
from backend.models import TaskRecord

router = APIRouter(prefix="/api/records", tags=["records"])


def _format_record_brief(r: TaskRecord) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "mode": r.mode,
        "node_name": r.node_name,
        "status": r.status,
        "xhs_title": r.xhs_title,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "has_images": bool(r.image_paths),
        "error_log": r.error_log,
    }


def _format_record_detail(r: TaskRecord) -> dict:
    d = _format_record_brief(r)
    d.update({
        "xhs_content": r.xhs_content,
        "xhs_tags": json.loads(r.xhs_tags) if r.xhs_tags else [],
        "image_paths": json.loads(r.image_paths) if r.image_paths else [],
        "publish_screenshot": r.publish_screenshot,
        "run_log": r.run_log,
    })
    return d


@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    total = session.exec(select(func.count(TaskRecord.id))).one()
    success = session.exec(
        select(func.count(TaskRecord.id)).where(TaskRecord.status == "success")
    ).one()
    failed = session.exec(
        select(func.count(TaskRecord.id)).where(TaskRecord.status == "failed")
    ).one()
    running = session.exec(
        select(func.count(TaskRecord.id)).where(TaskRecord.status == "running")
    ).one()
    return {"total": total, "success": success, "failed": failed, "running": running}


@router.get("")
def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(TaskRecord).order_by(TaskRecord.id.desc())
    if status:
        stmt = stmt.where(TaskRecord.status == status)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    records = session.exec(stmt).all()
    return [_format_record_brief(r) for r in records]


@router.get("/{record_id}")
def get_record(record_id: int, session: Session = Depends(get_session)):
    r = session.get(TaskRecord, record_id)
    if not r:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="记录不存在")
    return _format_record_detail(r)
