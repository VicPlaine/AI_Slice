import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import transcriber


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class DashScopeTranscriberTests(unittest.IsolatedAsyncioTestCase):
    async def test_transcribe_maps_timestamped_sentences(self):
        observed = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, **kwargs):
                observed["submit_url"] = url
                observed["submit_headers"] = kwargs["headers"]
                observed["submit_json"] = kwargs["json"]
                return FakeResponse({"output": {"task_id": "task-123"}})

            async def get(self, url, **kwargs):
                if url.endswith("/tasks/task-123"):
                    return FakeResponse(
                        {
                            "output": {
                                "task_status": "SUCCEEDED",
                                "results": [
                                    {
                                        "subtask_status": "SUCCEEDED",
                                        "transcription_url": "https://result.test/result.json",
                                    }
                                ],
                            }
                        }
                    )
                return FakeResponse(
                    {
                        "transcripts": [
                            {
                                "sentences": [
                                    {"begin_time": 120, "end_time": 980, "text": " 第一段 "},
                                    {"begin_time": 1100, "end_time": 2450, "text": "第二段"},
                                ]
                            }
                        ]
                    }
                )

        async def fake_upload(audio_path, api_key):
            observed["upload"] = (audio_path, api_key)
            return "oss://dashscope-instant/test/sample.mp3"

        audio_path = ROOT / "backend" / "tests" / "fixtures" / "sample.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"fake mp3")

        original_client = transcriber.httpx.AsyncClient
        original_dashscope_key = transcriber.settings.dashscope_api_key
        original_llm_key = transcriber.settings.llm_api_key
        original_base_url = transcriber.settings.dashscope_base_url
        original_model = transcriber.settings.dashscope_asr_model
        try:
            transcriber.httpx.AsyncClient = FakeClient
            transcriber.settings.dashscope_api_key = ""
            transcriber.settings.llm_api_key = "shared-test-key"
            transcriber.settings.dashscope_base_url = "https://workspace.test/api/v1"
            transcriber.settings.dashscope_asr_model = "qwen-audio-3.0-asr-flash-filetrans"

            service = transcriber.DashScopeASRTranscriber()
            service._upload_to_temporary_oss = fake_upload
            progress_updates = []

            async def capture_progress(progress, message):
                progress_updates.append((progress, message))

            result = await service.transcribe(
                str(audio_path),
                audio_duration=900,
                progress_callback=capture_progress,
            )

            self.assertEqual(
                result,
                [
                    {"start": 0.12, "end": 0.98, "text": "第一段"},
                    {"start": 1.1, "end": 2.45, "text": "第二段"},
                ],
            )
            self.assertEqual(observed["upload"][1], "shared-test-key")
            self.assertEqual(
                observed["submit_json"]["input"]["file_urls"],
                ["oss://dashscope-instant/test/sample.mp3"],
            )
            self.assertEqual(
                observed["submit_headers"]["X-DashScope-OssResourceResolve"],
                "enable",
            )
            self.assertEqual([item[0] for item in progress_updates], [3, 10, 15, 100])
        finally:
            transcriber.httpx.AsyncClient = original_client
            transcriber.settings.dashscope_api_key = original_dashscope_key
            transcriber.settings.llm_api_key = original_llm_key
            transcriber.settings.dashscope_base_url = original_base_url
            transcriber.settings.dashscope_asr_model = original_model
            audio_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
