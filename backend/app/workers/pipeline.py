"""视频处理 pipeline（纯前端 FFmpeg 架构）。

架构约定（参见 docs/阶段F-纯前端FFmpeg架构方案.md）：
- 浏览器端用 FFmpeg.wasm 抽音频后只上传音频文件
- 服务端只做 ASR + LLM 编排，不接触视频本体，不需要本机 FFmpeg
- 服务端只产出 clip plans（时间点 + 元数据），切片由前端 FFmpeg.wasm 完成
- task.source_path 永远指向音频文件
- task.video_duration 由前端在创建任务时传入
"""

import asyncio
import logging
import os
import shutil
import uuid

from sqlalchemy import select

from app.config import settings
from app.db import async_session
from app.models.database import Clip, Task, TaskStatus
from app.services.task_progress import update_task_progress
from app.services.transcriber import get_transcriber
from app.services.analyzer import ClipAnalyzer

logger = logging.getLogger(__name__)


async def run_video_pipeline(task_id: str):
    """音频 → ASR → LLM → clip plans 的纯网络 I/O 流水线。

    服务端**不切视频**：clip plans 落库后由前端 FFmpeg.wasm 完成实际切片下载。
    """
    work_dir = os.path.join(settings.temp_dir, task_id)
    os.makedirs(work_dir, exist_ok=True)

    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        try:
            audio_path = task.source_path

            if not os.path.exists(audio_path):
                raise RuntimeError(f"音频文件不存在: {audio_path}")
            file_size = os.path.getsize(audio_path)
            if file_size == 0:
                raise RuntimeError("音频文件为空 (0 bytes)")

            logger.info(
                f"Task {task_id}: 音频已就绪 path={audio_path}, "
                f"size={file_size / 1024 / 1024:.1f} MB"
            )

            # ── Step 1: 音频就绪 (0% → 15%) ──
            await update_task_progress(
                db,
                task,
                15,
                f"音频已就绪 ({file_size / 1024 / 1024:.1f} MB)，开始转录",
                TaskStatus.transcribing.value,
            )

            # ── Step 2: 语音转录 (15% → 60%) ──
            transcriber = get_transcriber()
            logger.info(
                f"Task {task_id}: 使用转录器 {type(transcriber).__name__}"
            )

            try:
                async def report_transcription_progress(
                    stage_progress: int, stage_message: str
                ) -> None:
                    total_progress = min(59, 15 + round(stage_progress * 44 / 100))
                    await update_task_progress(db, task, total_progress, stage_message)

                transcript = await transcriber.transcribe(
                    audio_path,
                    audio_duration=task.video_duration,
                    progress_callback=report_transcription_progress,
                )
            except Exception as e:
                logger.exception(f"Task {task_id}: 转录过程中发生异常")
                raise RuntimeError(
                    f"语音转录失败: {type(e).__name__}: {str(e)[:200]}。"
                    f"请检查 ASR 服务配置和网络。"
                ) from e

            task.transcript_json = transcript

            # ── 应用视频 PTS 偏移（OBS 分段录制修正） ──
            start_offset = getattr(task, 'video_start_offset', 0.0) or 0.0
            if start_offset > 1.0:
                logger.info(
                    f"Task {task_id}: 应用视频 PTS 偏移 {start_offset:.1f}s "
                    f"({int(start_offset // 3600)}h{int((start_offset % 3600) // 60)}m)"
                )
                for seg in transcript:
                    seg["start"] += start_offset
                    seg["end"] += start_offset
                task.transcript_json = transcript

            if not transcript or len(transcript) == 0:
                raise RuntimeError(
                    "语音转录结果为空（0 段）。ASR 服务返回成功但未识别到任何语音内容。\n"
                    "可能原因：\n"
                    "1. 音频中无可识别的人声（纯音乐/噪音）\n"
                    "2. 浏览器端音频抽取异常（检查前端 audioExtractor 日志）"
                )

            logger.info(f"Task {task_id}: 转录完成，共 {len(transcript)} 段")
            await update_task_progress(
                db,
                task,
                60,
                f"转录完成，共 {len(transcript)} 段",
            )

            # ── Step 3: LLM 分析精彩片段 (60% → 90%) ──
            await update_task_progress(
                db,
                task,
                60,
                "千问正在分析精彩片段 · 0%",
                TaskStatus.analyzing.value,
            )
            analyzer = ClipAnalyzer(scene_mode=getattr(task, 'scene_mode', None))
            async def report_analysis_progress(stage_progress: int) -> None:
                total_progress = min(89, 60 + round(stage_progress * 29 / 100))
                await update_task_progress(
                    db, task, total_progress, f"千问内容分析中 · {stage_progress}%"
                )

            clip_plans = await analyzer.analyze(
                transcript, progress_callback=report_analysis_progress
            )
            logger.info(
                f"Task {task_id}: LLM 分析完成，clip_plans={len(clip_plans)} 个"
            )

            if not clip_plans:
                logger.warning(
                    f"Task {task_id}: LLM 未识别到精彩片段。"
                    f"转录段数={len(transcript)}，音频时长={task.video_duration or 'N/A'}s。"
                )
                raise RuntimeError(
                    f"AI 分析完成但未识别到精彩片段（转录 {len(transcript)} 段）。"
                    f"可能原因：1) 千问 API 返回异常 2) 内容不足。"
                    f"请查看后端日志并重试。"
                )

            await update_task_progress(
                db,
                task,
                90,
                f"分析完成，找到 {len(clip_plans)} 个精彩片段",
            )

            # ── Step 4: 持久化 clip plans (90% → 100%) ──
            # 注意：file_key 永远为 None，切片产物在浏览器端生成并下载到用户本机
            await update_task_progress(
                db,
                task,
                95,
                "正在保存分析结果...",
                TaskStatus.uploading.value,
            )

            for i, clip_plan in enumerate(clip_plans):
                clip_record = Clip(
                    task_id=task.id,
                    clip_index=clip_plan["clip_id"],
                    title=clip_plan.get("title", f"切片 {i + 1}"),
                    summary=clip_plan.get("summary", ""),
                    clip_type=clip_plan.get("type", "未分类"),
                    start_time=clip_plan["start_time"],
                    end_time=clip_plan["end_time"],
                    duration=clip_plan.get(
                        "duration",
                        clip_plan["end_time"] - clip_plan["start_time"],
                    ),
                    virality_score=clip_plan.get("virality_score", 5),
                    suggested_caption=clip_plan.get("suggested_caption", ""),
                    file_key=None,  # 切片产物在浏览器端，服务端不存视频文件
                )
                db.add(clip_record)

            await db.commit()

            done_msg = (
                f"分析完成！识别到 {len(clip_plans)} 个精彩片段，"
                f"可在详情页点击「一键切片」由浏览器本地切片下载"
                if clip_plans
                else "分析完成，但未找到符合标准的精彩片段。可尝试重新处理。"
            )

            # ── 完成 ──
            await update_task_progress(
                db,
                task,
                100,
                done_msg,
                TaskStatus.done.value,
            )
            logger.info(
                f"Task {task_id} completed: {len(clip_plans)} clip plans persisted"
            )

        except asyncio.CancelledError:
            logger.info("Task %s pipeline canceled", task_id)
            await db.rollback()
            fresh_result = await db.execute(
                select(Task).where(Task.id == uuid.UUID(task_id))
            )
            fresh_task = fresh_result.scalar_one_or_none()
            if fresh_task and fresh_task.status != TaskStatus.canceled.value:
                fresh_task.status = TaskStatus.canceled.value
                fresh_task.progress_message = "任务已取消，后续转录和内容分析已停止"
                fresh_task.error_message = None
                await db.commit()
            raise

        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            error_msg = f"处理失败: {str(e)[:180]}"
            try:
                await db.rollback()
                task.error_message = str(e)[:500]
                await update_task_progress(
                    db,
                    task,
                    task.progress,
                    error_msg,
                    TaskStatus.failed.value,
                )
            except Exception:
                logger.exception(
                    "Failed to update error status to DB, forcing commit"
                )
                try:
                    await db.rollback()
                    task.status = TaskStatus.failed.value
                    task.error_message = str(e)[:500]
                    task.progress_message = error_msg[:200]
                    await db.commit()
                except Exception:
                    logger.exception("Final fallback commit also failed")
            raise

        finally:
            # 清理临时工作目录（音频源文件在 storage_dir，不在 temp_dir，不会被清掉）
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp dir: {work_dir}")
