import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine.queue_server import dashboard_file

class PublicDashboardTests(unittest.TestCase):
    def test_serves_public_files_but_never_parent_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);public=root/'docs';public.mkdir()
            (public/'index.html').write_text('public dashboard')
            (root/'credentials.json').write_text('must never be served')
            (public/'script.py').write_text('not a public asset')
            with patch('engine.queue_server.PUBLIC_DOCS',public):
                self.assertEqual(dashboard_file(''),public/'index.html')
                self.assertEqual(dashboard_file('index.html'),public/'index.html')
                for path in ('../credentials.json','%2e%2e/credentials.json','/credentials.json','script.py','%00.json'):
                    self.assertIsNone(dashboard_file(path))
