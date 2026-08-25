"""Database-backed in-process task runner.

并发模型：单 uvicorn 进程内启动 N 个 asyncio 协程作为 worker，并发处理 pending 任务。
N 由 settings.worker_concurrency 控制。
所有 worker 共享一把 asyncio.Lock 来串行化"抢任务"那一步（select+update+commit），
避免多个 worker 同时把同一行 pending 改成 downloading。
因为 asyncio 是单线程协作式调度，asyncio.Lock 在单进程内就足够，
不需要 PostgreSQL FOR UPDATE 行锁。
"""

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.db import async_session
from app.models.database import Task, TaskStatus
from app.workers.pipeline import run_video_pipeline

logger = logging.getLogger(__name__)

_runner_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None
_claim_lock: asyncio.Lock | None = None
_active_pipeline_tasks: dict[str, asyncio.Task] = {}


async def start_task_runner() -> None:
    """Start the process-local pending task scanner pool."""
    global _runner_tasks, _stop_event, _claim_lock

    # 已经在跑就直接返回（防止重复启动）
    if _runner_tasks and any(not t.done() for t in _runner_tasks):
        return

    await _reset_interrupted_tasks()

    _stop_event = asyncio.Event()
    _claim_lock = asyncio.Lock()

    concurrency = max(1, int(settings.worker_concurrency))
    _runner_tasks = [
        asyncio.create_task(_task_runner_loop(worker_id, _stop_event))
        for worker_id in range(concurrency)
    ]
    logger.info("Started %d task runner worker(s)", concurrency)


async def stop_task_runner() -> None:
    """Stop all worker coroutines."""
    if not _runner_tasks or not _stop_event:
        return

    _stop_event.set()
    for pipeline_task in list(_active_pipeline_tasks.values()):
        pipeline_task.cancel()
    await asyncio.gather(*_runner_tasks, return_exceptions=True)
    logger.info("Stopped %d task runner worker(s)", len(_runner_tasks))


async def _task_runner_loop(worker_id: int, stop_event: asyncio.Event) -> None:
    logger.info("Worker #%d started", worker_id)
    while not stop_event.is_set():
        task_id = await _claim_next_pending_task(worker_id)
        if task_id:
            pipeline_task = asyncio.create_task(run_video_pipeline(task_id))
            _active_pipeline_tasks[task_id] = pipeline_task
            try:
                await pipeline_task
            except asyncio.CancelledError:
                logger.info("Worker #%d: task %s was canceled", worker_id, task_id)
            except Exception:
                logger.exception(
                    "Worker #%d: pipeline failed for task %s", worker_id, task_id
                )
            finally:
                _active_pipeline_tasks.pop(task_id, None)
            continue

        # 没单可接就等 1 秒再扫；stop 信号到了立刻醒
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass

    logger.info("Worker #%d stopped", worker_id)


def cancel_running_task(task_id: str) -> bool:
    """Cancel an active pipeline without stopping its worker loop."""
    pipeline_task = _active_pipeline_tasks.get(task_id)
    if not pipeline_task or pipeline_task.done():
        return False
    pipeline_task.cancel()
    return True


async def _claim_next_pending_task(worker_id: int) -> str | None:
    """原子地拿走一条 pending 任务。

    用 _claim_lock 保证同一时刻只有一个 worker 在做 select→update→commit，
    其他 worker 想抢的时候会在 lock 这里挂起，等当前抢任务的 worker commit 完
    再轮到它们，所以不会有两个 worker 拿到同一行。
    """
    assert _claim_lock is not None, "task runner not started"

    async with _claim_lock:
        async with async_session() as db:
            result = await db.execute(
                select(Task)
                .where(Task.status == TaskStatus.pending.value)
                .order_by(Task.created_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()
            if not task:
                return None

            task.status = TaskStatus.downloading.value
            task.progress = 0
            task.progress_message = "正在排队处理..."
            await db.commit()

            logger.info("Worker #%d claimed task: %s", worker_id, task.id)
            return str(task.id)


async def _reset_interrupted_tasks() -> None:
    """Return interrupted in-progress tasks to pending on process startup."""
    in_progress_statuses = [
        TaskStatus.downloading.value,
        TaskStatus.transcribing.value,
        TaskStatus.analyzing.value,
        TaskStatus.clipping.value,
        TaskStatus.uploading.value,
    ]

    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.status.in_(in_progress_statuses)))
        tasks = result.scalars().all()
        for task in tasks:
            task.status = TaskStatus.pending.value
            task.progress = 0
            task.progress_message = "等待处理..."

        if tasks:
            await db.commit()
            logger.info("Reset %s interrupted task(s) to pending", len(tasks))
