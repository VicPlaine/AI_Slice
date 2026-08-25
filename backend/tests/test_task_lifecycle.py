import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.services.task_lifecycle import (
    cleanup_task_outputs,
    cleanup_task_storage,
    reset_task_for_retry,
)


class TaskLifecycleTests(unittest.TestCase):
    def test_reset_task_for_retry_clears_existing_clips_and_error_state(self):
        task = SimpleNamespace(
            status='done',
            progress=100,
            progress_message='处理完成',
            error_message='旧错误',
            clips=[SimpleNamespace(id='clip-1'), SimpleNamespace(id='clip-2')],
        )

        reset_task_for_retry(task)

        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.progress, 0)
        self.assertEqual(task.progress_message, '等待处理...')
        self.assertIsNone(task.error_message)
        self.assertEqual(task.clips, [])

    def test_cleanup_task_outputs_removes_only_generated_clips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / 'storage'
            upload_path = storage_dir / 'uploads' / 'source.mp3'
            clip_dir = storage_dir / 'clips' / 'task-1'

            upload_path.parent.mkdir(parents=True, exist_ok=True)
            clip_dir.mkdir(parents=True, exist_ok=True)
            upload_path.write_text('audio')
            (clip_dir / '01_demo.mp4').write_text('clip')

            task = SimpleNamespace(id='task-1', source_path=str(upload_path))

            cleanup_task_outputs(task, str(storage_dir))

            self.assertTrue(upload_path.exists())
            self.assertFalse(clip_dir.exists())

    def test_cleanup_task_storage_removes_managed_upload_and_clip_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / 'storage'
            upload_path = storage_dir / 'uploads' / 'source.mp3'
            clip_dir = storage_dir / 'clips' / 'task-1'

            upload_path.parent.mkdir(parents=True, exist_ok=True)
            clip_dir.mkdir(parents=True, exist_ok=True)
            upload_path.write_text('audio')
            (clip_dir / '01_demo.mp4').write_text('clip')

            task = SimpleNamespace(id='task-1', source_path=str(upload_path))

            cleanup_task_storage(task, str(storage_dir))

            self.assertFalse(upload_path.exists())
            self.assertFalse(clip_dir.exists())

    def test_cleanup_task_storage_keeps_external_user_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / 'storage'
            external_dir = Path(temp_dir) / 'external'
            external_file = external_dir / 'user-video.mp4'
            clip_dir = storage_dir / 'clips' / 'task-2'

            external_dir.mkdir(parents=True, exist_ok=True)
            clip_dir.mkdir(parents=True, exist_ok=True)
            external_file.write_text('video')
            (clip_dir / '01_demo.mp4').write_text('clip')

            task = SimpleNamespace(id='task-2', source_path=str(external_file))

            cleanup_task_storage(task, str(storage_dir))

            self.assertTrue(external_file.exists())
            self.assertFalse(clip_dir.exists())


if __name__ == '__main__':
    unittest.main()
