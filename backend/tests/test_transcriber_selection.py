import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.services import transcriber


class TranscriberTests(unittest.TestCase):
    def test_get_transcriber_returns_configured_provider(self):
        original_provider = transcriber.settings.asr_provider
        try:
            transcriber.settings.asr_provider = 'dashscope'
            self.assertIsInstance(
                transcriber.get_transcriber(),
                transcriber.DashScopeASRTranscriber,
            )

            transcriber.settings.asr_provider = 'groq'
            self.assertIsInstance(
                transcriber.get_transcriber(),
                transcriber.GroqASRTranscriber,
            )
        finally:
            transcriber.settings.asr_provider = original_provider


if __name__ == '__main__':
    unittest.main()
