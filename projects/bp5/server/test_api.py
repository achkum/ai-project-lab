import importlib.util, json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('app',Path(__file__).with_name('app.py'))
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
class BoundaryTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(); app.DB=Path(cls.temp.name)/'db.sqlite'; app.DATA=Path(cls.temp.name)
  cls.http=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler); threading.Thread(target=cls.http.serve_forever,daemon=True).start()
  cls.base='http://127.0.0.1:'+str(cls.http.server_port)
  cls.sc=patch.object(app,'scene',side_effect=lambda sid: {'id':sid,'opening_sv':'Hej'} if sid=='cafe' else (_ for _ in ()).throw(ValueError('Unknown scenario'))); cls.sc.start()
  cls.ai=patch.object(app,'character',return_value='Varsågod!'); cls.ai.start()
 @classmethod
 def tearDownClass(cls): cls.http.shutdown(); cls.http.server_close(); cls.sc.stop();cls.ai.stop();cls.temp.cleanup()
 def req(self,path,method='GET',data=None):
  b=None if data is None else json.dumps(data).encode()
  req=urllib.request.Request(self.base+path,data=b,method=method,headers={'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   with e: return e.code,json.load(e)
 def test_session_roundtrip_and_delete(self):
  status,r=self.req('/api/sessions','POST',{'scenario_id':'cafe','framework_id':'old','course':'2B','support':['hint']}); self.assertEqual(status,201); sid=r['session']['id']
  status,r=self.req('/api/sessions/'+sid+'/turn','POST',{'text':'En kaffe tack','input_mode':'voice','help_used':['hint']}); self.assertEqual(status,200); self.assertEqual(r['session']['turns'][1]['input_mode'],'voice'); self.assertEqual(r['session']['turns'][1]['help_used'],['hint'])
  status,r=self.req('/api/sessions/'+sid+'/evidence','POST',{'activity':'writing','response':'Tack','help_used':[]});self.assertEqual(status,200);self.assertEqual(r['session']['framework_id'],'old');self.assertEqual(r['session']['evidence'][0]['response'],'Tack')
  self.assertEqual(self.req('/api/export')[1]['sessions'][0]['id'],sid);self.assertEqual(self.req('/api/sessions/'+sid,'DELETE')[0],200);self.assertEqual(self.req('/api/sessions/'+sid)[0],400)
 def test_idempotent_turn_and_evidence(self):
  sid=self.req('/api/sessions','POST',{'scenario_id':'cafe'})[1]['session']['id']
  turn={'text':'Kaffe tack','input_mode':'text','help_used':[],'request_id':'turn-1'}
  first=self.req('/api/sessions/'+sid+'/turn','POST',turn)[1]; second=self.req('/api/sessions/'+sid+'/turn','POST',turn)[1]
  self.assertEqual(first['reply'],second['reply']);self.assertEqual(len(second['session']['turns']),3)
  e={'activity':'reading','response':'Ja','help_used':[],'request_id':'ev-1'}
  self.req('/api/sessions/'+sid+'/evidence','POST',e); session=self.req('/api/sessions/'+sid+'/evidence','POST',e)[1]['session']; self.assertEqual(len(session['evidence']),1);self.assertIn('snapshot',session)
 def test_delete_waits_for_inflight_turn(self):
  sid=self.req('/api/sessions','POST',{'scenario_id':'cafe'})[1]['session']['id']; entered=threading.Event(); release=threading.Event()
  def slow(s): entered.set();release.wait(3);return 'Hej'
  with patch.object(app,'character',side_effect=slow):
   t=threading.Thread(target=lambda:self.req('/api/sessions/'+sid+'/turn','POST',{'text':'Hej','input_mode':'text'}));t.start();self.assertTrue(entered.wait(2))
   result=[];d=threading.Thread(target=lambda:result.append(self.req('/api/sessions/'+sid,'DELETE')));d.start();release.set();t.join(5);d.join(5)
  self.assertEqual(result[0][0],200);self.assertEqual(self.req('/api/sessions/'+sid)[0],400)
 def test_coach_withholds_unsupported_grading(self):
  for unsafe in ['Your pronunciation grade is A', 'Your Swedish is well-pronounced', 'You sound fluent']:
   with patch.object(app,'generate',return_value=unsafe):
    with self.assertRaises(RuntimeError): app.coach({'turns':[{'role':'user','text':'Hej'}]})
 def test_model_output_preserves_swedish_after_invalid_byte(self):
  with patch.object(app,'execute',return_value=b'\x82\xac L\xc3\xb6rdag'):
   self.assertEqual(app.generate('system',[{'role':'user','text':'Hej'}]),'Lördag')
 def test_host_origin_and_content_type(self):
  for headers,expected in [({'Host':'evil.example'},403),({'Origin':'https://evil.example','Content-Type':'application/json'},403),({'Content-Type':'text/plain'},400)]:
   req=urllib.request.Request(self.base+'/api/sessions',data=b'{}',headers=headers,method='POST')
   with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,expected); e.exception.close()
 def test_invalid_inputs_and_private_paths(self):
  self.assertEqual(self.req('/api/sessions','POST',{'scenario_id':'unknown'})[0],400)
  self.assertEqual(self.req('/api/sessions','POST',{'scenario_id':'cafe','context':'x'*501})[0],400)
  self.assertEqual(self.req('/runtime/local-products/bp5/qwen.gguf')[0],404)
  self.assertEqual(self.req('/health')[1]['ok'],True)
if __name__=='__main__':unittest.main()
