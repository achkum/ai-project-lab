import json,tempfile,unittest
from pathlib import Path
from engine.jobs import Jobs

class ManualStarts(unittest.TestCase):
    def test_explicit_options_start_while_old_selections_stay_held(self):
        with tempfile.TemporaryDirectory() as d:
            q=Jobs(Path(d)/'jobs.sqlite',[dict(id=i,version=1,lane='Thesis',title=i) for i in ['old','RT1','RT2']])
            try:
                q.enqueue([dict(id='old',version=1)],'old-request')
                (Path(d)/'discovery-hold.json').write_text(json.dumps(dict(manual_start_ids=['RT1','RT2'])))
                with self.assertRaises(ValueError):q.enqueue([dict(id='old',version=1)],'blocked-request')
                items=[dict(id=i,version=1) for i in ['RT1','RT2']]
                ids=q.enqueue(items,'new-request')
                self.assertEqual(ids,q.enqueue(items,'new-request'))
                job=q.claim()
                self.assertIn(job['scope']['id'],['RT1','RT2'])
                self.assertIsNone(q.claim())
                self.assertEqual(next(j for j in q.snapshot()['jobs'] if j['candidate']=='old')['state'],'queued')
            finally:q.close()
