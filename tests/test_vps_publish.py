import unittest
import tempfile
from pathlib import Path
from engine.jobs import Jobs
from engine.vps_publish import compose, read_jobs


class PublisherTests(unittest.TestCase):
    def test_publisher_reconciles_disconnects_but_ignores_healthy_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'runtime/jobs.sqlite'
            now = [1000]
            q = Jobs(path, [{'id':'BP5','version':3,'title':'Practice','lane':'Project'}], clock=lambda:now[0])
            try:
                q.enqueue([{'id':'BP5','version':3}], 'publisher-idle-status')
                job = q.claim()
                before = read_jobs(path, clock=lambda:now[0])
                now[0] += 50
                q.heartbeat(job['id'], job['token'])
                self.assertEqual(before, read_jobs(path, clock=lambda:now[0]))
                self.assertEqual(set(before[0]), {'candidate','version','lane','state','updated'})
                now[0] += 181
                after = read_jobs(path, clock=lambda:now[0])
                self.assertEqual(after[0]['state'], 'needs_attention')
                self.assertEqual(after[0]['updated'], now[0])
                self.assertIsNone(q.claim())
            finally:
                q.close()

    def test_only_curated_allowlisted_cards_and_public_status(self):
        seed={'coverage':{'target':20},'thesis':{},'project':{}}
        cards=[{'id':'A','version':1,'publication':'owner_requested_visual_summary'}, {'id':'B','version':1,'publication':'owner_requested_visual_summary'}]
        jobs=[{'candidate':'A','version':1,'lane':'project','state':'completed','updated':100}]
        out=compose(seed,cards,{'hold':True,'manual_start_ids':['A']},{'generated_at':100,'checks':[]},jobs,[],101)
        self.assertEqual([c['id'] for c in out['opportunities']],['A'])
        self.assertTrue(out['opportunities'][0]['selected'])
        self.assertFalse(out['opportunities'][0]['recommended'])
        self.assertEqual(out['project']['state'],'completed')
        self.assertEqual(seed['thesis'],{})
        self.assertIsNone(out['thesis']['last_success'])
        self.assertEqual(out['thesis']['collection_last_success'], '1970-01-01T00:01:40+00:00')

    def test_collection_does_not_claim_research_complete(self):
        seed={'coverage':{},'thesis':{},'project':{}}
        research={'state':'investigating','last_completed_at':'2026-11-01T12:00:00+00:00','note':'Checking accessible data'}
        out=compose(seed,[],{}, {'generated_at':1793601102,'checks':[]},[],[],1793616000,research)
        self.assertEqual(out['thesis']['state'], 'investigating')
        self.assertEqual(out['thesis']['last_success'], research['last_completed_at'])
        self.assertNotEqual(out['thesis']['collection_last_success'], out['thesis']['last_success'])
        self.assertEqual(out['thesis']['research_run'], research)
