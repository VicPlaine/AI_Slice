import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import task_runner


class TaskRunnerCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_running_task_only_cancels_pipeline_child(self):
        task_id = "test-cancel-task"
        pipeline_task = asyncio.create_task(asyncio.sleep(60))
        task_runner._active_pipeline_tasks[task_id] = pipeline_task
        try:
            self.assertTrue(task_runner.cancel_running_task(task_id))
            with self.assertRaises(asyncio.CancelledError):
                await pipeline_task
            self.assertFalse(task_runner.cancel_running_task("missing-task"))
        finally:
            task_runner._active_pipeline_tasks.pop(task_id, None)


if __name__ == "__main__":
    unittest.main()
