import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.services.task_duration import hydrate_missing_task_durations


class HydrateMissingTaskDurationsTests(unittest.IsolatedAsyncioTestCase):
    async def test_hydrates_only_tasks_missing_duration_with_existing_file(self):
        tasks = [
            SimpleNamespace(video_duration=None, source_path='/tmp/a.mp3'),
            SimpleNamespace(video_duration=88.0, source_path='/tmp/b.mp3'),
            SimpleNamespace(video_duration=None, source_path='/tmp/missing.mp3'),
        ]
        probe_calls: list[str] = []

        def fake_probe_duration(path: str) -> float:
            probe_calls.append(path)
            return 123.4

        updated = await hydrate_missing_task_durations(
            tasks,
            probe_duration=fake_probe_duration,
            path_exists=lambda path: path != '/tmp/missing.mp3',
        )

        self.assertEqual(updated, 1)
        self.assertEqual(tasks[0].video_duration, 123.4)
        self.assertEqual(tasks[1].video_duration, 88.0)
        self.assertIsNone(tasks[2].video_duration)
        self.assertEqual(probe_calls, ['/tmp/a.mp3'])


if __name__ == '__main__':
    unittest.main()
