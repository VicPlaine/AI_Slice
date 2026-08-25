import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.services.task_progress import update_task_progress


class FakeDB:
    def __init__(self):
        self.commit_calls = 0

    async def commit(self):
        self.commit_calls += 1


class TaskProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_task_progress_persists_db_by_default(self):
        db = FakeDB()
        task = SimpleNamespace(
            id='task-1',
            status='pending',
            progress=0,
            progress_message='等待处理',
        )

        await update_task_progress(db, task, 35, '处理中', 'analyzing')

        self.assertEqual(task.progress, 35)
        self.assertEqual(task.progress_message, '处理中')
        self.assertEqual(task.status, 'analyzing')
        self.assertEqual(db.commit_calls, 1)

    async def test_update_task_progress_can_skip_db_commit(self):
        db = FakeDB()
        task = SimpleNamespace(
            id='task-2',
            status='uploading',
            progress=90,
            progress_message='正在保存切片',
        )

        await update_task_progress(
            db,
            task,
            95,
            '已保存 3/5 个切片',
            persist=False,
        )

        self.assertEqual(task.progress, 95)
        self.assertEqual(task.progress_message, '已保存 3/5 个切片')
        self.assertEqual(task.status, 'uploading')
        self.assertEqual(db.commit_calls, 0)


if __name__ == '__main__':
    unittest.main()
