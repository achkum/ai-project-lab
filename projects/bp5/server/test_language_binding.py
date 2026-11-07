import copy,hashlib,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import language_binding as b
from language_checker import Checker,CheckerUnavailable,ContextUnknown

class ManifestBindingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.project=self.root/'project';self.artifacts=self.root/'artifacts';(self.project/'server').mkdir(parents=True);(self.project/'content').mkdir();self.artifacts.mkdir()
  self.lib=self.project/'content/library.json';self.lib.write_text(json.dumps({'content_version':'fixture-v1','situations':[]}));self.sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();self.vocab=self.project/'server/swedish_support_vocabulary.json';self.vocab.write_text(json.dumps({'schema_version':'1','source_sha256':self.sha(self.lib),'words':['ja','nej','tack']}))
  names=['model.onnx','tokenizer.json','language.bin','python.bin','ort.bin','tokenizers.bin','numpy.bin','fasttext.bin']
  for name in names:
   if name=='python.bin':shutil.copyfile(sys.executable,self.artifacts/name)
   else:(self.artifacts/name).write_bytes(('fixture-'+name).encode())
  self.items=[{'path':name,'sha256':self.sha(self.artifacts/name)} for name in names]
  self.cfg={'model':'model.onnx','tokenizer':'tokenizer.json','language_model':'language.bin','runtime_artifacts':{'python':'python.bin','onnxruntime':'ort.bin','tokenizers':'tokenizers.bin','numpy':'numpy.bin','fasttext':'fasttext.bin'},'library_sha256':self.sha(self.lib),'library_version':'fixture-v1','vocabulary_sha256':self.sha(self.vocab),'checkpoint_id':'fixture-checkpoint','base_model_revision':b.TOKENIZER_REVISION,'tokenizer_revision':b.TOKENIZER_REVISION,'calibration_source':'fixture-dev','threshold':.8,'margin':.2,'max_tokens':512,'threads':1,'timeout_seconds':15,'startup_timeout_seconds':30,'label_mapping':{'entailment':0,'neutral':1,'contradiction':2},'premise_format':'offer-question-reply-v1','hypothesis_format':'meaning-sv-v1','language_policy':'fasttext-vocab-v1'}
  self.env={'BP5_SEMANTIC_REQUIRED':'1','BP5_SEMANTIC_BURST_UNITS':'48','BP5_SEMANTIC_REFILL_UNITS_PER_MINUTE':'24','BP5_SEMANTIC_COOLDOWN_PERCENT':'100'}
  self.manifest={'schema_version':1,'adapter':{'entrypoint':'server/language_checker.py:check','configuration':self.cfg,'execution_mode':'production_adapter','environment':self.env,'runtime_platform':'linux','evaluation_target':'identical_linux_container'},'artifacts':self.items};self.path=self.project/'LANGUAGE_CHECKER_MANIFEST.json';self.write()
  self.patch=patch.dict(os.environ,{**self.env,'BP5_LANGUAGE_ARTIFACT_ROOT':str(self.artifacts)});self.patch.start()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def write(self):self.path.write_text(json.dumps(self.manifest),encoding='utf8')
 def load(self):return b._load_configuration(self.project,self.artifacts)
 def invalid(self):
  self.write()
  with self.assertRaises((ValueError,TypeError,KeyError,OSError)):self.load()
 def test_fixture_manifest_resolves_exact_trained_format(self):
  info=self.load();self.assertEqual(info['config']['max_tokens'],512);self.assertEqual(info['config']['runtime_hashes']['python'],self.sha(Path(sys.executable)));self.assertEqual(info['threshold'],.8);self.assertEqual(info['revision'],'fixture-checkpoint')
  mission={'start_step':'one','opening_sv':'Vill du ha kaffe?','steps':[{'id':'one','intents':[]}]};step={'id':'one','prompt_sv':'Vill du ha kaffe?'}
  self.assertEqual(b._premise(mission,step,[],'Nej, inte kaffe.'),'Erbjudande: Vill du ha kaffe?\nFråga: Vill du ha kaffe?\nSvar: Nej, inte kaffe.')
 def test_module_entrypoints_bind_only_operator_fixture(self):
  import language_checker
  class FixtureChecker:
   def __init__(self,*args,**kwargs):self.kwargs=kwargs
   def ready(self):return True
   def check(self,*args,**kwargs):return {'fixture':True,'trace_requested':kwargs.get('evaluation_trace')}
   def close(self):pass
  with patch.object(b,'PROJECT',self.project),patch.object(b,'Checker',FixtureChecker),patch.object(b,'_bound',None),patch.object(sys,'platform','linux'),patch.dict(os.environ,{'BP5_LANGUAGE_ARTIFACT_ROOT':str(self.artifacts)}):
   self.assertTrue(language_checker.ready());out=language_checker.check({}, {}, [], 'hej',evaluation_trace=True);self.assertEqual(out,{'fixture':True,'trace_requested':True});self.assertIs(b._bound.checker.kwargs['premise_builder'],b._premise)
   with b._lock:self.assertTrue(language_checker.ready(),'initialized binding contention must not fail readiness')
   self.path.unlink();self.assertFalse(language_checker.ready())
   with self.assertRaises(CheckerUnavailable):language_checker.check({}, {}, [], 'hej')
 def test_missing_ambiguous_context_is_unknown_without_inference(self):
  mission={'start_step':'one','opening_sv':'Hej','steps':[{'id':'one','intents':[{'next_step':'two','reply_sv':'Måndag?'},{'next_step':'two','reply_sv':'Tisdag?'}]},{'id':'two','prompt_sv':'Går det bra?','intents':[{'id':'yes','meaning_sv':'Ja.'}]}]};step=mission['steps'][1];info=self.load();candidate=Checker(info['config'],.8,.2,'fixture',premise_builder=b._premise)
  with patch.object(candidate,'ready',return_value=False):
   with self.assertRaises(CheckerUnavailable):candidate.check(mission,step,[],'Ja.')
  with patch.object(candidate,'ready',return_value=True):out=candidate.check(mission,step,[],'Ja.',evaluation_trace=True)
  self.assertIsNone(out['intent_id']);self.assertEqual(out['language_evidence'],'unresolved');self.assertTrue(out['evaluation_trace']['context_unresolved']);self.assertEqual(out['evaluation_trace']['token_counts'],[]);candidate.close()
 def test_rejects_escape_duplicate_artifact_and_hash_mismatch(self):
  original=copy.deepcopy(self.manifest)
  for edit in ('traversal','absolute','backslash','duplicate','wronghash'):
   self.manifest=copy.deepcopy(original)
   if edit=='traversal':self.manifest['artifacts'][0]['path']='../outside'
   elif edit=='absolute':self.manifest['artifacts'][0]['path']='/tmp/outside'
   elif edit=='backslash':self.manifest['artifacts'][0]['path']='x\\outside'
   elif edit=='duplicate':self.manifest['artifacts'].append(copy.deepcopy(self.manifest['artifacts'][0]))
   else:self.manifest['artifacts'][0]['sha256']='0'*64
   with self.subTest(edit=edit):self.invalid()
 def test_rejects_unbound_artifacts_labels_and_configuration(self):
  original=copy.deepcopy(self.manifest)
  for edit in ('missing-role','role-alias','labels','bool-label','token-cap','tokenizer-revision','base-revision','format','extra-config','bad-threshold','wrong-library','wrong-version','wrong-vocab'):
   self.manifest=copy.deepcopy(original);c=self.manifest['adapter']['configuration']
   if edit=='missing-role':c['runtime_artifacts']['numpy']='missing.bin'
   elif edit=='role-alias':c['tokenizer']=c['model']
   elif edit=='labels':c['label_mapping']['neutral']=0
   elif edit=='bool-label':c['label_mapping']['neutral']=True
   elif edit=='token-cap':c['max_tokens']=128
   elif edit=='tokenizer-revision':c['tokenizer_revision']='wrong'
   elif edit=='base-revision':c['base_model_revision']='wrong'
   elif edit=='format':c['premise_format']='wrong'
   elif edit=='extra-config':c['unexpected']=True
   elif edit=='bad-threshold':c['threshold']=float('nan')
   elif edit=='wrong-library':c['library_sha256']='0'*64
   elif edit=='wrong-version':c['library_version']='other'
   else:c['vocabulary_sha256']='0'*64
   with self.subTest(edit=edit):self.invalid()
 def test_environment_and_platform_declaration_are_strict(self):
  original=copy.deepcopy(self.manifest)
  for edit in ('disabled','missing-budget','wrong-budget','windows','wrong-entry','extra-env'):
   self.manifest=copy.deepcopy(original);a=self.manifest['adapter']
   if edit=='disabled':a['environment']['BP5_SEMANTIC_REQUIRED']='0'
   elif edit=='missing-budget':a['environment'].pop('BP5_SEMANTIC_BURST_UNITS')
   elif edit=='wrong-budget':a['environment']['BP5_SEMANTIC_BURST_UNITS']='49'
   elif edit=='windows':a['runtime_platform']='windows'
   elif edit=='wrong-entry':a['entrypoint']='server/other.py:check'
   else:a['environment']['EXTRA']='1'
   with self.subTest(edit=edit):self.invalid()
  self.manifest=copy.deepcopy(original);self.write()
  with patch.dict(os.environ,{'BP5_SEMANTIC_REQUIRED':'0'}):
   with self.assertRaises(ValueError):self.load()
 def test_duplicate_keys_and_oversized_manifest_are_rejected(self):
  self.path.write_text('{"schema_version":1,"schema_version":1}');
  with self.assertRaises(ValueError):self.load()
  self.path.write_bytes(b' '*65537)
  with self.assertRaises(ValueError):self.load()
 def test_changed_manifest_or_artifact_invalidates_existing_binding(self):
  info=self.load();bound=b.Binding(info)
  try:
   self.assertTrue(bound.valid())
   with patch.dict(os.environ,{'BP5_SEMANTIC_REQUIRED':'0'}):self.assertFalse(bound.valid())
   with patch.dict(os.environ,{'BP5_SEMANTIC_BURST_UNITS':'49'}):self.assertFalse(bound.valid())
   with patch.dict(os.environ,{'BP5_LANGUAGE_ARTIFACT_ROOT':str(self.project)}):self.assertFalse(bound.valid())
   self.path.write_text(self.path.read_text()+' ');self.assertFalse(bound.valid());self.write();self.assertTrue(bound.valid());(self.artifacts/'model.onnx').write_bytes(b'changed');self.assertFalse(bound.valid())
  finally:bound.close()
 def test_revocation_during_inference_discards_result(self):
  bound=b.Binding(self.load())
  def mutate(*args,**kwargs):self.path.write_text(self.path.read_text()+' ');return {'intent_id':'a'}
  try:
   with patch.object(bound.checker,'check',side_effect=mutate):
    with self.assertRaises(CheckerUnavailable):bound.check({}, {}, [], 'hej')
  finally:bound.close()
 def test_symlink_artifact_rejected_when_supported(self):
  link=self.artifacts/'link.onnx'
  try:link.symlink_to(self.artifacts/'model.onnx')
  except OSError:self.skipTest('symlink privilege unavailable')
  self.manifest['artifacts'][0]['path']='link.onnx';self.invalid()
 def test_hardlinked_artifact_rejected(self):
  try:os.link(self.artifacts/'model.onnx',self.root/'outside-alias')
  except OSError:self.skipTest('hardlink unavailable')
  with self.assertRaises(ValueError):self.load()
 def test_root_link_swap_invalidates_before_using_cached_artifacts(self):
  bound=b.Binding(self.load());original=Path.is_symlink
  try:
   with patch.object(Path,'is_symlink',lambda p:p==self.artifacts or original(p)):
    self.assertFalse(bound.valid())
    with self.assertRaises(ValueError):self.load()
  finally:bound.close()
 def test_same_size_same_mtime_replacement_invalidates_binding(self):
  bound=b.Binding(self.load());model=self.artifacts/'model.onnx';before=model.stat();replacement=self.artifacts/'replacement'
  try:
   replacement.write_bytes(b'x'*before.st_size);os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns));os.replace(replacement,model)
   self.assertFalse(bound.valid())
  finally:bound.close()
 def test_warm_calls_do_not_rehash_or_read_large_artifacts(self):
  import language_checker as checker
  model=self.artifacts/'model.onnx';model.write_bytes(b'x'*(4*1024**2));self.manifest['artifacts'][0]['sha256']=self.sha(model);self.write()
  mission={'start_step':'one','opening_sv':'Vill du ha kaffe?','steps':[{'id':'one','prompt_sv':'Vill du ha kaffe?','objective':'confirm','intents':[{'id':'yes','meaning_sv':'Ja.'},{'id':'no','meaning_sv':'Nej.'}]}]}
  with patch.object(b,'_hashfile',wraps=b._hashfile) as loader_hash,patch.object(checker,'_digest',wraps=checker._digest) as checker_hash:
   bound=b.Binding(self.load());worker=Mock();worker.ready.return_value=True;worker.request.return_value={'ok':True,'scores':[.99,.01],'language':'sv','language_probability':1.,'swedish_probability':1.,'token_counts':[12,12],'truncated':False};bound.checker.worker=worker
   try:
    self.assertTrue(bound.ready());cold_loader=loader_hash.call_count;cold_checker=checker_hash.call_count
    self.assertGreater(cold_loader,0);self.assertEqual(cold_checker,5)
    with patch.object(b,'_bounded_bytes',wraps=b._bounded_bytes) as read:
     for _ in range(25):
      self.assertEqual(bound.check(mission,mission['steps'][0],[],'Ja tack')['intent_id'],'yes');self.assertTrue(bound.ready())
     self.assertTrue(read.call_count>0);self.assertTrue(all(call.args[0]==self.path.resolve() for call in read.call_args_list))
    self.assertEqual(loader_hash.call_count,cold_loader);self.assertEqual(checker_hash.call_count,cold_checker)
   finally:bound.close()
if __name__=='__main__':unittest.main()
