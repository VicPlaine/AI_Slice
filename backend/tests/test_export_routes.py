import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.main import app


class ExportRoutesTests(unittest.TestCase):
    def test_legacy_export_routes_are_not_registered(self):
        route_paths = {route.path for route in app.routes}

        self.assertNotIn('/api/tasks/{task_id}/export/clips', route_paths)
        self.assertNotIn('/api/tasks/{task_id}/export/jianying', route_paths)
        self.assertNotIn('/api/tasks/{task_id}/export/srt', route_paths)
        self.assertNotIn('/api/tasks/{task_id}/export/captions', route_paths)


if __name__ == '__main__':
    unittest.main()
