import hashlib,json,os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import language_checker as checker
from language_process import WorkerSupervisor,WorkerError,WorkerBusy

FAKE=r'''import json,os,sys,time,subprocess
mode=sys.argv[1]
def answer(value):
 sys.stdout.write(json.dumps(value)+'\n');sys.stdout.flush()
for line in sys.stdin:
 data=json.loads(line)
 if data['op']=='init':
  if mode=='badinit':answer({'ready':True,'protocol':2})
  else:answer({'ready':True,'protocol':1})
  continue
 if mode=='child':
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));open(sys.argv[2],'w').write(str(child.pid));time.sleep(60)
 elif mode=='hang':time.sleep(60)
 elif mode=='crash':os._exit(3)
 elif mode=='flood':sys.stdout.write('x'*20000);sys.stdout.flush();time.sleep(60)
 elif mode=='partial':sys.stdout.write('{');sys.stdout.flush();time.sleep(60)
 elif mode=='badjson':sys.stdout.write('not-json\n');sys.stdout.flush()
 elif mode=='wrongseq':answer({'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.9,'swedish_probability':.9,'token_counts':[20,20],'truncated':False,'seq':data['seq']+1})
 elif mode=='slow':time.sleep(.5);answer({'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.9,'swedish_probability':.9,'token_counts':[20,20],'truncated':False,'seq':data['seq']})
 else:answer({'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.9,'swedish_probability':.9,'token_counts':[20,20],'truncated':False,'seq':data['seq']})
'''
class CheckerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.fake=self.root/'fake.py';self.fake.write_text(FAKE,encoding='utf8');self.workers=[]
 def tearDown(self):
  for w in self.workers:
   try:w.close()
   except WorkerError:pass
  self.tmp.cleanup()
 def worker(self,mode,timeout=.3):
  w=WorkerSupervisor([sys.executable,str(self.fake),mode],{},timeout=timeout,startup_timeout=3);self.workers.append(w);return w
 def test_real_subprocess_handshake_and_reuse(self):
  w=self.worker('ok');self.assertTrue(w.ready());pid=w._proc.pid;self.assertEqual(w.request({'op':'score'})['scores'],[.9,.1]);self.assertEqual(w._proc.pid,pid)
 def test_bad_handshake_never_ready(self):
  w=self.worker('badinit');self.assertFalse(w.ready());self.assertIsNone(w._proc)
 def test_failed_reap_keeps_handle_and_blocks_replacement(self):
  import subprocess
  w=self.worker('ok');p=Mock();p.pid=12345;p.wait.side_effect=[subprocess.TimeoutExpired('worker',5),0];p.poll.return_value=None;w._proc=p;w._initialized=True
  with patch('language_process.os.name','nt'),patch('language_process.subprocess.run',return_value=Mock(returncode=0)):
   with self.assertRaises(WorkerError):w.close()
   self.assertIs(w._proc,p);self.assertFalse(w._initialized)
   with patch('language_process.subprocess.Popen') as spawn:
    self.assertFalse(w.ready());spawn.assert_not_called()
   w.close();self.assertIsNone(w._proc)
 def test_failed_windows_tree_kill_fails_closed(self):
  w=self.worker('ok');p=Mock();p.pid=12345;p.wait.return_value=0;p.poll.return_value=None;w._proc=p
  with patch('language_process.os.name','nt'),patch('language_process.subprocess.run',return_value=Mock(returncode=1)):
   with self.assertRaises(WorkerError):w.close()
  p.kill.assert_called_once();self.assertIsNone(w._proc);self.assertFalse(w.ready())
 def test_timeout_no_newline_flood_and_crash_are_reaped(self):
  for mode in ('hang','partial','flood','crash','badjson','wrongseq'):
   with self.subTest(mode=mode):
    w=self.worker(mode);self.assertTrue(w.ready());proc=w._proc;t=time.monotonic()
    with self.assertRaises(WorkerError):w.request({'op':'score'})
    self.assertLess(time.monotonic()-t,8);self.assertIsNotNone(proc.poll());self.assertIsNone(w._proc)
 def test_timeout_terminates_spawned_child_process(self):
  pidfile=self.root/'child.pid';w=WorkerSupervisor([sys.executable,str(self.fake),'child',str(pidfile)],{},timeout=.7,startup_timeout=3);self.workers.append(w);self.assertTrue(w.ready())
  with self.assertRaises(WorkerError):w.request({'op':'score'})
  self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
  def alive():
   if os.name=='nt':
    import ctypes
    handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
    if not handle:return False
    code=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code));ctypes.windll.kernel32.CloseHandle(handle);return code.value==259
   try:
    stat=Path(f'/proc/{pid}/stat')
    if stat.exists() and stat.read_text().split()[2]=='Z':return False
    os.kill(pid,0);return True
   except ProcessLookupError:return False
  for _ in range(30):
   if not alive():break
   time.sleep(.1)
  self.assertFalse(alive(),'worker descendant survived deadline')
 def test_busy_does_not_queue(self):
  w=self.worker('slow',timeout=2);self.assertTrue(w.ready());finished=[];t=threading.Thread(target=lambda:finished.append(w.request({'op':'score'})));t.start();time.sleep(.1)
  with self.assertRaises(WorkerBusy):w.request({'op':'score'})
  self.assertTrue(w.ready(),'healthy inference must not fail service readiness')
  t.join(3);self.assertEqual(len(finished),1)
 def test_limits_and_decisions(self):
  self.assertEqual(checker.choose([.9,.2],['a','b'],.8,.2),('a',.9));self.assertIsNone(checker.choose([.9,.85],['a','b'],.8,.2)[0]);self.assertIsNone(checker.choose([.3],['a'],.8,.2)[0]);self.assertEqual(checker.choose([.8],['a'],.5,.95),('a',.8));self.assertIsNone(checker.choose([.5,.5],['a','b'],.4,0)[0])
  for scores,ids in [([float('nan')],['a']),([True],['a']),([.4,.3],['a','a']),([.4],[])]:
   with self.assertRaises(ValueError):checker.choose(scores,ids,.5,.1)
  w=self.worker('ok');self.assertTrue(w.ready())
  with self.assertRaises(WorkerError):w.request({'op':'score','text':'a'*40000})
 def test_checker_validates_artifacts_language_and_pinned_format(self):
  model=self.root/'model';token=self.root/'token';lid=self.root/'lid';source=self.root/'source';vocab=self.root/'vocab';model.write_bytes(b'model');token.write_bytes(b'token');lid.write_bytes(b'lid');source.write_bytes(b'source');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();vocab.write_text(json.dumps({'schema_version':'1','source_sha256':sha(source),'words':['en','bulle','tack','kaffe']}));config={'model':str(model),'model_sha256':sha(model),'tokenizer':str(token),'tokenizer_sha256':sha(token),'language_model':str(lid),'language_model_sha256':sha(lid),'vocabulary':str(vocab),'vocabulary_sha256':sha(vocab),'vocabulary_source':str(source),'vocabulary_source_sha256':sha(source),'runtime_hashes':{k:'0'*64 for k in ('python','onnxruntime','tokenizers','numpy','fasttext')},'max_tokens':128,'threads':1};c=checker.Checker(config,.7,.2,'test-revision');self.addCleanup(c.close)
  fake=self.worker('ok');c.worker=fake;step={'id':'one','objective':'request','prompt_sv':'Vad vill du ha?','intents':[{'id':'a','meaning_sv':'Jag vill ha kaffe.'},{'id':'b','meaning_sv':'Jag vill ha te.'}]};self.assertTrue(c.ready());r=c.check({},step,[],'En kaffe tack');self.assertEqual(r['intent_id'],'a');self.assertEqual(r['checker_revision'],'test-revision')
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'en','language_probability':.95,'swedish_probability':.001,'token_counts':[20,20],'truncated':False}):self.assertIsNone(c.check({},step,[],'I want coffee')['intent_id'])
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'de','language_probability':.95,'swedish_probability':.001,'token_counts':[20,20],'truncated':False}):self.assertIsNone(c.check({},step,[],'Ich möchte Kaffee')['intent_id'])
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'en','language_probability':.95,'swedish_probability':.001,'token_counts':[20,20],'truncated':False}):self.assertEqual(c.check({},{**step,'objective':'confirm'},[],'OK')['intent_id'],'a')
  c.context_resolver=lambda mission,current,history:'Kan du hämta paketet i morgon?'
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.95,'swedish_probability':.95,'token_counts':[20,20],'truncated':False}) as request:
   c.check({},step,[],'Ja tack');self.assertIn('Kan du hämta paketet i morgon?',request.call_args.args[0]['pairs'][0][0])
  def unavailable(*args):raise ValueError('ambiguous')
  c.context_resolver=unavailable;self.assertRaises(checker.CheckerUnavailable,c.check,{},step,[],'Ja tack');c.context_resolver=None
  c.premise_builder=lambda mission,current,history,text:'Erbjudande: Hämta paketet.\nFråga: Går det bra?\nSvar: '+text
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.95,'swedish_probability':.95,'token_counts':[20,20],'truncated':False}) as request:
   c.check({},step,[],'Ja tack');self.assertEqual(request.call_args.args[0]['pairs'][0][0],'Erbjudande: Hämta paketet.\nFråga: Går det bra?\nSvar: Ja tack')
  c.premise_builder=lambda *args:'Svar: ja';self.assertRaises(checker.CheckerUnavailable,c.check,{},step,[],'Ja tack');c.premise_builder=None
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'zh','language_probability':.152,'swedish_probability':.099,'token_counts':[20,20],'truncated':False}):
   supported=c.check({},step,[],'En bulle tack.');self.assertEqual(supported['intent_id'],'a');self.assertEqual(supported['language'],'zh');self.assertTrue(supported['language_supported']);self.assertEqual(supported['language_evidence'],'lexical_support')
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'da','language_probability':.4,'swedish_probability':.035,'token_counts':[20,20],'truncated':False}):
   unsupported=c.check({},step,[],'En kaffe tak.');self.assertIsNone(unsupported['intent_id']);self.assertFalse(unsupported['language_supported']);self.assertEqual(unsupported['language_evidence'],'foreign_veto')
  with patch.object(fake,'request',return_value={'ok':True,'scores':[.9,.1],'language':'sv','language_probability':.95,'swedish_probability':.95,'token_counts':[20,21],'truncated':False}):
   traced=c.check({},step,[],'En bulle tack.',evaluation_trace=True);self.assertEqual(traced['evaluation_trace']['input_characters'],len('En bulle tack.'));self.assertEqual(traced['evaluation_trace']['token_counts'],[20,21]);self.assertFalse(traced['evaluation_trace']['truncated']);self.assertEqual(len(traced['evaluation_trace']['input_sha256']),64)
  with patch.object(fake,'request',return_value={'ok':False,'error':'token_limit','token_counts':[513,514],'truncated':False}):
   with self.assertRaises(checker.CheckerInputTooLong) as exc:c.check({},step,[],'En bulle tack.',evaluation_trace=True)
   self.assertEqual(exc.exception.token_counts,(513,514));self.assertEqual(exc.exception.evaluation_trace['input_characters'],len('En bulle tack.'));self.assertFalse(exc.exception.evaluation_trace['truncated'])
  model.write_bytes(b'tampered');self.assertFalse(c.ready());self.assertRaises(checker.CheckerUnavailable,c.check,{},step,[],'En kaffe tack')
 def test_default_module_unavailable(self):
  self.assertFalse(checker.ready());self.assertRaises(checker.CheckerUnavailable,checker.check,{}, {}, [], 'hej')
if __name__=='__main__':unittest.main()
