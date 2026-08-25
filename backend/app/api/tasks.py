"""任务管理接口：创建、列表、详情、SSE 进度"""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import async_session
from app.db import get_db
from app.models import Task, TaskCreate, TaskListItem, TaskRename, TaskResponse, TaskStatus
from app.services.task_duration import hydrate_missing_task_durations
from app.services.task_lifecycle import (
    cleanup_task_outputs,
    cleanup_task_storage,
    reset_task_for_retry,
)
from app.services.task_progress import get_queue_position
from app.services.task_runner import cancel_running_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)


@router.post("", response_model=TaskResponse)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建处理任务；后台 runner 会扫描 pending 任务并执行。"""
    task = Task(
        source_path=data.video_path,
        video_filename=data.video_filename,
        video_start_offset=data.video_start_offset,
        video_duration=data.video_duration,
        scene_mode=data.scene_mode,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 新建任务不会有 clips，手动构建避免异步懒加载
    return TaskResponse(
        id=task.id,
        status=task.status.value if hasattr(task.status, 'value') else task.status,
        video_filename=task.video_filename,
        video_duration=task.video_duration,
        progress=task.progress,
        progress_message=task.progress_message,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        clips=[],
    )


@router.get("", response_model=list[TaskListItem])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    """获取所有任务列表"""
    result = await db.execute(
        select(Task).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()

    updated = await hydrate_missing_task_durations(tasks)
    if updated:
        await db.commit()

    return [TaskListItem.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """获取任务详情（含切片列表，切片带本地下载 URL）"""
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_resp = TaskResponse.model_validate(task)
    # 为每个 clip 填充下载 URL（指向本地文件服务 API）
    for clip_resp in task_resp.clips:
        if clip_resp.file_key:
            clip_resp.download_url = f"/api/clips/{clip_resp.id}/download"
    return task_resp



@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """重试失败的任务（重置为 pending，等待后台 runner 执行）"""
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("pending", "failed", "canceled", "done"):
        raise HTTPException(status_code=400, detail="只能重试等待中、失败、已取消或已完成的任务")

    # 重置任务状态并清理旧切片结果，避免重试后重复记录
    reset_task_for_retry(task)
    try:
        cleanup_task_outputs(task, settings.storage_dir)
    except Exception:
        logger.exception("清理任务旧切片输出失败: %s", task_id)
    await db.commit()

    return TaskResponse.model_validate(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """停止尚未完成的 ASR/LLM 流水线，并保留任务记录供后续重试。"""
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("done", "failed", "canceled"):
        raise HTTPException(status_code=400, detail="当前任务已经结束，无需取消")

    task.status = TaskStatus.canceled.value
    task.progress_message = "任务已取消，后续转录和内容分析已停止"
    task.error_message = None
    await db.commit()
    cancel_running_task(str(task_id))
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}/rename", response_model=TaskResponse)
async def rename_task(task_id: UUID, data: TaskRename, db: AsyncSession = Depends(get_db)):
    """重命名任务名称（标题）"""
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task.video_filename = data.video_filename
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """删除任务及关联的切片数据"""
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    cancel_running_task(str(task_id))

    try:
        cleanup_task_storage(task, settings.storage_dir)
    except Exception:
        logger.exception("清理任务本地存储失败: %s", task_id)

    await db.delete(task)
    await db.commit()
    return {"message": "任务删除成功", "id": str(task_id)}


@router.get("/{task_id}/progress")
async def task_progress_sse(task_id: UUID):
    """SSE 实时进度推送：从数据库读取后台任务写入的进度。"""

    async def event_stream():
        while True:
            async with async_session() as db:
                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()

                if task:
                    status = (
                        task.status.value if hasattr(task.status, "value") else task.status
                    )
                    queue_position = await get_queue_position(
                        db, status, task.created_at
                    )
                    event = {
                        "progress": task.progress,
                        "message": task.progress_message or "",
                        "status": status,
                        "queue_position": queue_position,
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # 任务完成或失败时结束 SSE
                    if event["status"] in ("done", "failed", "canceled"):
                        break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
