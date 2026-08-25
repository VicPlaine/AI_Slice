from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── Request Schemas ──


class TaskCreate(BaseModel):
    """创建任务请求"""

    video_path: str  # 本地存储路径
    video_filename: str
    video_start_offset: float = 0.0  # 视频 PTS 偏移（秒），OBS 分段录制时非 0
    video_duration: float | None = None  # 原视频时长（秒）
    scene_mode: str = "livestream"  # 场景模式：livestream / podcast / lecture

    @field_validator("scene_mode", mode="before")
    @classmethod
    def validate_scene_mode(cls, value: str | None) -> str:
        # 旧前端或历史请求中的 interview 自动迁移为 podcast。
        normalized = "podcast" if value == "interview" else (value or "livestream")
        if normalized not in {"livestream", "podcast", "lecture"}:
            raise ValueError("scene_mode 必须是 livestream、podcast 或 lecture")
        return normalized


class TaskRename(BaseModel):
    """重命名任务请求"""

    video_filename: str


class ClipTitleUpdate(BaseModel):
    """Replace a clip title with a selected recommendation."""

    title: str


class ClipCaptionUpdate(BaseModel):
    """Replace the selected publishing caption."""

    caption: str


# ── Response Schemas ──


class ClipResponse(BaseModel):
    """切片详情响应"""

    id: UUID
    clip_index: int
    title: str
    summary: str
    clip_type: str
    start_time: float
    end_time: float
    duration: float
    virality_score: int
    suggested_caption: str
    file_key: str | None = None
    download_url: str | None = None
    viral_titles: list[str] | None = None
    editing_guide: dict | None = None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """任务详情响应（含切片列表）"""

    id: UUID
    status: str
    video_filename: str
    source_path: str = ""  # 本地存储路径（用于剪映导出时引用）
    video_duration: float | None = None
    scene_mode: str = "livestream"
    video_start_offset: float = 0.0
    progress: int
    progress_message: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    clips: list[ClipResponse] = []

    model_config = {"from_attributes": True}


class TaskListItem(BaseModel):
    """任务列表项（不含切片）"""

    id: UUID
    status: str
    video_filename: str
    video_duration: float | None = None
    scene_mode: str = "livestream"
    progress: int
    progress_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProgressEvent(BaseModel):
    """SSE 进度事件"""

    progress: int
    message: str
    status: str
    # 仅当 status == 'pending' 时有意义：表示前面还有多少个更早的 pending 任务
    # 0 = 下一个就轮到我；None = 任务已开跑，不需要排队信息
    queue_position: int | None = None


class ViralTitlesResponse(BaseModel):
    """爆款标题推荐响应"""

    clip_id: str
    viral_titles: list[str]


class EditingGuideResponse(BaseModel):
    """剪辑思路响应"""

    clip_id: str
    editing_guide: dict
