"""LLM 精彩片段分析器：调用 千问 分析转录文本，支持多场景模式"""

import json
import logging
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# 场景模式配置
# ══════════════════════════════════════════════════════════════════


@dataclass
class SceneConfig:
    """切片场景参数配置"""

    name: str                           # 场景标识（livestream / podcast / lecture）
    label: str                          # 中文显示名
    prompt_template: str                # LLM Prompt 模板（含 {transcript} 占位符）
    min_duration: float = 10.0          # 最小切片时长（秒），低于此值丢弃
    max_duration: float = 300.0         # 最大切片时长（秒），超过此值截断
    dedup_overlap_ratio: float = 0.3    # 去重重叠比例阈值


# ── 直播场景 Prompt ──────────────────────────────────────────────

_LIVESTREAM_PROMPT = """你是一个直播切片剪辑专家。分析以下直播转录文本，找出适合制作短视频切片的精彩片段。

## 转录文本（带时间轴，单位：秒）
{transcript}

## 切片标准
1. **高能时刻**：情绪爆发、搞笑片段、争议讨论
2. **干货知识**：有价值的观点、教程、经验分享
3. **互动精彩**：与观众的精彩互动
4. **金句名言**：可传播的经典语句
5. **带货亮点**：产品展示、砍价、用户反馈（如适用）

## 切片要求
- 每个切片 30秒 ~ 3分钟
- 片段要有完整的起承转合，不能话说一半就切
- 开头要有"钩子"（吸引注意力的内容）
- 结尾要有"价值感"（学到东西、被逗笑、有共鸣）

## ⚠️ 时间精度要求（务必遵守）
- start_time 和 end_time 必须直接使用上方转录文本中出现的秒数值（如 510.2、604.7）
- **禁止**四舍五入、近似取整或自己编造不存在的时间点
- 各切片之间**不能有时间重叠**，如果两个精彩段有交集，合并为一个或只保留更精彩的那个

## 输出格式
请严格输出 JSON 数组，不要包含其他文本：
[
  {{
    "clip_id": 1,
    "title": "切片标题（吸引眼球）",
    "start_time": 510.2,
    "end_time": 604.7,
    "duration": 94.5,
    "type": "高能时刻",
    "summary": "内容概要",
    "virality_score": 8,
    "suggested_caption": "推荐的发布文案"
  }}
]"""

# ── 播客访谈场景 Prompt ──────────────────────────────────────────

_PODCAST_PROMPT = """你是一个播客与人物访谈剪辑专家。分析以下对谈转录文本，找出无需依赖前文、能够独立传播的视频片段。

## 转录文本（带时间轴，单位：秒）
{transcript}

## 切片标准
1. **观点洞察**：嘉宾给出鲜明、反常识或有解释力的观点
2. **故事经历**：包含人物、冲突、转折和结果的完整故事
3. **争议讨论**：主持人与嘉宾围绕一个分歧进行有价值的交锋
4. **实用干货**：可直接复用的方法、建议、经验或避坑提示
5. **情绪共鸣**：真诚表达、幽默瞬间或容易引发讨论的内容

## 切片要求
- 每个切片 **1分钟 ~ 4分钟**
- 以话题的自然开始和结束为边界，保留必要的提问或铺垫
- 单独播放时也能理解人物关系、讨论对象和核心结论
- 开头优先选择有悬念、有冲突或直接抛出观点的内容
- 结尾要形成结论、转折、笑点或情绪落点，不能话说一半就切
- 标题应突出观点、故事冲突或用户收益，避免只复述主持人的问题

## ⚠️ 时间精度要求（务必遵守）
- start_time 和 end_time 必须直接使用上方转录文本中出现的秒数值（如 510.2、604.7）
- **禁止**四舍五入、近似取整或自己编造不存在的时间点
- 各切片之间**不能有时间重叠**
- 删除寒暄、口播广告和无信息量的过渡，除非它们是理解片段所必需的

## 输出格式
请严格输出 JSON 数组，不要包含其他文本：
[
  {{
    "clip_id": 1,
    "title": "能独立传播的观点型或故事型标题",
    "start_time": 510.2,
    "end_time": 804.7,
    "duration": 294.5,
    "type": "观点洞察",
    "summary": "这段对谈的背景、核心观点与结论",
    "virality_score": 8,
    "suggested_caption": "适合播客或人物访谈短视频的发布文案"
  }}
]"""

