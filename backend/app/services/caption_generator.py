"""Generate alternative social-media captions for a clip with Qwen."""

import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_CAPTION_PROMPT = """你是一名短视频运营文案策划，请为下面的视频切片生成 3 条可直接发布的文案。

## 内容信息
- 标题：{title}
- 摘要：{summary}
- 内容分类：{clip_type}
- 当前文案：{current_caption}

## 要求
1. 每条 45～100 个中文字符，开头有吸引力，但不要虚构内容
2. 口吻自然、有传播感，三条采用不同角度和表达方式
3. 适量使用 1～3 个 emoji，不要堆砌
4. 结尾包含 2～4 个与实际内容相关的话题标签
5. 不要使用引号包裹整条文案

请严格输出 JSON 字符串数组，不要包含其他文本：
["文案1", "文案2", "文案3"]"""


class CaptionGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model

    async def generate(self, clip_context: dict) -> list[str]:
        prompt = _CAPTION_PROMPT.format(
            title=clip_context.get("title", ""),
            summary=clip_context.get("summary", ""),
            clip_type=clip_context.get("clip_type", ""),
            current_caption=clip_context.get("suggested_caption", ""),
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                timeout=30,
            )
            content = response.choices[0].message.content or ""
            captions = self._parse_response(content)
            if not captions:
                raise RuntimeError("千问未返回可解析的发布文案")
            return captions[:3]
        except Exception as error:
            logger.error("CaptionGenerator failed: %s: %s", type(error).__name__, error)
            raise RuntimeError(f"生成发布文案失败: {str(error)[:100]}") from error

    @staticmethod
    def _parse_response(content: str) -> list[str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        candidates = [cleaned]
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match and match.group() != cleaned:
            candidates.append(match.group())
        for candidate in candidates:
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return [item.strip() for item in result if isinstance(item, str) and item.strip()]
            except json.JSONDecodeError:
                continue
        return []
