import logging
import os
from collections.abc import Sequence
from typing import Callable, Protocol

from starlette.concurrency import run_in_threadpool

from app.services.clipper import get_video_duration

logger = logging.getLogger(__name__)


class TaskDurationCarrier(Protocol):
    video_duration: float | None
    source_path: str


async def hydrate_missing_task_durations(
    tasks: Sequence[TaskDurationCarrier],
    probe_duration: Callable[[str], float] = get_video_duration,
    path_exists: Callable[[str], bool] = os.path.exists,
) -> int:
    updated = 0

    for task in tasks:
        if task.video_duration is not None:
            continue
        if not task.source_path or not path_exists(task.source_path):
            continue

        try:
            task.video_duration = await run_in_threadpool(
                probe_duration,
                task.source_path,
            )
            updated += 1
        except Exception as exc:
            logger.warning(
                "Failed to hydrate video duration for %s: %s",
                task.source_path,
                exc,
            )

    return updated
