import tempfile
import unittest
from pathlib import Path
from engine.jobs import Jobs


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=1000
        self.q=Jobs(Path(self.tmp.name)/'jobs.sqlite',[{'id':x,'version':1,'title':x,'lane':'Thesis' if x[0]=='T' else 'Project'} for x in ('T4','T5','P4')],lambda:self.now)
    def tearDown(self):self.q.close();self.tmp.cleanup()
    def test_multiple_choices_and_retries_are_independent_and_idempotent(self):
        items=[{'id':'T4','version':1},{'id':'T5','version':1},{'id':'P4','version':1}]
        ids=self.q.enqueue(items,'request-123')
        self.assertEqual(len(ids),3)
        self.assertEqual(ids,self.q.enqueue(items,'request-123'))
        self.assertEqual(ids,self.q.enqueue(items,'request-456'))
        with self.assertRaises(ValueError):self.q.enqueue(items[:1],'request-123')
        self.assertEqual(len(self.q.snapshot()['jobs']),3)
    def test_bad_candidate_rejects_whole_batch(self):
        with self.assertRaises(ValueError):self.q.enqueue([{'id':'T4','version':1},{'id':'T5','version':2}],'request-123')
        self.assertEqual(self.q.snapshot()['jobs'],[])
    def test_serial_worker_pause_revokes_lease_and_preserves_other_jobs(self):
        ids=self.q.enqueue([{'id':'T4','version':1},{'id':'T5','version':1}],'request-123')
        a=self.q.claim();self.assertIsNone(self.q.claim())
        self.q.control(a['id'],'pause')
        with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],'review_ready','done')
        b=self.q.claim();self.assertNotEqual(a['id'],b['id'])
        self.q.finish(b['id'],b['token'],'review_ready','brief ready')
        self.q.control(a['id'],'resume');c=self.q.claim();self.assertEqual(c['id'],a['id'])
        self.assertNotEqual(c['token'],a['token'])
    def test_expired_work_is_not_silently_restarted(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123');self.q.claim();self.now+=181
        self.assertIsNone(self.q.claim());self.assertEqual(self.q.snapshot()['jobs'][0]['state'],'needs_attention')
    def test_snapshot_excludes_scope_and_leases(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123');self.q.claim()
        row=self.q.snapshot()['jobs'][0]
        self.assertNotIn('scope',row);self.assertNotIn('token',row)
    def test_result_url_cannot_escape_private_artifact_directory(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123');a=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],'review_ready','done',{'url':'javascript:alert(1)'})

if __name__=='__main__':unittest.main()
