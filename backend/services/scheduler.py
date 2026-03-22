"""
APScheduler 调度服务
"""
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from backend.database import engine
from backend.models import ScheduleJob

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _scheduled_run(topic: str = "daily_news"):
    """定时触发时执行指定主题的 Pipeline"""
    from backend.services.runner import start_task
    logger.info(f"[Scheduler] 定时任务触发，启动工作流: {topic}")
    start_task(topic=topic)


def _update_job_last_run(job_id: str):
    with Session(engine) as session:
        stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
        job = session.exec(stmt).first()
        if job:
            job.last_run = datetime.utcnow()
            session.add(job)
            session.commit()


def load_jobs_from_db():
    """从数据库恢复所有已启用的定时任务"""
    with Session(engine) as session:
        jobs = session.exec(select(ScheduleJob).where(ScheduleJob.enabled == True)).all()
        for job in jobs:
            _add_job_to_scheduler(job)
    logger.info(f"[Scheduler] 已从数据库恢复 {len(jobs)} 个定时任务")


def _add_job_to_scheduler(job: ScheduleJob):
    try:
        if job.cron_expr:
            trigger = CronTrigger.from_crontab(job.cron_expr, timezone="Asia/Shanghai")
        elif job.interval_hours:
            trigger = IntervalTrigger(hours=job.interval_hours)
        else:
            return

        scheduler.add_job(
            _scheduled_run,
            args=[getattr(job, "topic", "daily_news")], # 从 job 对象获取主题
            trigger=trigger,
            id=job.job_id,
            name=job.name,
            replace_existing=True,
        )
        logger.info(f"[Scheduler] 已添加任务: {job.job_id} ({job.name})")
    except Exception as e:
        logger.error(f"[Scheduler] 添加任务失败 {job.job_id}: {e}")


def add_or_update_job(job: ScheduleJob):
    _add_job_to_scheduler(job)


def remove_job(job_id: str):
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass


def pause_job(job_id: str):
    try:
        scheduler.pause_job(job_id)
    except Exception:
        pass


def resume_job(job_id: str):
    try:
        scheduler.resume_job(job_id)
    except Exception:
        pass


def get_next_run(job_id: str) -> Optional[datetime]:
    try:
        job = scheduler.get_job(job_id)
        if job:
            return job.next_run_time
    except Exception:
        pass
    return None


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("[Scheduler] APScheduler 已启动")
