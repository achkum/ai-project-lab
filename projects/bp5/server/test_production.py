import os, sys, json, tempfile, unittest, importlib, subprocess, threading, time, socket, sqlite3, urllib.request, http.cookiejar, types, asyncio
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
TMP=tempfile.TemporaryDirectory();os.environ.update(LAB_DATA_DIR=TMP.name,BP5_PUBLIC_ORIGIN='http://testserver',BP5_ALLOWED_HOSTS='testserver',BP5_SECURE_COOKIE='0',BP5_COOKIE_PATH='/')
sys.path.insert(0,str(Path(__file__).resolve().parent))
import production_store as st
st.DATA=Path(TMP.name);st.DB=st.DATA/'production.sqlite3';st.init()
from fastapi.testclient import TestClient
import production
TEST_ROOT=Path(TMP.name);(TEST_ROOT/'content').mkdir()
mission={'id':'lib_test_m1','title':'Test','opening_sv':'Hej','start_step':'one','completion_objectives':['ask','choice'],'criterion_links':[], 'steps':[{'id':'one','objective':'ask','unknown_reply_sv':'Kan du säga det igen?','unknown_feedback_en':'Try the request','intents':[{'id':'coffee','required_groups':[['kaffe'],['vill ha','önskar']],'reject_terms':['inte'],'reply_sv':'Vill du sitta här?','feedback_en':'Request heard','next_step':'two'}]},{'id':'two','objective':'choice','unknown_reply_sv':'Här eller ta med?','unknown_feedback_en':'Choose','intents':[{'id':'stay','required_groups':[['sitta här']],'reject_terms':['inte'],'reply_sv':'Varsågod!','feedback_en':'Done','next_step':None}]}]}
(TEST_ROOT/'content'/'library.json').write_text(json.dumps({'content_version':'test1','situations':[{'id':'lib_test','title':'Test','missions':[mission]}]}),encoding='utf-8')
(TEST_ROOT/'content'/'curriculum.json').write_text(json.dumps({'content_version':'test1','frameworks':[],'criteria':[]}),encoding='utf-8')
ORIGIN={'origin':'http://testserver'}
class ProductionTest(unittest.TestCase):
 def setUp(self):
  self.previous_root=st.ROOT;st.ROOT=TEST_ROOT
  with st.connect() as c:c.execute('DELETE FROM attempts')
  self.c=TestClient(production.app);self.c.__enter__()
 def tearDown(self):self.c.__exit__(None,None,None);st.ROOT=self.previous_root
 def register(self,name):
  invite=st.create_invite();r=self.c.post('/api/auth/register',headers=ORIGIN,json={'username':name,'password':'correct horse battery staple','invite':invite});self.assertEqual(r.status_code,200,r.text);return r.json()
 def hdr(self,csrf):return {**ORIGIN,'x-csrf-token':csrf}
 def test_sql_injection_in_login_does_not_authenticate(self):
  r=self.c.post('/api/auth/login',headers=ORIGIN,json={'username':"alice' OR 1=1 --",'password':'anything'});self.assertEqual(r.status_code,400);self.assertNotIn('anything',r.text)
 def test_match_boundaries_reject_and_ambiguity(self):
  step=mission['steps'][0];self.assertIsNone(st.match_step(step,'Jag vill ha kaffe inte'));self.assertIsNone(st.match_step(step,'Jag vill ha kaffebönor'));self.assertIsNotNone(st.match_step(step,'Jag VILL HA KAFFE!'))
  ambiguous={**step,'intents':step['intents']+[dict(step['intents'][0],id='other')]};self.assertIsNone(st.match_step(ambiguous,'jag vill ha kaffe'))
 def test_exact_replies_are_full_sequence_and_do_not_weaken_groups(self):
  intent={'id':'decline','exact_replies_sv':['Jag kan inte komma på fredag, men vill gärna ses en annan dag.','Nej tack'], 'required_groups':[['vill ses'],['en annan dag']], 'reject_terms':['inte','nej']}
  step={'intents':[intent]}
  for text in ['JAG KAN INTE KOMMA PÅ FREDAG MEN VILL GÄRNA SES EN ANNAN DAG!', 'Nej, tack.']:
   self.assertEqual(st.match_step(step,text)['id'],'decline')
  for text in ['Jag kan inte komma på fredag men vill gärna ses en annan dag inte', 'Nej tack men ja', 'Jag vill ses en annan dag men inte fredag', 'Jag vill inte ses en annan dag']:
   self.assertIsNone(st.match_step(step,text))
  self.assertEqual(st.match_step(step,'Jag vill ses en annan dag')['id'],'decline')
  other={'id':'other','required_groups':[['nej'],['tack']],'reject_terms':[]}
  self.assertIsNone(st.match_step({'intents':[intent,other]},'Nej tack'))
 def test_readiness_accepts_valid_exact_only_and_rejects_invalid_exact(self):
  sample=json.loads(json.dumps(mission));sample['steps'][0]['intents'][0].pop('required_groups');sample['steps'][0]['intents'][0]['exact_replies_sv']=['Ja tack']
  lib={'situations':[{'id':f's{n}','missions':[dict(sample,id=f'm{n}-{j}') for j in range(3)]} for n in range(18)]}
  self.assertTrue(st.library_ready(lib));lib['situations'][0]['missions'][0]['steps'][0]['intents'][0]['exact_replies_sv']=['...'];self.assertFalse(st.library_ready(lib))
 def test_exact_only_and_invalid_match_spec_fail_closed(self):
  exact_only={'id':'yes','exact_replies_sv':['Ja tack'],'reject_terms':['nej']}
  self.assertTrue(st.valid_match_spec(exact_only));self.assertEqual(st.match_step({'intents':[exact_only]},'JA TACK!')['id'],'yes');self.assertIsNone(st.match_step({'intents':[exact_only]},'Ja tack inte'))
  for broken in [{'exact_replies_sv':['!!!']},{'exact_replies_sv':'Ja tack'},{'required_groups':[['ja']],'exact_replies_sv':[None]},{'required_groups':[],'exact_replies_sv':[]}]:
   self.assertFalse(st.valid_match_spec(broken));self.assertIsNone(st.match_step({'intents':[broken]},'ja tack'))
 def test_account_isolation_csrf_mission_restart_and_retry(self):
  a=self.register('aliceone'); ah=self.hdr(a['csrf']);r=self.c.post('/api/missions',headers=ah,json={'mission_id':'lib_test_m1','request_id':'start-1'});self.assertEqual(r.status_code,200,r.text);sid=r.json()['session']['id'];self.assertEqual(self.c.post('/api/missions',headers=ah,json={'mission_id':'lib_test_m1','request_id':'start-1'}).json()['session']['id'],sid)
  self.assertEqual(self.c.post('/api/missions',headers=ah,json={'mission_id':'lib_test_m1','request_id':'start-1','course':'x'}).status_code,409)
  self.assertEqual(self.c.post(f'/api/missions/{sid}/turn',headers=ORIGIN,json={'request_id':'a','text':'jag vill ha kaffe'}).status_code,403)
  self.assertEqual(self.c.post(f'/api/missions/{sid}/turn',headers={**ah,'origin':'https://evil.example'},json={'request_id':'a','text':'jag vill ha kaffe'}).status_code,403)
  injected=self.c.post(f'/api/missions/{sid}/turn',headers=ah,json={'request_id':'injection','text':"x' OR 1=1 --"});self.assertFalse(injected.json()['matched']);self.assertEqual(injected.json()['session']['current_step'],'one')
  bad={'request_id':'unknown','text':'jag vill ha kaffe inte'};r=self.c.post(f'/api/missions/{sid}/turn',headers=ah,json=bad);self.assertFalse(r.json()['matched']);self.assertEqual(r.json()['session']['current_step'],'one')
  turn={'request_id':'first','text':'jag vill ha kaffe'};r=self.c.post(f'/api/missions/{sid}/turn',headers=ah,json=turn);self.assertTrue(r.json()['matched']);self.assertEqual(r.json()['session']['current_step'],'two');n=len(r.json()['session']['turns']);self.assertEqual(len(self.c.post(f'/api/missions/{sid}/turn',headers=ah,json=turn).json()['session']['turns']),n);self.assertEqual(self.c.post(f'/api/missions/{sid}/turn',headers=ah,json={'request_id':'first','text':'different'}).status_code,409)
  r=self.c.post(f'/api/missions/{sid}/turn',headers=ah,json={'request_id':'end','text':'jag vill sitta här'});self.assertEqual(r.json()['session']['status'],'completed')
  self.c.post('/api/auth/logout',headers=ah,json={});b=self.register('bobtwo');bh=self.hdr(b['csrf']);self.assertEqual(self.c.get(f'/api/missions/{sid}').status_code,404);self.assertEqual(self.c.post(f'/api/missions/{sid}/turn',headers=bh,json={'request_id':'hack','text':'hej'}).status_code,404);self.assertEqual(self.c.delete(f'/api/missions/{sid}',headers=bh).status_code,404);export=self.c.get('/api/export');self.assertEqual(export.json()['sessions'],[]);self.assertIn('attachment',export.headers['content-disposition'])
 def test_clarify_preserves_voice_and_text_provenance_and_retry(self):
  a=self.register('clarifyowner');h=self.hdr(a['csrf']);start=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'clar-start'}).json()['session'];sid=start['id']
  for mode,edited in [('voice',True),('text',False)]:
   response=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'bad-'+mode,'text':'En kaffe, tack','input_mode':mode,'transcript_edited':edited,'help_used':['hint']});self.assertEqual(response.status_code,200);self.assertFalse(response.json()['matched']);idx=len(response.json()['session']['turns'])-2
   body={'request_id':'clar-'+mode,'step_id':'one','intent_id':'coffee','turn_index':idx,'turn_id':response.json()['session']['turns'][idx]['turn_id']};r=self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body);self.assertEqual(r.status_code,200,r.text);data=r.json();self.assertTrue(data['clarified']);self.assertFalse(data['matched']);self.assertEqual(data['match_source'],'learner_confirmation');s=data['session'];u=s['turns'][idx];self.assertEqual(u['text'],'En kaffe, tack');self.assertEqual(u['input_mode'],mode);self.assertEqual(u['transcript_edited'],edited);self.assertIsNone(u['intent_id']);self.assertEqual(u['confirmed_intent_id'],'coffee');self.assertEqual(u['help_used'],['hint','learner_confirmation']);self.assertEqual(u['evidence_state'],'practised');self.assertEqual(s['current_step'],'two');self.assertTrue(s['turns'][-1]['clarified']);self.assertFalse(s['turns'][-1]['matched'])
   retry=self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body);self.assertEqual(retry.status_code,200);self.assertEqual(len(retry.json()['session']['turns']),len(s['turns']));self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'intent_id':'other'}).status_code,409)
   self.assertEqual(self.c.post(f'/api/missions/{sid}/reset',headers=h,json={'request_id':'reset-'+mode}).status_code,200)
 def test_clarify_authorization_staleness_and_delete(self):
  a=self.register('clarifysafe');h=self.hdr(a['csrf']);sid=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'clar-safe-start'}).json()['session']['id'];body={'request_id':'choose','step_id':'one','intent_id':'coffee','turn_index':1,'turn_id':'nonexistent'}
  self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body).status_code,409)
  miss=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'bad','text':'En kaffe tack'}).json();body['turn_id']=miss['session']['turns'][1]['turn_id'];self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=ORIGIN,json=body).status_code,403);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'intent_id':'nonexistent'}).status_code,400);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'step_id':'two'}).status_code,409);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'turn_index':True}).status_code,400)
  self.c.post('/api/auth/logout',headers=h,json={});b=self.register('clarifyother');bh=self.hdr(b['csrf']);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=bh,json=body).status_code,404)
  self.c.post('/api/auth/logout',headers=bh,json={});login=self.c.post('/api/auth/login',headers=ORIGIN,json={'username':'clarifysafe','password':'correct horse battery staple'}).json();h=self.hdr(login['csrf'])
  self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'new-bad','text':'I want coffee'});self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body).status_code,409)
  self.c.post(f'/api/missions/{sid}/reset',headers=h,json={'request_id':'reset-safe'});self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body).status_code,409)
  self.assertEqual(self.c.delete(f'/api/missions/{sid}',headers=h).status_code,200);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body).status_code,404)
 def test_clarify_rejects_old_turn_id_after_reset_and_supports_legacy(self):
  a=self.register('clarifylegacy');h=self.hdr(a['csrf']);sid=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'legacy-clar'}).json()['session']['id'];miss=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'legacy-miss','text':'coffee please'}).json();old_id=miss['session']['turns'][1]['turn_id']
  with st.connect() as c:
   row=c.execute('SELECT payload FROM missions WHERE id=?',(sid,)).fetchone();payload=json.loads(row['payload']);payload['turns'][1].pop('turn_id');c.execute('UPDATE missions SET payload=? WHERE id=?',(json.dumps(payload),sid))
  s=self.c.get(f'/api/missions/{sid}').json()['session'];legacy=s['turns'][1]['turn_id'];self.assertTrue(legacy.startswith('legacy-'));self.assertEqual(self.c.get(f'/api/missions/{sid}').json()['session']['turns'][1]['turn_id'],legacy)
  body={'request_id':'legacy-choose','step_id':'one','intent_id':'coffee','turn_index':1,'turn_id':legacy};self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body).status_code,200)
  self.c.post(f'/api/missions/{sid}/reset',headers=h,json={'request_id':'legacy-reset'});new=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'new-miss','text':'coffee please'}).json()['session'];self.assertNotEqual(new['turns'][1]['turn_id'],old_id);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'request_id':'old-selection'}).status_code,409)
 def test_clarify_terminal_completion_preserves_objectives(self):
  a=self.register('clarifyfinish');h=self.hdr(a['csrf']);sid=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'clar-finish'}).json()['session']['id'];self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'first-finish','text':'jag vill ha kaffe'});miss=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'last-miss','text':'here please'}).json();index=len(miss['session']['turns'])-2
  body={'request_id':'last-choice','step_id':'two','intent_id':'stay','turn_index':index,'turn_id':miss['session']['turns'][index]['turn_id']};r=self.c.post(f'/api/missions/{sid}/clarify',headers=h,json=body);self.assertEqual(r.status_code,200);s=r.json()['session'];self.assertEqual(s['status'],'completed');self.assertEqual(s['completed_objectives'],['ask','choice']);self.assertEqual(s['turns'][index]['intent_id'],None);self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={**body,'request_id':'late'}).status_code,409)
 def test_clarify_concurrent_choices_only_one_advances(self):
  a=self.register('clarifyrace');h=self.hdr(a['csrf']);sid=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'clar-race'}).json()['session']['id'];miss=self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'race-bad','text':'coffee please'}).json()
  barrier=threading.Barrier(3);answers=[]
  def choose(rid):
   barrier.wait();answers.append(self.c.post(f'/api/missions/{sid}/clarify',headers=h,json={'request_id':rid,'step_id':'one','intent_id':'coffee','turn_index':1,'turn_id':miss['session']['turns'][1]['turn_id']}).status_code)
  threads=[threading.Thread(target=choose,args=(x,)) for x in ('race-one','race-two')]
  for t in threads:t.start()
  barrier.wait()
  for t in threads:t.join()
  self.assertEqual(sorted(answers),[200,409]);s=self.c.get(f'/api/missions/{sid}').json()['session'];self.assertEqual(len(s['turns']),4);self.assertEqual(s['completed_objectives'],['ask'])
 def test_progress_persists_and_is_owner_scoped_with_reset_delete(self):
  a=self.register('progressowner');h=self.hdr(a['csrf']);sid=self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'progress-start'}).json()['session']['id'];self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'progress-1','text':'jag vill ha kaffe'});self.c.post(f'/api/missions/{sid}/turn',headers=h,json={'request_id':'progress-2','text':'jag vill sitta här'})
  with TestClient(production.app) as fresh:
   fresh.cookies.update(self.c.cookies);response=fresh.get('/api/progress');self.assertEqual(response.status_code,200);summaries=response.json()['sessions'];self.assertEqual(len(summaries),1);self.assertEqual(set(summaries[0]),{'id','mission_id','status','updated_at'});self.assertEqual(summaries[0]['id'],sid);self.assertEqual(summaries[0]['mission_id'],'lib_test_m1');self.assertEqual(summaries[0]['status'],'completed');self.assertNotIn('kaffe',response.text);self.assertNotIn('snapshot',response.text)
   self.assertEqual(fresh.post(f'/api/missions/{sid}/reset',headers=h,json={'request_id':'progress-reset'}).status_code,200);self.assertEqual(fresh.get('/api/progress').json()['sessions'][0]['status'],'in_progress')
  self.c.post('/api/auth/logout',headers=h,json={});other=self.register('progressother');oh=self.hdr(other['csrf']);self.assertEqual(self.c.get('/api/progress').json()['sessions'],[]);self.assertEqual(self.c.delete(f'/api/missions/{sid}',headers=oh).status_code,404)
  self.c.post('/api/auth/logout',headers=oh,json={});login=self.c.post('/api/auth/login',headers=ORIGIN,json={'username':'progressowner','password':'correct horse battery staple'}).json();h=self.hdr(login['csrf']);self.assertEqual(self.c.delete(f'/api/missions/{sid}',headers=h).status_code,200);self.assertEqual(self.c.get('/api/progress').json()['sessions'],[])
 def test_deleted_history_cannot_be_recreated_by_retry(self):
  a=self.register('deleteme');h=self.hdr(a['csrf']);payload={'mission_id':'lib_test_m1','request_id':'start-delete'}
  self.assertEqual(self.c.post('/api/missions',headers=h,json=payload).status_code,200);self.assertEqual(self.c.delete('/api/missions',headers=h).status_code,200);self.assertEqual(self.c.post('/api/missions',headers=h,json=payload).status_code,409);export=self.c.get('/api/export');self.assertEqual(export.json()['sessions'],[]);self.assertIn('attachment',export.headers['content-disposition'])
 def test_process_restart_keeps_account_session(self):
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  base=f'http://127.0.0.1:{port}';env=os.environ.copy();env.update(BP5_PUBLIC_ORIGIN=base,BP5_ALLOWED_HOSTS=f'127.0.0.1:{port}',BP5_SECURE_COOKIE='0',BP5_COOKIE_PATH='/')
  cmd=[sys.executable,'-m','uvicorn','production:app','--app-dir',str(Path(__file__).resolve().parent),'--host','127.0.0.1','--port',str(port),'--no-access-log']
  def start():
   p=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   for _ in range(100):
    try:
     urllib.request.urlopen(base+'/health',timeout=.2).close();return p
    except Exception:time.sleep(.05)
   p.kill();p.wait();self.fail('server failed to start')
  jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));p=start()
  try:
   raw=json.dumps({'username':'restartuser','password':'correct horse battery staple','invite':st.create_invite()}).encode();req=urllib.request.Request(base+'/api/auth/register',data=raw,headers={'Content-Type':'application/json','Origin':base});self.assertEqual(opener.open(req).status,200)
   p.terminate();p.wait(timeout=5);p=start();self.assertTrue(json.load(opener.open(base+'/api/auth/session'))['authenticated'])
  finally:
   if p.poll() is None:p.terminate();p.wait(timeout=5)
 def test_ready_requires_library_and_runtime(self):
  situations=[]
  for n in range(18):
   situations.append({'id':'s'+str(n),'missions':[dict(mission,id=f'm{n}-{j}') for j in range(3)]})
  with patch.object(st,'get_library',return_value={'situations':situations}),patch.object(production.shutil,'which',return_value='/fake'),patch.object(production.Path,'is_file',return_value=True):self.assertEqual(production.readiness().status_code,200)
  situations[0]['missions'][0]=dict(mission,id='broken',steps=[])
  with patch.object(st,'get_library',return_value={'situations':situations}),patch.object(production.shutil,'which',return_value='/fake'),patch.object(production.Path,'is_file',return_value=True):self.assertEqual(production.readiness().status_code,503)
 def test_readiness_invitation_expiry_and_audio_cleanup(self):
  self.assertEqual(self.c.get('/ready').status_code,503);token=st.create_invite()
  with st.connect() as c:c.execute('UPDATE invitations SET created=? WHERE token_hash=?',(time.time()-production.INVITE_TTL-10,st.digest(token)))
  self.assertEqual(self.c.post('/api/auth/register',headers=ORIGIN,json={'username':'expiredinvite','password':'correct horse battery staple','invite':token}).status_code,400)
  ident='a'*32;stale=st.DATA/('bp5-audio-'+ident);stale.mkdir();(stale/'sample.wav').write_bytes(b'x');marker=st.DATA/('.bp5-audio-lock-'+ident);marker.write_bytes(b'1');unrelated=st.DATA/'bp5-audio-not-a-uuid';unrelated.mkdir()
  with st.audio_workspace() as active:
   (active/'recording').write_bytes(b'x');self.assertEqual(st.cleanup_abandoned_audio(),1);self.assertTrue(active.exists());self.assertFalse(stale.exists());self.assertTrue(unrelated.exists())
  self.assertFalse(active.exists());unrelated.rmdir()
 def test_invitation_and_explicit_legacy_import(self):
  invite_file=Path(TMP.name)/'private-invite.txt';cmd=[sys.executable,str(Path(__file__).with_name('manage.py')),'create-invite','--output',str(invite_file)];r=subprocess.run(cmd,capture_output=True,text=True,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));token=invite_file.read_text().strip();self.assertNotIn(token,r.stdout);self.assertGreater(len(token),20)
  a=self.c.post('/api/auth/register',headers=ORIGIN,json={'username':'importowner','password':'correct horse battery staple','invite':token});self.assertEqual(a.status_code,200);self.assertEqual(self.c.post('/api/auth/register',headers=ORIGIN,json={'username':'anotherowner','password':'correct horse battery staple','invite':token}).status_code,400)
  legacy=Path(TMP.name)/'legacy-example.db'
  with closing(sqlite3.connect(legacy)) as c:c.execute('CREATE TABLE sessions(id TEXT,payload TEXT)');c.execute('INSERT INTO sessions VALUES(?,?)',('old1',json.dumps({'id':'old1','scenario_id':'old'})));c.commit()
  cmd=[sys.executable,str(Path(__file__).with_name('manage.py')),'import-legacy','--username','importowner','--confirm-owner','importowner','--legacy-db',str(legacy)];subprocess.run(cmd,capture_output=True,text=True,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertEqual(self.c.get('/api/legacy').json()['sessions'][0]['id'],'old1')
 def test_history_stream_disconnect_releases_capacity(self):
  a=self.register('streamowner')
  with st.connect() as c:uid=c.execute('SELECT id FROM users WHERE username=?',('streamowner',)).fetchone()['id']
  response=production.history_response(uid,'missions');other=production.history_response(uid,'export')
  with self.assertRaises(production.HTTPException) as blocked:production.history_response(uid,'legacy')
  self.assertEqual(blocked.exception.status_code,429)
  async def simulate():
   async def send(message):
    if message['type']=='http.response.body':raise OSError('client disconnected')
   async def receive():return {'type':'http.request','body':b'','more_body':False}
   try:await response({'type':'http','asgi':{'spec_version':'2.4'}},receive,send)
   except Exception:pass
  asyncio.run(simulate())
  async def finish_other():
   async def send(message):pass
   async def receive():return {'type':'http.request','body':b'','more_body':False}
   await other({'type':'http','asgi':{'spec_version':'2.4'}},receive,send)
  asyncio.run(finish_other())
  self.assertTrue(production.HISTORY_STREAM_LOCK.acquire(False));self.assertTrue(production.HISTORY_STREAM_LOCK.acquire(False));self.assertFalse(production.HISTORY_STREAM_LOCK.acquire(False));production.HISTORY_STREAM_LOCK.release();production.HISTORY_STREAM_LOCK.release()
 def test_full_authored_library_through_http(self):
  actual=Path(__file__).resolve().parent.parent;a=self.register('librarytester');h=self.hdr(a['csrf'])
  with patch.object(st,'ROOT',actual):
   lib=st.get_library();missions=[m for sit in lib['situations'] for m in sit['missions']];self.assertEqual(len(missions),54)
   for mission in missions:
    started=self.c.post('/api/missions',headers=h,json={'mission_id':mission['id'],'request_id':'start-'+mission['id']});self.assertEqual(started.status_code,200,(mission['id'],started.text));session=started.json()['session'];steps={x['id']:x for x in mission['steps']};turn_number=0
    while session['status']!='completed':
     turn_number+=1;self.assertLessEqual(turn_number,len(steps));step=steps[session['current_step']];text=step['intents'][0]['examples_sv'][0]
     r=self.c.post('/api/missions/'+session['id']+'/turn',headers=h,json={'request_id':f'turn-{turn_number}','text':text});self.assertEqual(r.status_code,200,(mission['id'],step['id'],r.text));self.assertTrue(r.json()['matched'],(mission['id'],step['id'],text));session=r.json()['session']
    self.assertTrue(set(mission['completion_objectives']).issubset(session['completed_objectives']))
 def test_legacy_import_rejects_invalid_atomically(self):
  self.register('importguard')
  for case in ('nan','infinity','huge','count','malformed'):
   db=Path(TMP.name)/('legacy-'+case+'.db')
   with closing(sqlite3.connect(db)) as c:
    c.execute('CREATE TABLE sessions(id TEXT,payload TEXT)');c.execute('INSERT INTO sessions VALUES(?,?)',('safe','{"id":"safe"}'))
    if case=='count':c.executemany('INSERT INTO sessions VALUES(?,?)',[(str(i),'{}') for i in range(200)])
    else:
     payload={'nan':'{"value":NaN}','infinity':'{"value":1e999}','huge':'{"value":"'+'x'*131072+'"}','malformed':'{"value":'}[case];c.execute('INSERT INTO sessions VALUES(?,?)',('bad',payload))
    c.commit()
   cmd=[sys.executable,str(Path(__file__).with_name('manage.py')),'import-legacy','--username','importguard','--confirm-owner','importguard','--legacy-db',str(db)];r=subprocess.run(cmd,capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertNotEqual(r.returncode,0,case);self.assertEqual(self.c.get('/api/legacy').json()['sessions'],[],case)
 def test_account_deletion_removes_owner_data(self):
  a=self.register('removeaccount');h=self.hdr(a['csrf']);self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'create'});r=self.c.request('DELETE','/api/account',headers=h,json={'password':'correct horse battery staple'});self.assertEqual(r.status_code,200,r.text);self.assertFalse(self.c.get('/api/auth/session').json()['authenticated'])
  with st.connect() as c:self.assertIsNone(c.execute('SELECT 1 FROM users WHERE username=?',('removeaccount',)).fetchone());self.assertIsNone(c.execute('SELECT 1 FROM attempts WHERE subject=?',(st.digest('removeaccount'),)).fetchone())
 def test_creation_tombstones_are_bounded(self):
  a=self.register('boundedcreation');h=self.hdr(a['csrf'])
  with patch.object(production,'MAX_CREATION_REQUESTS',1):
   self.assertEqual(self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'one'}).status_code,200);self.assertEqual(self.c.delete('/api/missions',headers=h).status_code,200);self.assertEqual(self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'two'}).status_code,409)
 def test_login_cannot_survive_concurrent_password_recovery(self):
  a=self.register('raceuser');code=a['recovery_codes'][0];verified=threading.Event();release=threading.Event();original=production.password_verify;result=[]
  def gated(password,encoded):
   ok=original(password,encoded)
   if password=='correct horse battery staple':verified.set();release.wait(5)
   return ok
  def attempt():
   with TestClient(production.app) as other:result.append(other.post('/api/auth/login',headers=ORIGIN,json={'username':'raceuser','password':'correct horse battery staple'}))
  with patch.object(production,'password_verify',side_effect=gated):
   thread=threading.Thread(target=attempt);thread.start()
   try:
    self.assertTrue(verified.wait(4));r=self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'raceuser','recovery_code':code,'new_password':'another correct horse battery'});self.assertEqual(r.status_code,200,r.text)
   finally:release.set();thread.join(5)
  self.assertFalse(thread.is_alive());self.assertEqual(result[0].status_code,401);self.assertNotIn('bp5_session',result[0].cookies)
 def test_account_deletion_cannot_survive_concurrent_recovery(self):
  a=self.register('deleterace');h=self.hdr(a['csrf']);code=a['recovery_codes'][0];verified=threading.Event();release=threading.Event();original=production.password_verify;result=[]
  def gated(password,encoded):
   ok=original(password,encoded)
   if password=='correct horse battery staple':verified.set();release.wait(5)
   return ok
  def attempt():result.append(self.c.request('DELETE','/api/account',headers=h,json={'password':'correct horse battery staple'}))
  with patch.object(production,'password_verify',side_effect=gated):
   thread=threading.Thread(target=attempt);thread.start()
   try:
    self.assertTrue(verified.wait(4));r=self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'deleterace','recovery_code':code,'new_password':'another correct horse battery'});self.assertEqual(r.status_code,200,r.text)
   finally:release.set();thread.join(5)
  self.assertFalse(thread.is_alive());self.assertEqual(result[0].status_code,401)
  with st.connect() as c:self.assertIsNotNone(c.execute('SELECT 1 FROM users WHERE username=?',('deleterace',)).fetchone())
 def test_audio_cannot_start_after_account_deletion(self):
  a=self.register('audioafterdelete');h=self.hdr(a['csrf']);token=self.c.cookies.get(production.COOKIE)
  with st.connect() as c:uid=c.execute('SELECT id FROM users WHERE username=?',('audioafterdelete',)).fetchone()['id']
  ready=threading.Event();release=threading.Event();result=[];request=types.SimpleNamespace(headers={'x-audio-job':'late-audio-job'},cookies={production.COOKIE:token})
  def attempt():
   ready.set();release.wait(5)
   try:production.begin_audio({'user_id':uid},request);result.append('admitted')
   except production.HTTPException as e:result.append(e.status_code)
  worker=threading.Thread(target=attempt);worker.start()
  try:
   self.assertTrue(ready.wait(2));self.assertEqual(self.c.request('DELETE','/api/account',headers=h,json={'password':'correct horse battery staple'}).status_code,200)
  finally:release.set();worker.join(5)
  self.assertEqual(result,[401]);self.assertNotIn('late-audio-job',production.AUDIO_JOBS)
  with st.connect() as c:self.assertIsNone(c.execute('SELECT 1 FROM attempts WHERE subject=?',(st.digest(uid),)).fetchone())
 def test_regenerate_recovery_codes_revokes_old_codes(self):
  a=self.register('regencodes');h=self.hdr(a['csrf']);old=a['recovery_codes'][0]
  self.assertEqual(self.c.post('/api/auth/recovery-codes',headers=ORIGIN,json={'password':'correct horse battery staple'}).status_code,403)
  self.assertEqual(self.c.post('/api/auth/recovery-codes',headers=h,json={'password':'wrong password'}).status_code,401)
  r=self.c.post('/api/auth/recovery-codes',headers=h,json={'password':'correct horse battery staple'});self.assertEqual(r.status_code,200,r.text);new=r.json()['recovery_codes'];self.assertEqual(len(new),8);self.assertNotIn(old,new)
  self.assertEqual(self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'regencodes','recovery_code':old,'new_password':'another correct horse battery'}).status_code,400)
  self.assertEqual(self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'regencodes','recovery_code':new[0],'new_password':'another correct horse battery'}).status_code,200)
 def test_sessions_expire_and_are_capped(self):
  self.register('sessioncap');first=self.c.cookies.get(production.COOKIE)
  with st.connect() as c:
   uid=c.execute('SELECT id FROM users WHERE username=?',('sessioncap',)).fetchone()['id'];c.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',(st.digest('expired-token'),uid,st.digest('csrf'),time.time()-10))
  newest=None
  with patch.object(production,'rate',return_value=None):
   for _ in range(11):
    with TestClient(production.app) as other:
     r=other.post('/api/auth/login',headers=ORIGIN,json={'username':'sessioncap','password':'correct horse battery staple'});self.assertEqual(r.status_code,200);newest=other.cookies.get(production.COOKIE)
  with st.connect() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM auth_sessions WHERE user_id=?',(uid,)).fetchone()[0],production.MAX_AUTH_SESSIONS);self.assertIsNone(c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(st.digest('expired-token'),)).fetchone());self.assertIsNone(c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(st.digest(first),)).fetchone());self.assertIsNotNone(c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(st.digest(newest),)).fetchone())
 def test_new_mission_rate_excludes_retries(self):
  a=self.register('missionratetest');h=self.hdr(a['csrf']);payload={'mission_id':'lib_test_m1','request_id':'one'}
  with patch.object(production,'MAX_MISSION_CREATIONS_PER_HOUR',1):
   self.assertEqual(self.c.post('/api/missions',headers=h,json=payload).status_code,200);self.assertEqual(self.c.post('/api/missions',headers=h,json=payload).status_code,200);self.assertEqual(self.c.post('/api/missions',headers=h,json={'mission_id':'lib_test_m1','request_id':'two'}).status_code,429)
 def test_blocked_ip_does_not_grow_rate_store(self):
  key=st.digest('login-ip:testclient');now=time.time()
  with st.connect() as c:c.executemany('INSERT INTO attempts(key,occurred,subject) VALUES(?,?,NULL)',[(key,now)]*40);before=c.execute('SELECT count(*) FROM attempts').fetchone()[0]
  for i in range(20):self.assertEqual(self.c.post('/api/auth/login',headers=ORIGIN,json={'username':'otheruser'+str(i),'password':'x'}).status_code,429)
  with st.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM attempts').fetchone()[0],before)
  with patch.object(production,'MAX_RATE_ROWS',before):self.assertEqual(self.c.post('/api/auth/register',headers=ORIGIN,json={'username':'anotheruser','password':'correct horse battery staple','invite':'x'*32}).status_code,429)
 def test_recovery_one_use_and_session_revocation(self):
  a=self.register('recoverme');code=a['recovery_codes'][0];r=self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'recoverme','recovery_code':code,'new_password':'another correct horse battery'});self.assertEqual(r.status_code,200);self.assertFalse(self.c.get('/api/auth/session').json()['authenticated']);self.assertEqual(self.c.post('/api/auth/recover',headers=ORIGIN,json={'username':'recoverme','recovery_code':code,'new_password':'another correct horse battery'}).status_code,400);self.assertEqual(self.c.post('/api/auth/login',headers=ORIGIN,json={'username':'recoverme','password':'another correct horse battery'}).status_code,200)
 @unittest.skipUnless(os.getenv('BP5_TEST_LOCAL_AUDIO')=='1','requires local Windows audio runtime')
 def test_real_local_audio_pipeline(self):
  a=self.register('voicetest');h=self.hdr(a['csrf']);h['X-Audio-Job']='speech-test-123';r=self.c.post('/api/speech',headers=h,json={'text':'Hej, jag vill ha en kaffe tack.'});self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.content.startswith(b'RIFF'))
  wav=st.DATA/'test-audio.wav';m4a=st.DATA/'test-audio.m4a';wav.write_bytes(r.content);subprocess.run([os.environ['BP5_FFMPEG'],'-v','error','-y','-i',str(wav),str(m4a)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));h['X-Audio-Job']='transcribe-test-123';h['Content-Type']='audio/mp4';r=self.c.post('/api/transcribe',headers=h,content=m4a.read_bytes());self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['text']);print('REAL_M4A_ASR',r.json()['text'].encode('unicode_escape'));wav.unlink();m4a.unlink()
 def test_audio_cancel_owner_only(self):
  a=self.register('audiouser');h=self.hdr(a['csrf']);uid=None
  with st.connect() as db: uid=db.execute('SELECT id FROM users WHERE username=?',('audiouser',)).fetchone()['id']
  jid='audio-job-test';job={'user_id':uid,'cancelled':False,'process':None};production.AUDIO_JOBS[jid]=job;finished=[]
  def run():
   try:production.run_audio(job,[sys.executable,'-c','import time;time.sleep(20)'],timeout=30)
   except RuntimeError:finished.append('cancelled')
  worker=threading.Thread(target=run);worker.start()
  try:
   for _ in range(100):
    if job['process'] is not None:break
    time.sleep(.02)
   self.assertIsNotNone(job['process']);self.c.post('/api/auth/logout',headers=h,json={});b=self.register('audioother');bh=self.hdr(b['csrf']);self.assertEqual(self.c.delete('/api/audio/jobs/'+jid,headers=bh).status_code,404);self.assertFalse(job['cancelled']);self.c.post('/api/auth/logout',headers=bh,json={});login=self.c.post('/api/auth/login',headers=ORIGIN,json={'username':'audiouser','password':'correct horse battery staple'});h=self.hdr(login.json()['csrf'])
   self.assertEqual(self.c.delete('/api/audio/jobs/'+jid,headers=h).status_code,200);worker.join(5);self.assertFalse(worker.is_alive());self.assertEqual(finished,['cancelled'])
  finally:
   if job['process'] and job['process'].poll() is None:job['process'].kill()
   worker.join(5);production.AUDIO_JOBS.pop(jid,None)
if __name__=='__main__':unittest.main()
