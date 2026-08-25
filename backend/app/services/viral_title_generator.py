"""标题建议生成器：调用已配置的 LLM 为单个切片生成标题。"""

import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_VIRAL_TITLE_PROMPT = """你是一个抖音爆款标题策划专家，擅长写出让人忍不住点进来的短视频标题。

## 切片内容信息
- 原始标题：{title}
- 内容摘要：{summary}
- 内容分类：{clip_type}
- 参考文案：{suggested_caption}

## 要求
请基于以上内容信息，生成 5 个抖音风格的爆款标题。

### 标题规则
1. **20 字以内**，简短有力
2. **悬念感开头**：用反问、设问、转折制造好奇心
3. **适度使用 emoji**：1-2 个即可，不要堆砌
4. **包含爆款元素**（至少用 1 种）：
   - 数字化：「3个技巧」「99%的人不知道」
   - 反常识：「原来我们都错了」「千万别这样做」
   - 情绪化：「看完直接惊了」「评论区炸了」
   - 身份代入：「打工人必看」「新手最容易犯的错」
   - 紧迫感：「赶紧收藏」「再不看就晚了」
5. **基于实际内容**，不要编造不存在的信息
6. **5 个标题风格各异**，不要雷同

## 输出格式
请严格输出 JSON 数组，不要包含其他文本：
["标题1", "标题2", "标题3", "标题4", "标题5"]"""


class ViralTitleGenerator:
    """抖音风格爆款标题生成器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model

    async def generate(self, clip_context: dict) -> list[str]:
        """
        为单个切片生成 5 个抖音风格爆款标题。

        Args:
            clip_context: 包含 title, summary, clip_type, suggested_caption 的字典

        Returns:
            包含 5 个标题字符串的列表
        """
        prompt = _VIRAL_TITLE_PROMPT.format(
            title=clip_context.get("title", ""),
            summary=clip_context.get("summary", ""),
            clip_type=clip_context.get("clip_type", ""),
            suggested_caption=clip_context.get("suggested_caption", ""),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,  # 稍高温度增加创意多样性
                timeout=30,
            )

            content = response.choices[0].message.content
            if not content or not content.strip():
                logger.warning("ViralTitleGenerator: LLM returned empty content")
                return self._fallback_titles(clip_context)

            titles = self._parse_response(content)
            if not titles:
                logger.warning(
                    f"ViralTitleGenerator: failed to parse response, "
                    f"content={content[:200]}"
                )
                return self._fallback_titles(clip_context)

            logger.info(f"ViralTitleGenerator: generated {len(titles)} titles")
            return titles[:5]  # 确保最多 5 个

        except Exception as e:
            logger.error(
                f"ViralTitleGenerator failed: {type(e).__name__}: {e}"
            )
            raise RuntimeError(f"生成爆款标题失败: {str(e)[:100]}") from e

    def _parse_response(self, content: str) -> list[str]:
        """解析 LLM 返回的 JSON 数组"""
        content = content.strip()

        # 去掉 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            result = json.loads(content)
            if isinstance(result, list) and all(isinstance(t, str) for t in result):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 数组部分
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list) and all(isinstance(t, str) for t in result):
                    return result
            except json.JSONDecodeError:
                pass

        return []

    @staticmethod
    def _fallback_titles(clip_context: dict) -> list[str]:
        """兜底：当 LLM 解析失败时返回基于原标题的简单变体"""
        title = clip_context.get("title", "精彩片段")
        return [
            f"🔥 {title}",
            f"这个视频火了！{title}",
            f"看完这个你就懂了！{title}",
            f"建议收藏！{title}",
            f"太绝了！{title}",
        ]
