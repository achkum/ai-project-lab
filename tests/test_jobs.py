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
    def test_material_scope_cannot_change_under_the_same_version(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123')
        self.q.catalog['T4']['title']='A different experiment'
        with self.assertRaisesRegex(ValueError,'version bump'):
            self.q.enqueue([{'id':'T4','version':1}],'request-456')
    def test_result_url_cannot_escape_private_artifact_directory(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123');a=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],'review_ready','done',{'url':'javascript:alert(1)'})
    def test_local_app_requires_explicit_selected_delivery_scope(self):
        self.q.enqueue([{'id':'T4','version':1}],'request-123');a=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],'completed','local',{'demo_url':'http://127.0.0.1:19123/'})
        self.q.finish(a['id'],a['token'],'review_ready','findings')
        self.q.catalog['P4'].update(delivery_mode='working_product',delivery_target='local_service')
        self.q.enqueue([{'id':'P4','version':1}],'request-456');b=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(b['id'],b['token'],'completed','local',{'demo_url':'http://192.168.1.1:19123/'})
        self.q.finish(b['id'],b['token'],'completed','local',{'demo_url':'http://127.0.0.1:19123/'})

    def test_private_mobile_url_is_bound_to_the_selected_bp5_service(self):
        url='https://198.44.116.159.sslip.io/apps/bp5/'
        self.q.enqueue([{'id':'P4','version':1}],'wrong-pilot-url');a=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],'completed','ready',{'demo_url':url})
        self.q.finish(a['id'],a['token'],'review_ready','retained')
        self.q.catalog['BP5']={'id':'BP5','version':2,'title':'Practice','lane':'Project','delivery_mode':'working_product','delivery_target':'local_service'}
        self.q.enqueue([{'id':'BP5','version':2}],'bp5-private-pilot');b=self.q.claim()
        with self.assertRaises(ValueError):self.q.finish(b['id'],b['token'],'completed','ready',{'demo_url':url+'../other/'})
        self.q.finish(b['id'],b['token'],'completed','experimental prototype',{'demo_url':url})

if __name__=='__main__':unittest.main()
