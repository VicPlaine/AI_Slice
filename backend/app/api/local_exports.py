"""Large local video export API using native FFmpeg on localhost."""

from pathlib import Path
import shutil
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.db import get_db
from app.models import Task
from app.services.local_export import (
    cancel_local_export,
    cleanup_local_export,
    create_job_directory,
    get_local_export,
    get_local_export_archive,
    start_local_export,
)

router = APIRouter(prefix="/api/local-exports", tags=["local-exports"])


@router.post("/tasks/{task_id}")
async def create_local_export(
    task_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).options(selectinload(Task.clips)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "done" or not task.clips:
        raise HTTPException(status_code=400, detail="任务尚未生成可导出的切片方案")
    if not file.filename:
        raise HTTPException(status_code=400, detail="视频文件名为空")

    job_id = str(uuid4())
    job_dir = create_job_directory(job_id)
    suffix = Path(file.filename).suffix.lower() or ".mp4"
    source_path = job_dir / f"source{suffix}"

    try:
        with source_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                await run_in_threadpool(target.write, chunk)
    except Exception as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"本机视频接收失败: {error}") from error

    offset = task.video_start_offset if task.video_start_offset > 1 else 0
    clips = [
        {
            "clip_index": clip.clip_index,
            "title": clip.title,
            "start_time": max(0, clip.start_time - offset),
            "duration": max(0, clip.end_time - offset) - max(0, clip.start_time - offset),
        }
        for clip in task.clips
        if clip.end_time > clip.start_time
    ]
    start_local_export(job_id, source_path, task.video_filename, clips)
    return {"job_id": job_id}


@router.get("/{job_id}")
async def local_export_status(job_id: UUID):
    job = get_local_export(str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="导出任务不存在或已清理")
    if job["status"] == "done":
        job["download_url"] = f"/api/local-exports/{job_id}/download"
    return job


@router.get("/{job_id}/download")
async def download_local_export(job_id: UUID):
    archive = get_local_export_archive(str(job_id))
    if not archive:
        raise HTTPException(status_code=404, detail="导出文件尚未就绪")
    archive_path, archive_name = archive
    if not archive_path.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=archive_name,
        background=BackgroundTask(cleanup_local_export, str(job_id)),
    )


@router.delete("/{job_id}")
async def stop_local_export(job_id: UUID):
    if not cancel_local_export(str(job_id)):
        raise HTTPException(status_code=400, detail="导出任务无法取消或已经结束")
    return {"message": "正在取消本机切片"}
