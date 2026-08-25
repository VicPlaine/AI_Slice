import shutil
from pathlib import Path


def reset_task_for_retry(task) -> None:
    task.status = "pending"
    task.progress = 0
    task.progress_message = "等待处理..."
    task.error_message = None

    clips = getattr(task, "clips", None)
    if clips is not None:
        clips.clear()


def cleanup_task_outputs(task, storage_dir: str) -> None:
    storage_root = Path(storage_dir).expanduser().resolve()
    clip_dir = storage_root / "clips" / str(task.id)
    shutil.rmtree(clip_dir, ignore_errors=True)


def cleanup_task_storage(task, storage_dir: str) -> None:
    storage_root = Path(storage_dir).expanduser().resolve()
    cleanup_task_outputs(task, storage_dir)

    source_path = getattr(task, "source_path", "")
    if not source_path:
        return

    resolved_source = Path(source_path).expanduser().resolve()
    try:
        resolved_source.relative_to(storage_root)
    except ValueError:
        return

    if resolved_source.is_file():
        resolved_source.unlink(missing_ok=True)
