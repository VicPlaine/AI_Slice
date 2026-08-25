import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import local_export
from app.services.ffmpeg_tools import find_command


class LocalExportTests(unittest.TestCase):
    def test_native_ffmpeg_job_creates_downloadable_zip(self):
        ffmpeg = find_command("ffmpeg")
        if not ffmpeg:
            self.skipTest("FFmpeg is not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            original_storage_dir = local_export.settings.storage_dir
            local_export.settings.storage_dir = temp_dir
            try:
                job_id = "11111111-1111-1111-1111-111111111111"
                job_dir = local_export.create_job_directory(job_id)
                source_path = job_dir / "source.mp4"
                subprocess.run(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=black:s=320x180:d=2",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=44100:cl=stereo",
                        "-shortest",
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-y",
                        str(source_path),
                    ],
                    check=True,
                )
                local_export.start_local_export(
                    job_id,
                    source_path,
                    "sample.mp4",
                    [
                        {
                            "clip_index": 1,
                            "title": "测试片段",
                            "start_time": 0,
                            "duration": 1,
                        }
                    ],
                )

                deadline = time.monotonic() + 10
                job = local_export.get_local_export(job_id)
                while job and job["status"] not in {"done", "failed"}:
                    if time.monotonic() > deadline:
                        self.fail("local export timed out")
                    time.sleep(0.1)
                    job = local_export.get_local_export(job_id)

                self.assertIsNotNone(job)
                self.assertEqual(job["status"], "done")
                archive = local_export.get_local_export_archive(job_id)
                self.assertIsNotNone(archive)
                with zipfile.ZipFile(archive[0]) as zip_file:
                    self.assertEqual(len(zip_file.namelist()), 1)
                    self.assertGreater(zip_file.getinfo(zip_file.namelist()[0]).file_size, 0)
            finally:
                local_export.cleanup_local_export(job_id)
                local_export.settings.storage_dir = original_storage_dir


if __name__ == "__main__":
    unittest.main()
