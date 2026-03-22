"""
SQLModel 数据模型定义
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class TaskRecord(SQLModel, table=True):
    """每次 Pipeline 运行的完整记录"""
    __tablename__ = "task_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)          # UUID
    mode: str = Field(default="full")          # full / node_test
    node_name: Optional[str] = None            # 单节点测试时使用
    status: str = Field(default="pending")     # pending / running / success / failed
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    # 内容
    xhs_title: Optional[str] = None
    xhs_content: Optional[str] = None
    xhs_tags: Optional[str] = None            # JSON 数组字符串
    image_paths: Optional[str] = None         # JSON 数组字符串
    publish_screenshot: Optional[str] = None

    # 日志
    error_log: Optional[str] = None
    run_log: Optional[str] = None             # 完整日志文本


class RssSource(SQLModel, table=True):
    """RSS 数据源配置"""
    __tablename__ = "rss_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str = Field(default="综合资讯")
    url: str
    description: str = Field(default="")
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduleJob(SQLModel, table=True):
    """定时任务配置"""
    __tablename__ = "schedule_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    name: str
    cron_expr: Optional[str] = None           # Cron 表达式 e.g. "0 8 * * *"
    interval_hours: Optional[float] = None    # 或间隔小时数
    topic: str = Field(default="daily_news")  # daily_news / reddit_hot
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
