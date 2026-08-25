import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.caption_generator import CaptionGenerator


class CaptionGeneratorTests(unittest.TestCase):
    def test_parse_json_array_inside_markdown_fence(self):
        result = CaptionGenerator._parse_response(
            '```json\n["第一条文案 #话题", "第二条文案 #干货", "第三条文案 #收藏"]\n```'
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "第一条文案 #话题")

    def test_invalid_response_returns_empty_list(self):
        self.assertEqual(CaptionGenerator._parse_response("not json"), [])


if __name__ == "__main__":
    unittest.main()