# ── 课程/讲座场景 Prompt ─────────────────────────────────────────

_LECTURE_PROMPT = """你是一个课程视频剪辑专家。分析以下课程/讲座的转录文本，按知识点将长视频切分为独立的短视频片段。

## 转录文本（带时间轴，单位：秒）
{transcript}

## 切片标准
1. **独立知识点**：一个完整的概念、原理、方法论的讲解段落
2. **案例演示**：讲师用具体案例、代码、Demo 演示某个知识点的段落
3. **总结回顾**：讲师对一段内容进行总结或对比分析的段落
4. **互动问答**：学员提问 + 讲师解答的段落

## 切片要求
- 每个切片 **5分钟 ~ 10分钟**（一个完整知识点的典型时长）
- 以**话题切换**为自然分界点
- 切片必须包含一个**完整的知识点**：引入 → 讲解 → 总结
- 不能在讲师话说一半时截断

## ⚠️ 时间精度要求（务必遵守）
- start_time 和 end_time 必须直接使用上方转录文本中出现的秒数值（如 510.2、604.7）
- **禁止**四舍五入、近似取整或自己编造不存在的时间点
- 各切片之间**不能有时间重叠**

## 输出格式
请严格输出 JSON 数组，不要包含其他文本：
[
  {{
    "clip_id": 1,
    "title": "知识点主题",
    "start_time": 510.2,
    "end_time": 1004.7,
    "duration": 494.5,
    "type": "独立知识点",
    "summary": "内容概要",
    "virality_score": 7,
    "suggested_caption": "推荐的发布文案"
  }}
]"""

# ── 场景配置注册表 ───────────────────────────────────────────────

SCENE_CONFIGS: dict[str, SceneConfig] = {
    "livestream": SceneConfig(
        name="livestream",
        label="直播回放",
        prompt_template=_LIVESTREAM_PROMPT,
        min_duration=10.0,
        max_duration=300.0,       # 5 分钟
        dedup_overlap_ratio=0.3,
    ),
    "podcast": SceneConfig(
        name="podcast",
        label="播客访谈",
        prompt_template=_PODCAST_PROMPT,
        min_duration=30.0,
        max_duration=360.0,
        dedup_overlap_ratio=0.2,
    ),
    "lecture": SceneConfig(
        name="lecture",
        label="课程讲座",
        prompt_template=_LECTURE_PROMPT,
        min_duration=60.0,        # 知识点至少 1 分钟
        max_duration=900.0,       # 允许到 15 分钟
        dedup_overlap_ratio=0.2,
    ),
}

DEFAULT_SCENE = "livestream"


def get_scene_config(scene_mode: str | None = None) -> SceneConfig:
    """获取场景配置，不存在时回退到默认值"""
    mode = scene_mode or DEFAULT_SCENE
    # 兼容迁移前已保存的面试任务；重新处理时按新的播客访谈策略执行。
    if mode == "interview":
        mode = "podcast"
    config = SCENE_CONFIGS.get(mode)
    if not config:
        logger.warning(f"Unknown scene_mode '{mode}', falling back to '{DEFAULT_SCENE}'")
        config = SCENE_CONFIGS[DEFAULT_SCENE]
    return config


