"""FFmpeg 视频处理：音频提取 + 视频切片"""

import logging
import os
import subprocess

from app.services.ffmpeg_tools import require_command

logger = logging.getLogger(__name__)


def extract_audio(video_path: str, audio_path: str) -> str:
    """从视频中提取音频（16kHz mono MP3，体积小适合上传 ASR）"""
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    ffmpeg_bin = require_command("ffmpeg", "extract audio from video")
    cmd = [
        ffmpeg_bin, "-y",
        "-i", video_path,
        "-vn",                  # 去掉视频流
        "-acodec", "libmp3lame",# MP3 编码（比 WAV 小 10 倍）
        "-ar", "16000",         # 16kHz 采样率
        "-ac", "1",             # 单声道
        "-b:a", "64k",          # 64kbps 码率（语音足够）
        audio_path,
    ]
    logger.info(f"Extracting audio: {video_path} → {audio_path}")
    subprocess.run(cmd, check=True, capture_output=True)
    file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
    logger.info(f"Audio extracted: {audio_path} ({file_size_mb:.1f} MB)")
    return audio_path


def clip_video(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
) -> str:
    """FFmpeg 精确切片（重编码确保关键帧对齐）"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    start_str = _seconds_to_ffmpeg_time(start_time)
    end_str = _seconds_to_ffmpeg_time(end_time)
    ffmpeg_bin = require_command("ffmpeg", "clip video segments")

    cmd = [
        ffmpeg_bin, "-y",
        "-i", video_path,
        "-ss", start_str,
        "-to", end_str,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        output_path,
    ]
    logger.info(f"Clipping: {start_str} → {end_str} → {output_path}")
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def batch_clip(
    video_path: str,
    clips: list[dict],
    output_dir: str,
) -> list[str]:
    """批量切片，返回输出文件路径列表"""
    os.makedirs(output_dir, exist_ok=True)
    outputs = []

    for clip in clips:
        # 文件名：序号_标题（截取前 20 字符）
        safe_title = "".join(
            c for c in clip.get("title", "clip")[:20]
            if c.isalnum() or c in ("_", "-", " ")
        ).strip()
        filename = f"clip_{clip['clip_id']:03d}_{safe_title}.mp4"
        output_path = os.path.join(output_dir, filename)

        try:
            clip_video(
                video_path,
                clip["start_time"],
                clip["end_time"],
                output_path,
            )
            outputs.append(output_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clip {clip['clip_id']}: {e}")
            continue

    logger.info(f"Batch clipping done: {len(outputs)}/{len(clips)} succeeded")
    return outputs


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    # 前置校验：文件必须存在且非空
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        raise ValueError(f"视频文件为空 (0 bytes): {video_path}")
    logger.info(f"Probing video: {video_path} ({file_size / 1024 / 1024:.1f} MB)")
    ffprobe_bin = require_command("ffprobe", "probe media duration")

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "(无 stderr 输出)"
        raise RuntimeError(
            f"ffprobe 无法读取视频文件 ({file_size / 1024 / 1024:.1f} MB): {stderr}"
        )
    duration_str = result.stdout.strip()
    if not duration_str:
        raise RuntimeError(f"ffprobe 未返回时长信息，文件可能损坏: {video_path}")
    return float(duration_str)


def _seconds_to_ffmpeg_time(seconds: float) -> str:
    """秒数转 FFmpeg 时间格式 HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
