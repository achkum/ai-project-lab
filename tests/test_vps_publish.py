import unittest
import tempfile
import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from engine.jobs import Jobs
from engine import vps_publish
from engine.vps_publish import compose, read_jobs, write_catalog


class PublisherTests(unittest.TestCase):
    def test_optional_ltu_catalog_publishes_changes_with_same_allowlist_and_skips_unchanged_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root'
            checkout=Path(tmp)/'checkout'
            for directory in (root/'config',root/'runtime',checkout/'docs/data'):
                directory.mkdir(parents=True)
            def save(path,value):
                path.write_text(json.dumps(value),encoding='utf-8')
            save(root/'config/public-opportunities.json',[])
            save(root/'config/discovery-audit.json',{'hold':True})
            save(root/'config/collectors.json',[])
            save(root/'runtime/collection.json',{'generated_at':100,'checks':[]})
            save(checkout/'docs/data/status.json',{'coverage':{},'thesis':{},'project':{}})
            published=checkout/'docs/data/ltu-research.json'
            save(published,{'previous':'catalog'})
            commands=[]
            def run(command,**kwargs):
                commands.append((command,kwargs))
                stdout='docs/data/status.json\n' if command[1]=='diff' else 'commit-sha' if command[1]=='rev-parse' else ''
                return SimpleNamespace(stdout=stdout)
            real_path=Path
            def publisher_path(value):
                return checkout if value=='/home/openclaw/ai-dashboard-publish' else real_path(value)
            locks=SimpleNamespace(LOCK_EX=1,LOCK_NB=2,flock=Mock())
            with patch.object(vps_publish,'__file__',str(root/'engine/vps_publish.py')), \
                 patch.object(vps_publish,'Path',side_effect=publisher_path), \
                 patch.object(vps_publish,'read_jobs',return_value=[]), \
                 patch.dict('sys.modules',{'fcntl':locks}), \
                 patch.object(vps_publish.subprocess,'run',side_effect=run):
                vps_publish.main()
                self.assertEqual(json.loads(published.read_text()),{'previous':'catalog'})
                self.assertIn(['git','add','--','docs/data/status.json'],[command for command,_ in commands])
                legacy_inputs={'catalog':[],'audit':{'hold':True},'collected_at':100,'jobs':[],'sources':[],
                               'signals':None,'batches':None,'presentation':{}}
                expected=hashlib.sha256(json.dumps(legacy_inputs,sort_keys=True).encode()).hexdigest()
                self.assertEqual(json.loads((root/'runtime/dashboard-publish.json').read_text())['fingerprint'],expected)
                commands.clear()
                vps_publish.main()
                self.assertEqual(commands,[])

                source=root/'config/ltu-research.json'
                catalog={'schema_version':1,'generated_at':'2026-11-05','directory_url':'https://www.ltu.se/en/research/research-subjects',
                         'coverage':{'note':'Review in progress'},'subjects':[
                          {'id':'ml','name':'Machine Learning','url':'https://www.ltu.se/ml','review_status':'reviewed','topics':[
                           {'id':'example','title':'A reviewed listing','url':'https://www.ltu.se/example'}]}]}
                save(source,catalog)
                vps_publish.main()
                self.assertEqual(json.loads(published.read_text(encoding='utf-8')),catalog)
                for command,kwargs in commands:
                    self.assertIn('ai_dashboard_publish',kwargs['env']['GIT_SSH_COMMAND'])
                    if command[1]=='add' or 'commit' in command:
                        self.assertEqual(command[command.index('--')+1:],['docs/data/status.json','docs/data/ltu-research.json'])
                self.assertTrue(any(command[1]=='push' for command,_ in commands))
                commands.clear()
                vps_publish.main()
                self.assertEqual(commands,[])
                catalog['coverage']['note']='Another set of pages reviewed'
                save(source,catalog)
                vps_publish.main()
                self.assertTrue(any(command[1]=='push' for command,_ in commands))
                self.assertEqual(json.loads(published.read_text())['coverage']['note'],catalog['coverage']['note'])
                commands.clear()
                previous=published.read_bytes()
                save(source,{**catalog,'subjects':[{'name':'Malformed subject'}]})
                with self.assertRaises(ValueError):
                    vps_publish.main()
                self.assertEqual(commands,[])
                self.assertEqual(published.read_bytes(),previous)
                save(source,{**catalog,'mode':'sample'})
                with self.assertRaises(ValueError):
                    vps_publish.main()
                self.assertEqual(commands,[])
                self.assertEqual(published.read_bytes(),previous)

    def test_atomic_catalog_failure_preserves_existing_public_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ltu-research.json'
            path.write_text('previous catalog',encoding='utf-8')
            with patch.object(vps_publish.os,'replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    write_catalog(path,{'schema_version':1})
            self.assertEqual(path.read_text(encoding='utf-8'),'previous catalog')
            self.assertEqual(list(path.parent.iterdir()),[path])

    def test_atomic_catalog_is_publicly_readable_despite_private_publisher_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ltu-research.json'
            path.write_text('old',encoding='utf-8')
            with patch.object(vps_publish.os,'chmod',wraps=os.chmod) as chmod:
                write_catalog(path,{'schema_version':1})
            chmod.assert_called_once()
            self.assertEqual(chmod.call_args.args[1],0o644)
            self.assertEqual(json.loads(path.read_text()),{'schema_version':1})
            if os.name!='nt':
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)

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
