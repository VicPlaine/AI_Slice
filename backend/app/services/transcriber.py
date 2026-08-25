"""Speech transcription services — DashScope Qwen ASR and Groq fallback."""

import asyncio
import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

import dashscope
import httpx
from dashscope.utils.oss_utils import OssUtils

from app.config import settings
from app.services.ffmpeg_tools import require_command

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], Awaitable[None]]

def _get_audio_duration(audio_path: str) -> float:
    """Read audio duration in seconds via ffprobe."""
    ffprobe_bin = require_command("ffprobe", "detect audio duration")
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed to read audio duration: {result.stderr}")
    return float(result.stdout.strip())


def _split_audio(
    audio_path: str,
    chunk_seconds: int,
    known_duration: float | None = None,
) -> list[tuple[str, float]]:
    """
    Split long audio into multiple chunks.

    Returns:
        [(chunk_path, offset_seconds), ...]
    """
    duration = known_duration if known_duration and known_duration > 0 else _get_audio_duration(audio_path)
    if duration <= chunk_seconds:
        return [(audio_path, 0.0)]

    ffmpeg_bin = require_command(
        "ffmpeg",
        "split audio for cloud ASR",
    )

    base, ext = os.path.splitext(audio_path)
    chunks: list[tuple[str, float]] = []
    start = 0.0

    while start < duration:
        chunk_idx = len(chunks)
        chunk_path = f"{base}_chunk{chunk_idx:03d}{ext}"
        end = min(start + chunk_seconds, duration)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            audio_path,
            "-c",
            "copy",
            chunk_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        chunks.append((chunk_path, start))
        logger.info("Audio chunk %s: %.0fs -> %.0fs -> %s", chunk_idx, start, end, chunk_path)
        start = end

    logger.info("Split audio into %s chunks (total %.0fs)", len(chunks), duration)
    return chunks


