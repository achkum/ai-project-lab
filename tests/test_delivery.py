import tempfile,unittest
from pathlib import Path
from engine.jobs import Jobs
from engine.job_worker import version_static_assets

class DeliveryTests(unittest.TestCase):
    def test_asset_url_changes_when_deployed_code_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);page=root/'index.html';asset=root/'app.js'
            page.write_text('<script src="app.js"></script>');asset.write_text('first')
            version_static_assets(root);first=page.read_text()
            self.assertIn('app.js?v=',first)
            asset.write_text('second');version_static_assets(root)
            self.assertNotEqual(page.read_text(),first)
    def test_completed_delivery_is_terminal_and_preserves_demo_link(self):
        with tempfile.TemporaryDirectory() as d:
            q=Jobs(Path(d)/'jobs.sqlite',[dict(id='RP1',version=2,title='App',lane='Project')])
            q.enqueue([dict(id='RP1',version=2)],'delivery-request')
            j=q.claim()
            with self.assertRaises(ValueError):
                q.finish(j['id'],j['token'],'completed','done',{'demo_url':'https://example.com/leak'})
            q.finish(j['id'],j['token'],'completed','App tested and deployed',{'demo_url':'https://achkum.github.io/ai-project-lab/projects/rp1/'})
            self.assertEqual(q.snapshot()['jobs'][0]['state'],'completed')
            with self.assertRaises(ValueError):q.control(j['id'],'resume')
            q.close()
