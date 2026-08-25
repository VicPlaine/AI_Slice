"""剪辑思路生成器：调用已配置的 LLM 生成结构化剪辑指导。"""

import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_EDITING_GUIDE_PROMPT = """你是一个专业短视频剪辑指导老师，擅长为抖音/短视频平台的内容提供详细的剪辑思路。

## 切片内容信息
- 标题：{title}
- 内容摘要：{summary}
- 内容分类：{clip_type}
- 时长：{duration} 秒（约 {duration_display}）
- 爆款指数：{virality_score}/10

## 要求
请基于以上信息，给出一份完整的剪辑指导方案，帮助剪辑师快速完成高质量短视频。

### 输出内容（5 个维度）

1. **special_effects**（特效时间点建议）：
   - 给出 3~6 个关键时间点，标注应该加什么特效
   - 每个时间点包含：相对时间（如 "0:03"）、特效类型、加特效的原因
   - 特效类型包括但不限于：缩放、闪白转场、抖动、模糊转清晰、画面分割、贴纸动画
   - 时间点不要超过切片总时长 {duration} 秒

2. **music**（配乐推荐）：
   - 推荐适合的 BGM 风格和节奏（BPM）
   - 说明什么时间段该用什么情绪的音乐
   - 控制在 2-3 句话

3. **subtitles**（字幕/贴纸建议）：
   - 给出 3~5 条字幕/贴纸使用建议
   - 包含花字、标题字幕、引导关注贴纸等

4. **rhythm**（节奏控制建议）：
   - 说明视频的节奏编排，哪里加速、哪里放慢、哪里做停顿
   - 控制在 2-3 句话

5. **cover**（封面截取建议）：
   - 推荐从什么时间点截取封面
   - 说明为什么这个画面适合做封面
   - 控制在 1-2 句话

## 输出格式
请严格输出 JSON 对象，不要包含其他文本：
{{
  "special_effects": [
    {{"time_point": "0:03", "effect": "缩放特效", "reason": "强调开场钩子，快速抓住观众注意力"}},
    {{"time_point": "0:15", "effect": "闪白转场", "reason": "切换话题时制造节奏感"}}
  ],
  "music": "推荐使用轻快节奏的电子 BGM，BPM 120 左右。前 5 秒用悬念感音效，高潮段切换为节奏更强的 BGM。",
  "subtitles": [
    "开头 3 秒加大字标题字幕，突出核心主题",
    "关键观点处加动态花字特效，增强视觉冲击",
    "结尾加「关注 + 点赞」引导贴纸"
  ],
  "rhythm": "前 3 秒快节奏吸引注意 → 中间干货段保持正常速度 → 高潮处 1.2x 加速制造紧凑感 → 最后 3 秒放慢收尾。",
  "cover": "建议截取约 0:08 处的画面作为封面，此处画面丰富、表情生动，配合标题文字能有效吸引点击。"
}}"""


class EditingGuideGenerator:
    """短视频剪辑思路生成器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model

    async def generate(self, clip_context: dict) -> dict:
        """
        为单个切片生成结构化剪辑指导。

        Args:
            clip_context: 包含 title, summary, clip_type, duration,
                         virality_score 的字典

        Returns:
            结构化剪辑指导 dict
        """
        duration = clip_context.get("duration", 60)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_display = f"{minutes}分{seconds}秒" if minutes else f"{seconds}秒"

        prompt = _EDITING_GUIDE_PROMPT.format(
            title=clip_context.get("title", ""),
            summary=clip_context.get("summary", ""),
            clip_type=clip_context.get("clip_type", ""),
            duration=int(duration),
            duration_display=duration_display,
            virality_score=clip_context.get("virality_score", 5),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                timeout=45,
            )

            content = response.choices[0].message.content
            if not content or not content.strip():
                logger.warning("EditingGuideGenerator: LLM returned empty content")
                return self._fallback_guide(clip_context)

            guide = self._parse_response(content)
            if not guide:
                logger.warning(
                    f"EditingGuideGenerator: failed to parse response, "
                    f"content={content[:200]}"
                )
                return self._fallback_guide(clip_context)

            logger.info("EditingGuideGenerator: generated guide successfully")
            return guide

        except Exception as e:
            logger.error(
                f"EditingGuideGenerator failed: {type(e).__name__}: {e}"
            )
            raise RuntimeError(f"生成剪辑思路失败: {str(e)[:100]}") from e

    def _parse_response(self, content: str) -> dict | None:
        """解析 LLM 返回的 JSON 对象"""
        content = content.strip()

        # 去掉 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            result = json.loads(content)
            if isinstance(result, dict) and "special_effects" in result:
                return self._validate_guide(result)
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 对象部分
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict) and "special_effects" in result:
                    return self._validate_guide(result)
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _validate_guide(guide: dict) -> dict:
        """确保指南结构完整"""
        validated = {
            "special_effects": guide.get("special_effects", []),
            "music": guide.get("music", ""),
            "subtitles": guide.get("subtitles", []),
            "rhythm": guide.get("rhythm", ""),
            "cover": guide.get("cover", ""),
        }
        # 确保 special_effects 中每项都有必要字段
        validated["special_effects"] = [
            {
                "time_point": fx.get("time_point", "0:00"),
                "effect": fx.get("effect", "特效"),
                "reason": fx.get("reason", ""),
            }
            for fx in validated["special_effects"]
            if isinstance(fx, dict)
        ]
        # 确保 subtitles 是字符串列表
        validated["subtitles"] = [
            s for s in validated["subtitles"] if isinstance(s, str)
        ]
        return validated

    @staticmethod
    def _fallback_guide(clip_context: dict) -> dict:
        """兜底：LLM 解析失败时返回通用剪辑建议"""
        return {
            "special_effects": [
                {"time_point": "0:03", "effect": "缩放特效", "reason": "开场吸引注意力"},
                {"time_point": "0:10", "effect": "闪白转场", "reason": "切换到主要内容"},
            ],
            "music": "推荐使用节奏感适中的 BGM，与内容风格匹配。",
            "subtitles": [
                "开头加大字标题字幕",
                "关键内容处加花字强调",
                "结尾加关注引导贴纸",
            ],
            "rhythm": "保持正常播放速度，高潮处可适当加速。",
            "cover": "建议选取内容最精彩的瞬间作为封面。",
        }
