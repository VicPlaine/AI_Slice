import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import transcriber


class GroqTranscriberTests(unittest.IsolatedAsyncioTestCase):
    async def test_transcribe_single_maps_segments(self):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "segments": [
                        {"start": 1.25, "end": 2.5, "text": " 第一段 "},
                        {"start": 3.0, "end": 4.75, "text": "第二段"},
                    ]
                }

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                file_tuple = kwargs["files"]["file"]
                if not isinstance(file_tuple[1], bytes):
                    raise AssertionError("Groq upload must pass bytes to httpx.AsyncClient")
                return FakeResponse()

        audio_path = ROOT / "backend" / "tests" / "fixtures" / "sample.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"fake mp3")

        original_client = transcriber.httpx.AsyncClient
        original_key = transcriber.settings.groq_api_key
        try:
            transcriber.httpx.AsyncClient = FakeClient
            transcriber.settings.groq_api_key = "test-key"

            result = await transcriber.GroqASRTranscriber()._transcribe_single(str(audio_path))

            self.assertEqual(
                result,
                [
                    {"start": 1.25, "end": 2.5, "text": "第一段"},
                    {"start": 3.0, "end": 4.75, "text": "第二段"},
                ],
            )
        finally:
            transcriber.httpx.AsyncClient = original_client
            transcriber.settings.groq_api_key = original_key
            audio_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
