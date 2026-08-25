import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    downloading = "downloading"
    transcribing = "transcribing"
    analyzing = "analyzing"
    clipping = "clipping"
    uploading = "uploading"
    canceled = "canceled"
    done = "done"
    failed = "failed"


class Task(Base):
    """处理任务：一个直播视频对应一个 Task"""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.pending.value)
    scene_mode: Mapped[str] = mapped_column(String(30), default="livestream", server_default="livestream")
    video_filename: Mapped[str] = mapped_column(String(500))
    source_path: Mapped[str] = mapped_column(String(500))
    video_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    video_start_offset: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str] = mapped_column(String(200), default="等待处理")
    transcript_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    clips: Mapped[list["Clip"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class Clip(Base):
    """切片结果：一个 Task 可以有多个 Clip"""

    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    clip_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    clip_type: Mapped[str] = mapped_column(String(50))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    duration: Mapped[float] = mapped_column(Float)
    virality_score: Mapped[int] = mapped_column(Integer)
    suggested_caption: Mapped[str] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    viral_titles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    editing_guide: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="clips")
