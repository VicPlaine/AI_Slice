"""切片结果接口：列表、下载"""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Clip, ClipCaptionUpdate, ClipResponse, ClipTitleUpdate

router = APIRouter(prefix="/api", tags=["clips"])


@router.get("/tasks/{task_id}/clips", response_model=list[ClipResponse])
async def list_clips(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """获取指定任务的切片列表"""
    result = await db.execute(
        select(Clip).where(Clip.task_id == task_id).order_by(Clip.clip_index)
    )
    clips = result.scalars().all()

    clip_responses = []
    for clip in clips:
        resp = ClipResponse.model_validate(clip)
        if clip.file_key:
            resp.download_url = f"/api/clips/{clip.id}/download"
        clip_responses.append(resp)

    return clip_responses


@router.get("/clips/{clip_id}/download")
async def download_clip(clip_id: UUID, db: AsyncSession = Depends(get_db)):
    """从本地存储下载切片文件"""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")
    if not clip.file_key:
        raise HTTPException(status_code=404, detail="切片文件尚未生成")

    # file_key 存的是本地相对路径 clips/{task_id}/filename.mp4
    file_path = os.path.join(settings.storage_dir, clip.file_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"切片文件不存在: {clip.file_key}")

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=os.path.basename(file_path),
    )


@router.patch("/clips/{clip_id}/title")
async def replace_clip_title(
    clip_id: UUID,
    data: ClipTitleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Persist a selected recommended title as the clip's primary title."""
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="标题不能超过 200 个字符")

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")

    clip.title = title
    await db.commit()
    return {"clip_id": str(clip_id), "title": title}


@router.post("/clips/{clip_id}/viral-titles")
async def generate_viral_titles(clip_id: UUID, db: AsyncSession = Depends(get_db)):
    """为指定切片生成 5 个抖音风格爆款标题（每次调用覆盖旧结果）"""
    from app.services.viral_title_generator import ViralTitleGenerator
    from app.models import ViralTitlesResponse

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")

    # 构建上下文
    clip_context = {
        "title": clip.title,
        "summary": clip.summary,
        "clip_type": clip.clip_type,
        "suggested_caption": clip.suggested_caption,
    }

    generator = ViralTitleGenerator()
    titles = await generator.generate(clip_context)

    # 持久化到数据库
    clip.viral_titles = titles
    await db.commit()

    return ViralTitlesResponse(
        clip_id=str(clip_id),
        viral_titles=titles,
    )


@router.post("/clips/{clip_id}/caption-suggestions")
async def generate_caption_suggestions(
    clip_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate three alternative publishing captions without replacing the current one."""
    from app.services.caption_generator import CaptionGenerator

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")

    captions = await CaptionGenerator().generate(
        {
            "title": clip.title,
            "summary": clip.summary,
            "clip_type": clip.clip_type,
            "suggested_caption": clip.suggested_caption,
        }
    )
    return {"clip_id": str(clip_id), "captions": captions}


@router.patch("/clips/{clip_id}/caption")
async def replace_clip_caption(
    clip_id: UUID,
    data: ClipCaptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Persist a selected generated caption."""
    caption = data.caption.strip()
    if not caption:
        raise HTTPException(status_code=400, detail="发布文案不能为空")
    if len(caption) > 1000:
        raise HTTPException(status_code=400, detail="发布文案不能超过 1000 个字符")

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")
    clip.suggested_caption = caption
    await db.commit()
    return {"clip_id": str(clip_id), "caption": caption}


@router.post("/clips/{clip_id}/editing-guide")
async def generate_editing_guide(clip_id: UUID, db: AsyncSession = Depends(get_db)):
    """为指定切片生成结构化剪辑思路（每次调用覆盖旧结果）"""
    from app.services.editing_guide_generator import EditingGuideGenerator
    from app.models import EditingGuideResponse

    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="切片不存在")

    # 构建上下文
    clip_context = {
        "title": clip.title,
        "summary": clip.summary,
        "clip_type": clip.clip_type,
        "duration": clip.duration,
        "virality_score": clip.virality_score,
    }

    generator = EditingGuideGenerator()
    guide = await generator.generate(clip_context)

    # 持久化到数据库
    clip.editing_guide = guide
    await db.commit()

    return EditingGuideResponse(
        clip_id=str(clip_id),
        editing_guide=guide,
    )
