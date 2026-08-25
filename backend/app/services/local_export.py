"""Native FFmpeg export jobs for videos too large for FFmpeg.wasm memory."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.ffmpeg_tools import require_command

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _safe_name(value: str, fallback: str) -> str:
    cleaned = "".join(
        character if character not in '/\\:*?"<>|' else "_" for character in value
    ).strip()
    return (cleaned[:80] or fallback)


def get_local_export_root() -> Path:
    root = Path(settings.storage_dir).resolve() / "local_exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_job_directory(job_id: str) -> Path:
    job_dir = get_local_export_root() / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def start_local_export(
    job_id: str,
    source_path: Path,
    task_filename: str,
    clips: list[dict[str, Any]],
) -> None:
    job_dir = source_path.parent
    archive_name = f"{_safe_name(Path(task_filename).stem, '视频')}_切片.zip"
    archive_path = job_dir / archive_name
    cancel_event = threading.Event()
    job = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "视频已传到本机，等待 FFmpeg 处理",
        "current_clip": 0,
        "total_clips": len(clips),
        "archive_name": archive_name,
        "archive_path": str(archive_path),
        "source_path": str(source_path),
        "cancel_event": cancel_event,
    }
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_export,
        args=(job_id, source_path, archive_path, clips, cancel_event),
        daemon=True,
        name=f"local-export-{job_id[:8]}",
    )
    thread.start()


def _update_job(job_id: str, **values: Any) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job.update(values)


def _run_ffmpeg(command: list[str], cancel_event: threading.Event) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    while process.poll() is None:
        if cancel_event.wait(0.2):
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            raise InterruptedError("导出已取消")

    _, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError((stderr or f"FFmpeg exit code {process.returncode}")[-800:])


def _run_export(
    job_id: str,
    source_path: Path,
    archive_path: Path,
    clips: list[dict[str, Any]],
    cancel_event: threading.Event,
) -> None:
    created_clips: list[tuple[Path, str]] = []
    completed = False
    try:
        ffmpeg = require_command("ffmpeg", "export large local video clips")
        _update_job(job_id, status="clipping", message="本机 FFmpeg 正在生成切片")
        for index, clip in enumerate(clips, start=1):
            if cancel_event.is_set():
                raise InterruptedError("导出已取消")

            output_name = (
                f"{int(clip['clip_index']):02d}_"
                f"{_safe_name(str(clip.get('title') or ''), '未命名片段')}.mp4"
            )
            output_path = source_path.parent / output_name
            _update_job(
                job_id,
                current_clip=index,
                progress=round((index - 1) / max(1, len(clips)) * 85),
                message=f"本机 FFmpeg 正在切片 {index}/{len(clips)}",
            )
            _run_ffmpeg(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{float(clip['start_time']):.3f}",
                    "-i",
                    str(source_path),
                    "-t",
                    f"{float(clip['duration']):.3f}",
                    "-c",
                    "copy",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-y",
                    str(output_path),
                ],
                cancel_event,
            )
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"切片 {index} 未生成有效文件")
            created_clips.append((output_path, output_name))

        _update_job(job_id, status="zipping", progress=90, message="正在打包 ZIP")
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True
        ) as archive:
            for output_path, output_name in created_clips:
                if cancel_event.is_set():
                    raise InterruptedError("导出已取消")
                archive.write(output_path, arcname=output_name)
                output_path.unlink(missing_ok=True)

        _update_job(
            job_id,
            status="done",
            progress=100,
            message="切片完成，准备下载",
            current_clip=len(clips),
        )
        completed = True
    except InterruptedError:
        _update_job(job_id, status="canceled", message="本机切片已取消")
    except Exception as error:
        _update_job(job_id, status="failed", message=f"本机切片失败: {error}")
    finally:
        for output_path, _ in created_clips:
            output_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)
        if not completed:
            shutil.rmtree(source_path.parent, ignore_errors=True)


def get_local_export(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return {
            key: value
            for key, value in job.items()
            if key not in {"archive_path", "source_path", "cancel_event"}
        }


def get_local_export_archive(job_id: str) -> tuple[Path, str] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "done":
            return None
        return Path(job["archive_path"]), str(job["archive_name"])


def cancel_local_export(job_id: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job["status"] in {"done", "failed", "canceled"}:
            return False
        job["cancel_event"].set()
        job["status"] = "canceling"
        job["message"] = "正在停止本机 FFmpeg"
        return True


def cleanup_local_export(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.pop(job_id, None)
    if not job:
        return
    job_dir = Path(job["archive_path"]).parent
    shutil.rmtree(job_dir, ignore_errors=True)


def cleanup_stale_local_exports(max_age_seconds: int = 24 * 3600) -> None:
    cutoff = time.time() - max_age_seconds
    for path in get_local_export_root().iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)
