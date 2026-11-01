import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from engine.product_delivery import contract,check_product,start_local,source_fingerprint,process_alive,reap_local_processes

class ProductDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lab-product-test-')
        self.root=Path(self.temp.name).resolve();self.w=self.root/'app';self.w.mkdir()
        self.runtime=self.root/'runtime';self.runtime.mkdir()
        for name in ('README.md','PRODUCT.md'):(self.w/name).write_text('Delivery harness fixture; not a business prototype.')
        self.spec={'delivery':'local_service','runtime':'python','entry':'server.py','memory_mb':128}
        (self.w/'product.json').write_text(json.dumps(self.spec));(self.w/'server.py').write_text('pass\n')
        self.job={'id':'fixture-instance','scope':{'id':'FIXTURE'}}
    def tearDown(self):
        assert self.root.parent==Path(tempfile.gettempdir()).resolve()
        self.temp.cleanup()
    def test_contract_rejects_escape_and_mismatched_delivery(self):
        contract(self.w,'local_service')
        with self.assertRaises(ValueError):contract(self.w,'static')
        (self.root/'outside.py').write_text('pass\n')
        self.spec['entry']='../outside.py';(self.w/'product.json').write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):contract(self.w,'local_service')
    def test_actual_failed_and_empty_acceptance_suites_are_rejected(self):
        tests=self.w/'tests';tests.mkdir()
        p=tests/'test_flow.py';p.write_text('import unittest\nclass Flow(unittest.TestCase):\n def test_real_result(self): self.assertEqual(2+2,5)\n')
        with self.assertRaises(RuntimeError):check_product(self.w,'local_service')
        self.assertIn('FAILED',(self.w/'VALIDATION.txt').read_text())
        p.write_text('import unittest\n')
        with self.assertRaises(RuntimeError):check_product(self.w,'local_service')
        p.write_text('import unittest\nclass Flow(unittest.TestCase):\n def test_real_result(self): self.assertEqual(2+2,4)\n')
        check_product(self.w,'local_service')
    def test_unresponsive_managed_process_is_preserved_not_duplicated(self):
        old={'fixture':{'job':self.job['id'],'pid':os.getpid(),'url':'http://127.0.0.1:19100/','memory_mb':128,'source_hash':source_fingerprint(self.w)}}
        (self.runtime/'local-products.json').write_text(json.dumps(old))
        with patch('engine.product_delivery.live_instance',return_value=False),patch('engine.product_delivery.sp.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'earlier local version'):start_local({'runtime_root':str(self.runtime)},self.job,self.w,lambda:None)
            spawn.assert_not_called()
    def test_larger_voice_budget_keeps_a_bounded_shared_admission_limit(self):
        self.spec['memory_mb']=5120;(self.w/'product.json').write_text(json.dumps(self.spec))
        contract(self.w,'local_service')
        self.spec['memory_mb']=5121;(self.w/'product.json').write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):contract(self.w,'local_service')
        self.spec['memory_mb']=2048;(self.w/'product.json').write_text(json.dumps(self.spec))
        existing={'other':{'job':'other-owner-selected-app','pid':os.getpid(),'url':'http://127.0.0.1:19100/','memory_mb':5120}}
        (self.runtime/'local-products.json').write_text(json.dumps(existing))
        with patch('engine.product_delivery.sp.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'resource budget'):start_local({'runtime_root':str(self.runtime)},self.job,self.w,lambda:None)
            spawn.assert_not_called()
        self.assertEqual(existing,json.loads((self.runtime/'local-products.json').read_text()))
    @unittest.skipUnless(os.name=='nt','Windows managed-service smoke check')
    def test_hidden_local_service_health_ui_and_idempotent_reuse(self):
        source='''import os,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  data=(json.dumps({'ok':True,'instance':os.environ['LAB_INSTANCE_ID']}).encode() if self.path=='/health' else b'<html>Delivery fixture</html>')
  self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/health' else 'text/html');self.end_headers();self.wfile.write(data)
  if self.path=='/stop':threading.Thread(target=self.server.shutdown,daemon=True).start()
server=ThreadingHTTPServer((os.environ['HOST'],int(os.environ['PORT'])),Handler)
server.serve_forever();server.server_close()
'''
        (self.w/'server.py').write_text(source)
        stopped={'job':'old-fixture','pid':0,'url':'http://127.0.0.1:19100/','memory_mb':128,'workspace':'retained-record'}
        (self.runtime/'local-products.json').write_text(json.dumps({'stopped':stopped}))
        url=start_local({'runtime_root':str(self.runtime)},self.job,self.w,lambda:None)
        record=json.loads((self.runtime/'local-products.json').read_text())['fixture']
        try:
            self.assertTrue(url.startswith('http://127.0.0.1:19'))
            self.assertTrue(process_alive(record['pid']))
            self.assertEqual(stopped,json.loads((self.runtime/'local-products.json').read_text())['stopped'])
            with patch('engine.product_delivery.sp.Popen') as spawn:
                self.assertEqual(url,start_local({'runtime_root':str(self.runtime)},self.job,self.w,lambda:None));spawn.assert_not_called()
        finally:
            urlopen(url+'stop',timeout=3).close()
            for _ in range(40):
                if not process_alive(record['pid']):break
                time.sleep(.1)
            self.assertFalse(process_alive(record['pid']))
            reap_local_processes()

if __name__=='__main__':unittest.main()
