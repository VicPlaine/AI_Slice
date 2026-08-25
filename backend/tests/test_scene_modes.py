from pydantic import ValidationError

from app.models.schemas import TaskCreate
from app.services.analyzer import get_scene_config


def _task(scene_mode: str) -> TaskCreate:
    return TaskCreate(
        video_path="./storage/uploads/test.mp3",
        video_filename="test.mp4",
        scene_mode=scene_mode,
    )


def test_podcast_scene_uses_dedicated_prompt() -> None:
    scene = get_scene_config("podcast")
    assert scene.name == "podcast"
    assert scene.label == "播客访谈"
    assert "观点洞察" in scene.prompt_template


def test_legacy_interview_scene_is_normalized_to_podcast() -> None:
    assert get_scene_config("interview").name == "podcast"
    assert _task("interview").scene_mode == "podcast"


def test_unknown_scene_is_rejected_at_api_boundary() -> None:
    try:
        _task("unknown")
    except ValidationError:
        return
    raise AssertionError("unknown scene_mode should be rejected")
