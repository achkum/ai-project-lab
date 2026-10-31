import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from engine.discovery import dated_record,parse,Discovery
from engine.jobs import Jobs

class RecencyTests(unittest.TestCase):
    now=datetime(2026,10,31,tzinfo=timezone.utc).timestamp()
    def test_publication_not_crawl_time(self):
        r=dated_record({'published':'"2021-03-26T00:00:00Z"','first_seen':self.now},self.now)
        self.assertEqual(r['recency_bucket'],'background')
        for date,bucket in [('2026-10-15T00:00:00Z','recent_30d'),('2026-09-01T00:00:00Z','corroboration_90d'),('2027-01-01T00:00:00Z','future_date'),('garbage','unknown_date')]:
            self.assertEqual(dated_record({'published':json.dumps(date)},self.now)['recency_bucket'],bucket)
    def test_rfc_and_modified_only(self):
        self.assertEqual(dated_record({'published':'Sat, 24 Oct 2026 10:00:00 GMT'},self.now)['recency_bucket'],'recent_30d')
        self.assertEqual(dated_record({'published':json.dumps({'value':'2026-10-30T00:00:00Z','kind':'modified'})},self.now)['recency_bucket'],'modified_only')
        atom=b'<feed><entry><title>Old paper updated</title><link href="https://example.org/p"/><updated>2026-10-30T00:00:00Z</updated></entry></feed>'
        self.assertEqual(parse({'kind':'feed'},atom)[0]['date_kind'],'modified')
    def test_hold_preserves_queued_selection_and_blocks_new_claims(self):
        with tempfile.TemporaryDirectory() as d:
            q=Jobs(Path(d)/'jobs.sqlite',[{'id':'T1','version':1,'lane':'Thesis','title':'Topic'}])
            try:
                q.enqueue([{'id':'T1','version':1}],'request-one')
                (Path(d)/'discovery-hold.json').write_text('{}')
                self.assertIsNone(q.claim())
                self.assertEqual(q.snapshot()['jobs'][0]['state'],'queued')
                with self.assertRaises(ValueError):q.enqueue([{'id':'T1','version':1}],'request-two')
            finally:q.close()
