"""
Pipeline 运行器服务
负责在后台线程中执行 LangGraph graph，实时日志收集，任务状态管理
"""
import json
import logging
import queue
import threading
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from backend.database import engine
from backend.models import TaskRecord

# 全局：每个 task_id 对应一个日志队列
_log_queues: dict[str, queue.Queue] = {}
_log_queues_lock = threading.Lock()

logger = logging.getLogger(__name__)


class TaskLogHandler(logging.Handler):
    """自定义 logging Handler，将日志写入指定队列"""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        try:
            self.q.put_nowait(msg)
        except queue.Full:
            pass


def _get_initial_state() -> dict:
    return {
        "raw_articles": [],
        "scored_articles": [],
        "premium_articles": [],
        "deduped_events": [],
        "master_summary": "",
        "images": [],
        "xhs_post": {},
        "card_data_list": [],
        "reddit_submission": None,
        "error_log": None,
    }


def _run_pipeline(task_id: str, topic: str, sources_override: Optional[list]):
    """在子线程中执行 pipeline，根据 topic 自动分发到对应的任务图"""
    log_q = _log_queues.get(task_id)

    # 临时拦截所有 root logger 输出到队列
    handler = TaskLogHandler(log_q) if log_q else None
    if handler:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        # 强制推入初始日志，确保前端立即有显示
        log_q.put_nowait("🚀 [Runner] 任务引擎已就绪，正在初始化全链路 Pipeline...")

    collected_logs = []
    original_emit = handler.emit if handler else None

    def capturing_emit(record):
        msg = handler.format(record)
        collected_logs.append(msg)
        try:
            log_q.put_nowait(msg)
        except Exception:
            pass

    if handler:
        handler.emit = capturing_emit

    try:
        # 动态根据业务类型选择入口图
        if topic == "reddit_hot":
            from src.reddit_graph import reddit_app
            logger.info("  🚀 启动：【Reddit热议】全链路发布流程")
            final_state = reddit_app.invoke(_get_initial_state())
        else:
            from src.graph import app
            logger.info(f"  🚀 启动：【每日AI资讯】全链路发布流程 (Task: {task_id})")
            final_state = app.invoke(_get_initial_state())

        xhs_post = final_state.get("xhs_post", {})
        images = final_state.get("images", [])
        error = final_state.get("error_log")

        with Session(engine) as session:
            record = session.get(TaskRecord, None)
            # 按 task_id 查找
            from sqlmodel import select
            stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
            record = session.exec(stmt).first()
            if record:
                record.status = "failed" if error else "success"
                record.finished_at = datetime.utcnow()
                record.xhs_title = xhs_post.get("title", "")
                record.xhs_content = xhs_post.get("content", "")
                record.xhs_tags = json.dumps(xhs_post.get("tags", []), ensure_ascii=False)
                record.image_paths = json.dumps(images, ensure_ascii=False)
                record.error_log = str(error) if error else None
                record.run_log = "\n".join(collected_logs)
                session.add(record)
                session.commit()

    except Exception as e:
        logger.error(f"[Runner] Pipeline 执行异常: {e}", exc_info=True)
        with Session(engine) as session:
            from sqlmodel import select
            stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
            record = session.exec(stmt).first()
            if record:
                record.status = "failed"
                record.finished_at = datetime.utcnow()
                record.error_log = str(e)
                record.run_log = "\n".join(collected_logs)
                session.add(record)
                session.commit()
    finally:
        if handler:
            logging.getLogger().removeHandler(handler)
        # 向队列发送结束标记
        if log_q:
            log_q.put_nowait("__END__")
        # 延迟清理队列
        threading.Timer(300, lambda: _log_queues.pop(task_id, None)).start()


def start_task(topic: str = "daily_news", sources_override: Optional[list] = None) -> str:
    """
    启动一个新的发布任务：
    topic: 'daily_news' (每日AI资讯) | 'reddit_hot' (Reddit热议)
    """
    task_id = str(uuid.uuid4())

    # 创建日志队列
    log_q: queue.Queue = queue.Queue(maxsize=2000)
    with _log_queues_lock:
        _log_queues[task_id] = log_q

    # 写入初始记录
    with Session(engine) as session:
        record = TaskRecord(
            task_id=task_id,
            mode=topic, # 这里借用 mode 字段存储业务模式名
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()

    # 启动子线程
    t = threading.Thread(
        target=_run_pipeline,
        args=(task_id, topic, sources_override),
        daemon=True,
    )
    t.start()

    return task_id


def get_log_queue(task_id: str) -> Optional[queue.Queue]:
    return _log_queues.get(task_id)