class ClipAnalyzer:
    """多场景切片分析器"""

    MAX_TOKENS_PER_BATCH = 6000

    def __init__(self, scene_mode: str | None = None):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model
        self.scene = get_scene_config(scene_mode)
        logger.info(f"ClipAnalyzer initialized with scene '{self.scene.name}' ({self.scene.label})")

    MAX_RETRIES = 3

    async def analyze(self, transcript: list[dict], progress_callback=None) -> list[dict]:
        """分段分析转录文本，返回切片方案"""
        batches = self._split_transcript(transcript)
        logger.info(f"Split transcript into {len(batches)} batches for analysis")

        all_clips = []
        clip_id_counter = 1
        failed_batches = []

        for i, batch in enumerate(batches):
            batch_clips = await self._analyze_batch_with_retry(i, len(batches), batch)

            if batch_clips is None:
                failed_batches.append(i + 1)
                if progress_callback:
                    await progress_callback(round((i + 1) / len(batches) * 100))
                continue

            # 更新 clip_id
            for clip in batch_clips:
                clip["clip_id"] = clip_id_counter
                clip_id_counter += 1

            all_clips.extend(batch_clips)
            if progress_callback:
                await progress_callback(round((i + 1) / len(batches) * 100))

        if failed_batches:
            logger.warning(
                f"Failed batches: {failed_batches} out of {len(batches)} total"
            )

        # 校验并对齐 LLM 返回的时间到转录 segment 边界
        before_align = len(all_clips)
        all_clips = self._align_to_transcript(all_clips, transcript)
        if len(all_clips) < before_align:
            logger.warning(
                f"Alignment dropped {before_align - len(all_clips)} invalid clips"
            )

        # 按 virality_score 降序排列
        all_clips.sort(key=lambda x: x.get("virality_score", 0), reverse=True)

        # 去重（时间段重叠超过 50% 的取高分项）
        all_clips = self._deduplicate(all_clips)

        logger.info(f"Total clips found: {len(all_clips)}")
        return all_clips

    async def _analyze_batch_with_retry(
        self, batch_idx: int, total_batches: int, batch: list[dict]
    ) -> list[dict] | None:
        """带重试的单批次分析，返回 None 表示彻底失败"""
        import asyncio

        formatted = self._format_transcript(batch)
        prompt = self.scene.prompt_template.format(transcript=formatted)
        time_range = f"{batch[0]['start']:.0f}s ~ {batch[-1]['end']:.0f}s"

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    f"Analyzing batch {batch_idx + 1}/{total_batches} "
                    f"(attempt {attempt}/{self.MAX_RETRIES}, "
                    f"segments={len(batch)}, range={time_range})"
                )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    timeout=120,
                )

                content = response.choices[0].message.content
                if not content or not content.strip():
                    logger.warning(
                        f"Batch {batch_idx + 1} attempt {attempt}: "
                        f"LLM returned empty content, retrying..."
                    )
                    await asyncio.sleep(2 * attempt)
                    continue

                logger.info(
                    f"Batch {batch_idx + 1} raw response length: "
                    f"{len(content)} chars, first 200: {content[:200]}"
                )

                clips = self._parse_response(content)

                if clips:
                    logger.info(
                        f"Batch {batch_idx + 1}: parsed {len(clips)} clips successfully"
                    )
                    return clips
                else:
                    logger.warning(
                        f"Batch {batch_idx + 1} attempt {attempt}: "
                        f"parsed 0 clips from non-empty response, retrying..."
                    )
                    await asyncio.sleep(2 * attempt)
                    continue

            except Exception as e:
                logger.error(
                    f"Batch {batch_idx + 1} attempt {attempt} failed: "
                    f"{type(e).__name__}: {e}"
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(3 * attempt)
                continue

        logger.error(
            f"Batch {batch_idx + 1} PERMANENTLY FAILED after "
            f"{self.MAX_RETRIES} attempts"
        )
        return None

    def _split_transcript(self, transcript: list[dict]) -> list[list[dict]]:
        """按 Token 预算分批"""
        batches, current_batch, current_tokens = [], [], 0

        for seg in transcript:
            # 中文约 1.5 字符 = 1 token
            seg_tokens = len(seg["text"]) / 1.5
            if current_tokens + seg_tokens > self.MAX_TOKENS_PER_BATCH and current_batch:
                batches.append(current_batch)
                current_batch, current_tokens = [], 0
            current_batch.append(seg)
            current_tokens += seg_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def _format_transcript(self, segments: list[dict]) -> str:
        """格式化转录文本为带时间轴的字符串（直接使用秒数，避免 LLM 换算误差）"""
        lines = []
        for seg in segments:
            lines.append(f"[{seg['start']:.1f}s → {seg['end']:.1f}s] {seg['text']}")
        return "\n".join(lines)

    def _parse_response(self, content: str) -> list[dict]:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON 数组
        content = content.strip()

        # 去掉 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            logger.warning(f"LLM returned non-array JSON: {type(result)}")
            return []
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 数组部分
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                logger.error(
                    f"Found JSON-like array but failed to parse it. "
                    f"Matched content (first 300 chars): {match.group()[:300]}"
                )
                return []

        logger.error(
            f"Failed to parse LLM response (no JSON array found). "
            f"Full content (first 500 chars): {content[:500]}"
        )
        return []

    def _deduplicate(self, clips: list[dict]) -> list[dict]:
        """去重：时间段重叠超过阈值的保留高分项（双向检测，阈值由场景配置决定）"""
        if not clips:
            return clips

        threshold = self.scene.dedup_overlap_ratio
        result = [clips[0]]
        for clip in clips[1:]:
            overlap = False
            clip_dur = clip["end_time"] - clip["start_time"]
            for existing in result:
                overlap_start = max(clip["start_time"], existing["start_time"])
                overlap_end = min(clip["end_time"], existing["end_time"])
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    existing_dur = existing["end_time"] - existing["start_time"]
                    # 双向：任一方重叠比例超阈值即视为重复
                    ratio = max(
                        overlap_duration / clip_dur if clip_dur > 0 else 0,
                        overlap_duration / existing_dur if existing_dur > 0 else 0,
                    )
                    if ratio > threshold:
                        overlap = True
                        break
            if not overlap:
                result.append(clip)

        return result

    def _align_to_transcript(
        self, clips: list[dict], transcript: list[dict]
    ) -> list[dict]:
        """将 LLM 返回的时间范围对齐到实际转录 segment 边界，过滤无效片段"""
        if not transcript or not clips:
            return clips

        import bisect

        seg_starts = sorted(s["start"] for s in transcript)
        seg_ends = sorted(s["end"] for s in transcript)
        min_time = seg_starts[0]
        max_time = seg_ends[-1]

        aligned = []
        for clip in clips:
            start = clip.get("start_time")
            end = clip.get("end_time")

            # 跳过缺失或明显异常的时间字段
            if start is None or end is None or end <= start:
                logger.warning(
                    f"Dropping clip '{clip.get('title', '?')}': "
                    f"invalid time range ({start} → {end})"
                )
                continue

            # 裁切到转录文本的合法时间范围
            start = max(min_time, start)
            end = min(max_time, end)

            if end <= start:
                logger.warning(
                    f"Dropping clip '{clip.get('title', '?')}': "
                    f"time range out of transcript bounds"
                )
                continue

            # 对齐 start_time 到最近的 segment 起始点
            idx = bisect.bisect_right(seg_starts, start) - 1
            idx = max(0, idx)
            clip["start_time"] = seg_starts[idx]

            # 对齐 end_time 到最近的 segment 结束点
            idx = bisect.bisect_left(seg_ends, end)
            idx = min(idx, len(seg_ends) - 1)
            clip["end_time"] = seg_ends[idx]

            # 重新计算时长
            clip["duration"] = clip["end_time"] - clip["start_time"]

            # 过滤时长异常的片段（由场景配置决定阈值）
            min_dur = self.scene.min_duration
            max_dur = self.scene.max_duration
            if clip["duration"] < min_dur:
                logger.warning(
                    f"Dropping clip '{clip.get('title', '?')}': "
                    f"too short ({clip['duration']:.1f}s < {min_dur:.0f}s)"
                )
                continue
            if clip["duration"] > max_dur:
                logger.warning(
                    f"Trimming clip '{clip.get('title', '?')}': "
                    f"too long ({clip['duration']:.1f}s), capping at {max_dur:.0f}s"
                )
                # 从 start 往后截取 max_dur 秒，对齐到最近的 segment 结束点
                target_end = clip["start_time"] + max_dur
                idx = bisect.bisect_left(seg_ends, target_end)
                idx = min(idx, len(seg_ends) - 1)
                clip["end_time"] = seg_ends[idx]
                clip["duration"] = clip["end_time"] - clip["start_time"]

            aligned.append(clip)

        return aligned

    @staticmethod
    def _format_time(seconds: float) -> str:
        """秒数转 HH:MM:SS 格式"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
