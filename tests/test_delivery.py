import tempfile,unittest
from pathlib import Path
from engine.jobs import Jobs

class DeliveryTests(unittest.TestCase):
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
