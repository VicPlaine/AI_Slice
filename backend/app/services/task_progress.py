from datetime import datetime

from sqlalchemy import func, select

from app.models.database import Task, TaskStatus


async def update_task_progress(
    db,
    task,
    progress: int,
    message: str,
    status: str | None = None,
    *,
    persist: bool = True,
) -> None:
    """更新任务进度；PostgreSQL 是唯一状态源。"""
    task.progress = progress
    task.progress_message = message[:200]
    if status:
        task.status = status

    if persist:
        await db.commit()


async def get_queue_position(db, task_status: str, task_created_at: datetime) -> int | None:
    """计算 pending 任务前面还排着几个人。

    仅当 task_status == 'pending' 时返回有意义的值：
    返回比当前任务更早创建（created_at 更小）且仍是 pending 的任务数。
    0 表示"我就是下一个被 worker 接走的"。

    非 pending 状态直接返回 None，前端用来判断要不要展示"排队中"提示。
    """
    if task_status != TaskStatus.pending.value:
        return None

    result = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.status == TaskStatus.pending.value)
        .where(Task.created_at < task_created_at)
    )
    return int(result.scalar_one() or 0)
