"""上传接口：支持视频直传和浏览器端提取后的音频上传"""

import logging
import os
import time

from fastapi import APIRouter, HTTPException, UploadFile, File
from starlette.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(settings.storage_dir, "uploads")


@router.post("/video")
async def upload_video(file: UploadFile = File(...)):
    """接收视频文件，流式写入本地存储，返回存储路径"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 安全化文件名
    safe_name = "".join(
        c for c in file.filename if c.isalnum() or c in ("_", "-", ".", " ")
    ).strip()
    timestamp = int(time.time() * 1000)
    stored_name = f"{timestamp}_{safe_name}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 流式写入（支持 GB 级大文件，不会撑爆内存）
    total_bytes = 0
    try:
        with open(stored_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await run_in_threadpool(f.write, chunk)
                total_bytes += len(chunk)
    except Exception as e:
        # 清理半成品
        if os.path.exists(stored_path):
            os.remove(stored_path)
        logger.exception(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件写入失败: {str(e)}")

    logger.info(f"Video uploaded: {stored_name} ({total_bytes / 1024 / 1024:.1f} MB)")

    return {
        "video_path": stored_path,
        "video_filename": file.filename,
        "size_bytes": total_bytes,
    }


@router.post("/audio")
async def upload_audio(file: UploadFile = File(...)):
    """接收浏览器端提取的音频文件（MP3），流式写入本地存储"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 校验文件类型
    if not file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
        raise HTTPException(status_code=400, detail="仅支持 MP3/WAV/M4A/OGG 音频格式")

    # 安全化文件名
    safe_name = "".join(
        c for c in file.filename if c.isalnum() or c in ("_", "-", ".", " ")
    ).strip()
    timestamp = int(time.time() * 1000)
    stored_name = f"{timestamp}_{safe_name}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 流式写入
    total_bytes = 0
    try:
        with open(stored_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await run_in_threadpool(f.write, chunk)
                total_bytes += len(chunk)
    except Exception as e:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        logger.exception(f"音频上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件写入失败: {str(e)}")

    logger.info(f"Audio uploaded: {stored_name} ({total_bytes / 1024 / 1024:.1f} MB)")

    return {
        "audio_path": stored_path,
        "original_filename": file.filename,
        "size_bytes": total_bytes,
    }
