import tempfile,unittest
from pathlib import Path
from engine.jobs import Jobs
from engine.job_worker import version_static_assets,pages_workflow_contains
from engine import background_process as sp
import json
from unittest.mock import patch
from subprocess import CompletedProcess

class DeliveryTests(unittest.TestCase):
    def test_vps_deployment_url_is_narrowly_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            q=Jobs(Path(d)/'jobs.sqlite',[dict(id='NP1',version=1,title='App',lane='Project')])
            q.enqueue([dict(id='NP1',version=1)],'vps-delivery');j=q.claim()
            for url in ('https://198.44.116.159.sslip.io.evil.invalid/dashboard/projects/np1/','https://198.44.116.159.sslip.io/password','https://198.44.116.159.sslip.io/dashboard/projects/../'):
                with self.assertRaises(ValueError):q.finish(j['id'],j['token'],'completed','done',{'demo_url':url})
            url='https://198.44.116.159.sslip.io/dashboard/projects/np1/'
            q.finish(j['id'],j['token'],'completed','App deployed',{'demo_url':url})
            self.assertEqual(q.snapshot()['jobs'][0]['result']['demo_url'],url)
            q.close()
    def test_deployment_must_include_the_app_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args):return sp.check_output(['git',*args],cwd=root,text=True).strip()
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            def commit(text):
                (root/'file.txt').write_text(text);git('add','.');git('commit','-qm',text)
                return git('rev-parse','HEAD')
            base=commit('base');app=commit('app');snapshot=commit('snapshot')
            git('checkout','-q',base);unrelated=commit('unrelated')
            original=sp.run
            def check(success):
                def run(args,**kwargs):
                    if args[0]=='gh':return CompletedProcess(args,0,json.dumps({'workflow_runs':[{'head_sha':success,'conclusion':'success'},{'head_sha':app,'conclusion':'failure'}]}),'')
                    if args[:2]==['git','fetch']:return CompletedProcess(args,0,'','')
                    return original(args,**kwargs)
                with patch('engine.job_worker.subprocess.run',side_effect=run):
                    return pages_workflow_contains(root,app)
            self.assertTrue(check(app))
            self.assertTrue(check(snapshot))
            self.assertFalse(check(base))
            self.assertFalse(check(unrelated))
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