class BaseTranscriber(ABC):
    """Base transcriber."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        audio_duration: float | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict]:
        """Return timestamped transcript segments."""


class DashScopeASRTranscriber(BaseTranscriber):
    """Use DashScope async file transcription with sentence timestamps."""

    TERMINAL_FAILURE_STATES = {"FAILED", "CANCELED", "UNKNOWN"}

    def __init__(self):
        self.base_url = settings.dashscope_base_url.rstrip("/")
        self.model = settings.dashscope_asr_model
        logger.info("DashScopeASRTranscriber initialized: model=%s", self.model)

    def _get_api_key(self) -> str:
        # 同一北京业务空间的 Key 可同时用于 OpenAI 兼容 LLM 与原生 ASR。
        api_key = settings.dashscope_api_key.strip() or settings.llm_api_key.strip()
        if not api_key:
            raise RuntimeError(
                "未配置百炼 API Key。请在 .env 中设置 LLM_API_KEY，"
                "或单独设置 DASHSCOPE_API_KEY。"
            )
        return api_key

    async def _upload_to_temporary_oss(self, audio_path: str, api_key: str) -> str:
        """Upload a local audio file to DashScope's temporary OSS storage."""

        def upload() -> str:
            dashscope.base_http_api_url = self.base_url
            file_url, _ = OssUtils.upload(
                model=self.model,
                file_path=audio_path,
                api_key=api_key,
            )
            return file_url

        logger.info(
            "Uploading %.1f MB audio to DashScope temporary OSS: %s",
            os.path.getsize(audio_path) / 1024 / 1024,
            os.path.basename(audio_path),
        )
        return await asyncio.to_thread(upload)

    @staticmethod
    def _extract_segments(payload: dict[str, Any]) -> list[dict]:
        result: list[dict] = []
        for transcript in payload.get("transcripts") or []:
            for sentence in transcript.get("sentences") or []:
                text = str(sentence.get("text") or "").strip()
                if not text:
                    continue
                begin_ms = float(sentence.get("begin_time") or 0)
                end_ms = float(sentence.get("end_time") or begin_ms)
                result.append(
                    {
                        "start": begin_ms / 1000,
                        "end": end_ms / 1000,
                        "text": text,
                    }
                )
        result.sort(key=lambda item: item["start"])
        return result

    async def transcribe(
        self,
        audio_path: str,
        audio_duration: float | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict]:
        if progress_callback:
            await progress_callback(3, "正在上传音频到千问转录服务 · 3%")
        api_key = self._get_api_key()
        file_url = await self._upload_to_temporary_oss(audio_path, api_key)
        if progress_callback:
            await progress_callback(10, "音频上传完成，正在创建转录任务 · 10%")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
            "X-DashScope-OssResourceResolve": "enable",
        }
        request_body = {
            "model": self.model,
            "input": {"file_urls": [file_url]},
            "parameters": {"channel_id": [0]},
        }
        timeout_seconds = max(60, settings.dashscope_asr_timeout_seconds)
        poll_seconds = max(0.5, settings.dashscope_asr_poll_interval_seconds)

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0)) as client:
            response = await client.post(
                f"{self.base_url}/services/audio/asr/transcription",
                headers=headers,
                json=request_body,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"百炼 ASR 任务提交失败 (HTTP {response.status_code}): "
                    f"{response.text[:500]}"
                )

            output = response.json().get("output") or {}
            task_id = output.get("task_id")
            if not task_id:
                raise RuntimeError(f"百炼 ASR 未返回 task_id: {response.text[:500]}")

            if progress_callback:
                await progress_callback(15, "千问转录任务已提交 · 15%")

            deadline = time.monotonic() + timeout_seconds
            poll_started_at = time.monotonic()
            expected_seconds = min(180.0, max(20.0, (audio_duration or 300.0) * 0.08))
            task_output: dict[str, Any] = {}
            while time.monotonic() < deadline:
                task_response = await client.get(
                    f"{self.base_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if task_response.status_code != 200:
                    raise RuntimeError(
                        f"百炼 ASR 任务查询失败 (HTTP {task_response.status_code}): "
                        f"{task_response.text[:500]}"
                    )

                task_output = task_response.json().get("output") or {}
                task_status = str(task_output.get("task_status") or "").upper()
                if task_status == "SUCCEEDED":
                    break
                if task_status in self.TERMINAL_FAILURE_STATES:
                    detail = task_output.get("message") or task_output
                    raise RuntimeError(f"百炼 ASR 任务失败 ({task_status}): {detail}")
                elapsed = time.monotonic() - poll_started_at
                estimated = min(95, 15 + round((elapsed / expected_seconds) * 80))
                if progress_callback:
                    await progress_callback(
                        estimated, f"千问正在转录音频（估算） · {estimated}%"
                    )
                await asyncio.sleep(poll_seconds)
            else:
                raise RuntimeError(f"百炼 ASR 任务等待超时（{timeout_seconds} 秒）")

            segments: list[dict] = []
            for item in task_output.get("results") or []:
                if str(item.get("subtask_status") or "SUCCEEDED").upper() != "SUCCEEDED":
                    raise RuntimeError(f"百炼 ASR 子任务失败: {item}")
                transcription_url = item.get("transcription_url")
                if not transcription_url:
                    continue
                result_response = await client.get(transcription_url)
                result_response.raise_for_status()
                segments.extend(self._extract_segments(result_response.json()))

        segments.sort(key=lambda item: item["start"])
        if not segments:
            raise RuntimeError("百炼 ASR 已完成，但没有返回带时间戳的转写片段。")
        if progress_callback:
            await progress_callback(100, "千问转录完成 · 100%")
        logger.info("DashScope ASR total: %s segments from %s", len(segments), audio_path)
        return segments


class GroqASRTranscriber(BaseTranscriber):
    """Use Groq Whisper transcription with segment timestamps."""

    TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self):
        self.model = settings.groq_asr_model
        logger.info("GroqASRTranscriber initialized: model=%s", self.model)

    def _get_api_key(self) -> str:
        api_key = settings.groq_api_key.strip()
        if not api_key:
            raise RuntimeError("未配置 Groq API Key。请在 .env 中设置 GROQ_API_KEY。")
        return api_key

    async def _transcribe_single(self, audio_path: str) -> list[dict]:
        api_key = self._get_api_key()

        file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
        logger.info(
            "Groq ASR uploading %.1f MB audio: %s, model=%s",
            file_size_mb,
            os.path.basename(audio_path),
            self.model,
        )

        with open(audio_path, "rb") as file_obj:
            audio_data = file_obj.read()

        data = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, read=600.0, write=600.0)
        ) as client:
            response = await client.post(
                self.TRANSCRIPTION_URL,
                data=data,
                files={"file": (os.path.basename(audio_path), audio_data, "audio/mpeg")},
                headers=headers,
            )

        if response.status_code != 200:
            error_detail = response.text[:500]
            logger.error(
                "Groq ASR HTTP error: status_code=%s, body=%s",
                response.status_code,
                error_detail,
            )
            raise RuntimeError(f"Groq ASR request failed (HTTP {response.status_code}): {error_detail}")

        payload = response.json()
        segments = payload.get("segments") or []
        result = []
        for segment in segments:
            text = segment.get("text", "").strip()
            if not text:
                continue
            result.append(
                {
                    "start": float(segment.get("start", 0.0)),
                    "end": float(segment.get("end", 0.0)),
                    "text": text,
                }
            )

        logger.info("Groq ASR chunk transcribed: %s segments", len(result))
        return result

    async def transcribe(
        self,
        audio_path: str,
        audio_duration: float | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict]:
        chunk_minutes = max(1, settings.groq_asr_chunk_minutes)
        chunk_seconds = chunk_minutes * 60
        if audio_duration:
            logger.info("Groq ASR using known audio duration from task metadata: %.1fs", audio_duration)

        chunks = _split_audio(audio_path, chunk_seconds, known_duration=audio_duration)
        logger.info("Audio split into %s chunk(s) for Groq ASR", len(chunks))

        all_segments = []
        if progress_callback:
            await progress_callback(0, "正在准备音频分段 · 0%")
        for index, (chunk_path, offset) in enumerate(chunks, start=1):
            logger.info("Groq transcribing chunk %s/%s (offset=%.0fs)", index, len(chunks), offset)
            segments = await self._transcribe_single(chunk_path)

            for seg in segments:
                seg["start"] += offset
                seg["end"] += offset

            all_segments.extend(segments)

            if progress_callback:
                stage_progress = round(index / len(chunks) * 100)
                await progress_callback(
                    stage_progress,
                    f"语音转录分段 {index}/{len(chunks)} · {stage_progress}%",
                )

            if chunk_path != audio_path and os.path.exists(chunk_path):
                os.remove(chunk_path)

        all_segments.sort(key=lambda item: item["start"])
        logger.info("Groq ASR total: %s segments from %s", len(all_segments), audio_path)
        return all_segments


def get_transcriber() -> BaseTranscriber:
    """Return the configured ASR provider."""
    provider = settings.asr_provider.strip().lower()
    if provider == "dashscope":
        return DashScopeASRTranscriber()
    if provider == "groq":
        return GroqASRTranscriber()
    raise RuntimeError(f"不支持的 ASR_PROVIDER: {settings.asr_provider}")
