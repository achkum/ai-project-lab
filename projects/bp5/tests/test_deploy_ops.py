"""Offline operational fault injection. No SSH, Docker daemon, or real user data."""
import contextlib, copy, hashlib, importlib.util, io, json, os, sqlite3, subprocess, sys, tarfile, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'projects/bp5/deploy'))
import backup as storage
import activate
from engine import vps_product_delivery as delivery


class RolloutTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)/'prata';self.base.mkdir()
  self.stack=contextlib.ExitStack()
  for obj,name,value in [(storage,'BASE',self.base),(activate,'BASE',self.base),(storage,'operator',lambda:None),(storage,'locked',lambda _:contextlib.nullcontext()),(activate,'verify_release',lambda *_:None),(activate,'wait_ready',lambda *_args,**_kwargs:None),(storage,'active_mounts',lambda:[]),(storage,'backup',lambda:{'ok':True,'filename':'encrypted-recovery.age'})]:self.stack.enter_context(patch.object(obj,name,value))
  activate._CANCELLED=False;activate._OPERATION=None;self.source='c'*64;self.op='d'*32
  release=self.base/'releases'/self.source/'deploy';release.mkdir(parents=True);(release/'Dockerfile').write_text('FROM scratch')
  (self.base/'backup-recipient.txt').write_text('age1'+'q'*58)
  for name in ('piper/piper','sv-se-nst-medium.onnx','sv-se-nst-medium.onnx.json','kb-whisper-base-q5_0.bin','age/age'):
   p=self.base/'runtime'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
  data=self.base/'data';data.mkdir()
  with contextlib.closing(sqlite3.connect(data/'production.sqlite3')) as db,db:db.execute('CREATE TABLE evidence(value TEXT)');db.execute("INSERT INTO evidence VALUES('before')")
  self.containers={'a'*64:{'Id':'a'*64,'Name':'/prata-app','State':{'Running':True},'Config':{'Labels':{'com.prata.managed':'1','com.prata.source':'b'*64},'Env':['LAB_INSTANCE_ID=old']},'HostConfig':{'RestartPolicy':{'Name':'unless-stopped'}}}}
  self.fault=None;self.fired=False
  self.stack.enter_context(patch.object(activate,'inspect',side_effect=self.inspect))
  self.stack.enter_context(patch.object(activate,'run',side_effect=self.docker_run))
  self.stack.enter_context(patch.object(activate,'start',side_effect=self.start))
  self.stack.enter_context(patch.object(activate,'urlopen',side_effect=lambda url,**_:io.BytesIO(json.dumps({'instance':'new','ok':True}).encode())))
 def tearDown(self):self.stack.close();self.tmp.cleanup()
 def find(self,name):return next((c for c in self.containers.values() if c['Id']==name or c['Name'].lstrip('/')==name),None)
 def inspect(self,name):return copy.deepcopy(self.find(name))
 def docker_run(self,args,**kwargs):
  action=args[1]
  if action==self.fault and not self.fired:self.fired=True;raise RuntimeError('synthetic '+action+' failure')
  if action=='update':self.find(args[-1])['HostConfig']['RestartPolicy']['Name']=args[2].split('=',1)[1]
  elif action=='stop':self.find(args[-1])['State']['Running']=False
  elif action=='rename':self.find(args[2])['Name']='/'+args[3]
  elif action=='start':self.find(args[-1])['State']['Running']=True
  elif action=='rm':del self.containers[self.find(args[-1])['Id']]
  return subprocess.CompletedProcess(args,0,'','')
 def start(self,name,image,data,port,instance,source,restart,operation):
  ident=('e' if port==8789 else 'f')*64
  self.containers[ident]={'Id':ident,'Name':'/'+name,'State':{'Running':True},'Config':{'Labels':{'com.prata.managed':'1','com.prata.source':source,'com.prata.operation':operation},'Env':['LAB_INSTANCE_ID='+instance]},'HostConfig':{'RestartPolicy':{'Name':restart}}}
  if port==8788 and self.fault=='new-start':
   with contextlib.closing(sqlite3.connect(data/'production.sqlite3')) as db,db:db.execute("INSERT INTO evidence VALUES('new-user-write')")
   raise RuntimeError('synthetic startup failure after a user write')
 def assert_old(self):
  old=self.find('prata-app');self.assertEqual(old['Id'],'a'*64);self.assertTrue(old['State']['Running']);self.assertEqual(old['HostConfig']['RestartPolicy']['Name'],'unless-stopped')
  self.assertFalse(any(c['Name'].startswith('/prata-check-') for c in self.containers.values()))
 def test_update_stop_and_rename_failure_recover_old_container(self):
  for action in ('update','stop','rename'):
   with self.subTest(action=action):
    self.fault=action;self.fired=False
    with self.assertRaises(RuntimeError):activate.activate(self.source,'new',os.urandom(16).hex())
    self.assert_old()
 def test_encrypted_snapshot_failure_after_stop_recovers_old_container(self):
  with patch.object(storage,'backup',side_effect=OSError('synthetic encrypted backup failure')),self.assertRaises(OSError):activate.activate(self.source,'new',self.op)
  self.assert_old()
 def test_failed_release_never_erases_new_account_writes(self):
  self.fault='new-start'
  with self.assertRaises(RuntimeError):activate.activate(self.source,'new',self.op)
  self.assert_old()
  with contextlib.closing(sqlite3.connect(self.base/'data/production.sqlite3')) as db,db:self.assertEqual(db.execute('SELECT value FROM evidence').fetchall(),[('before',),('new-user-write',)])
 def test_legacy_snapshot_is_not_replayed(self):
  (self.base/'rollback.sqlite3').write_bytes(b'stale-untrusted')
  activate.activate(self.source,'new',self.op)
  self.assertEqual((self.base/'rollback.sqlite3').read_bytes(),b'stale-untrusted')
  with contextlib.closing(sqlite3.connect(self.base/'data/production.sqlite3')) as db:self.assertEqual(db.execute('SELECT value FROM evidence').fetchall(),[('before',)])
  self.assertFalse(list((self.base/'rollback').glob('*.sqlite3')))
 def test_same_source_new_job_is_idempotent(self):
  result=activate.activate(self.source,'new',self.op)
  self.assertEqual(result['source'],self.source)
  retry=activate.activate(self.source,'another-job','1'*32)
  self.assertTrue(retry['already_running']);self.assertEqual(retry['instance'],'new')
 def test_cleanup_failure_does_not_rollback_committed_service(self):
  original=storage.remove_tree;failed=[]
  def cleanup(path,parent):
   state=json.loads((self.base/'operations'/(self.op+'.json')).read_text())
   if state['phase']=='complete' and not failed:failed.append(True);raise OSError('cleanup failure')
   return original(path,parent)
  with patch.object(storage,'remove_tree',side_effect=cleanup):result=activate.activate(self.source,'new',self.op)
  self.assertTrue(result['cleanup_pending']);self.assertEqual(self.find('prata-app')['Id'],'f'*64)
  activate.recover_pending();self.assertFalse((self.base/'rollback'/(self.op+'.sqlite3')).exists());self.assertEqual(self.find('prata-app')['Id'],'f'*64)


class PackagingTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
  for name in delivery.REQUIRED:
   p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}' if p.suffix=='.json' else 'fixture')
 def tearDown(self):self.tmp.cleanup()
 def test_archive_scope_and_dockerfile_fingerprint(self):
  for name in ('data/private.json','runtime/key.txt','job-response.json','VALIDATION.txt','content/library_validation.json','server/test_private.py'):
   p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('DO_NOT_UPLOAD')
  archive=self.root/'source.tgz';first=delivery.package(self.source,archive)
  with tarfile.open(archive) as tar:
   self.assertFalse(any('DO_NOT_UPLOAD' in tar.extractfile(m).read().decode() for m in tar.getmembers()))
  (self.source/'deploy/Dockerfile').write_text('changed build')
  self.assertNotEqual(delivery.payload(self.source)[0],first)
 def test_source_changes_during_packaging_are_rejected(self):
  with patch.object(delivery,'source_fingerprint',side_effect=['before','after']),self.assertRaises(RuntimeError):delivery.package(self.source,self.root/'archive.tgz')
  self.assertFalse((self.root/'archive.tgz').exists())
 def test_symlink_source_rejected(self):
  target=self.root/'private.py';target.write_text('secret');link=self.source/'server/link.py'
  try:link.symlink_to(target)
  except OSError:self.skipTest('Symlink creation unavailable')
  with self.assertRaises(ValueError):delivery.payload(self.source)
 def unpack(self,op,fingerprint):
  code=delivery.UNPACK.replace("Path('/home/openclaw/prata')",'Path('+repr(str(self.root/'remote'))+')').replace('os.geteuid()!=996','False')
  old=os.umask(0o077)
  try:
   with patch.object(sys,'argv',['unpack',op,fingerprint]):exec(compile(code,'unpack','exec'),{})
  finally:os.umask(old)
 def test_remote_manifest_verification_and_repeat(self):
  remote=self.root/'remote';releases=remote/'releases';releases.mkdir(parents=True)
  for op in ('1'*32,'2'*32):
   archive=releases/('.upload-'+op+'.tgz');fingerprint=delivery.package(self.source,archive);self.unpack(op,fingerprint)
  with patch.object(storage,'BASE',remote):activate.verify_release(releases/fingerprint,fingerprint)
  (releases/fingerprint/'server/run.py').write_text('tamper')
  with patch.object(storage,'BASE',remote),self.assertRaises(RuntimeError):activate.verify_release(releases/fingerprint,fingerprint)
 def test_remote_archive_traversal_is_rejected(self):
  remote=self.root/'remote';releases=remote/'releases';releases.mkdir(parents=True);op='3'*32;data=b'bad'
  rows=[{'path':'../outside','size':3,'sha256':hashlib.sha256(data).hexdigest()}];fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with tarfile.open(releases/('.upload-'+op+'.tgz'),'w:gz') as tar:
   for name,raw in [('../outside',data),('release-manifest.json',json.dumps({'source':fingerprint,'files':rows}).encode())]:
    item=tarfile.TarInfo(name);item.size=len(raw);tar.addfile(item,io.BytesIO(raw))
  with self.assertRaises(RuntimeError):self.unpack(op,fingerprint)
  self.assertFalse((remote/'outside').exists())


class BackupTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)/'prata';self.base.mkdir();self.stack=contextlib.ExitStack()
  for obj,name,value in [(storage,'BASE',self.base),(storage,'operator',lambda:None),(storage,'locked',lambda _:contextlib.nullcontext()),(storage,'active_mounts',lambda:[])]:self.stack.enter_context(patch.object(obj,name,value))
  (self.base/'data').mkdir();(self.base/'runtime/age').mkdir(parents=True);(self.base/'runtime/age/age').write_text('fake');(self.base/'backup-recipient.txt').write_text('age1'+'q'*58)
  with contextlib.closing(sqlite3.connect(self.base/'data/production.sqlite3')) as db,db:db.execute('CREATE TABLE fixture(value TEXT)')
 def tearDown(self):self.stack.close();self.tmp.cleanup()
 def test_failed_encryption_leaves_no_partial_or_plain_and_prunes_old(self):
  target=self.base/'backups';target.mkdir();old=target/'prata-20200101T010101000000Z.sqlite3.age';old.write_bytes(b'old');os.utime(old,(time.time()-8*86400,)*2)
  def fail(args,**_):Path(args[args.index('-o')+1]).write_bytes(b'partial');raise subprocess.CalledProcessError(1,args)
  with patch.object(storage.subprocess,'run',side_effect=fail),self.assertRaises(subprocess.CalledProcessError):storage.backup()
  self.assertFalse(list(target.iterdir()));self.assertFalse(list((self.base/'backup-work').iterdir()));self.assertTrue((self.base/'data/production.sqlite3').exists())
  self.assertFalse(json.loads((self.base/'backup-status.json').read_text())['ok'])
 def test_backup_is_atomic_and_restricted_to_active_data(self):
  def encrypt(args,**_):Path(args[args.index('-o')+1]).write_bytes(b'encrypted');return subprocess.CompletedProcess(args,0)
  with patch.object(storage.subprocess,'run',side_effect=encrypt):record=storage.backup()
  self.assertEqual((self.base/'backups'/record['filename']).read_bytes(),b'encrypted');self.assertFalse(list((self.base/'backup-work').iterdir()))
  with self.assertRaises(ValueError):storage.backup(self.base/'candidate-data')
 def test_symlink_component_is_rejected_before_resolve(self):
  outside=Path(self.tmp.name)/'outside';outside.mkdir();link=self.base/'linked'
  try:link.symlink_to(outside,target_is_directory=True)
  except OSError:self.skipTest('Symlink creation unavailable')
  with self.assertRaises(ValueError):storage.checked(link/'database.sqlite3')
 def test_daily_expiry_preserves_active_data_and_mounted_clones(self):
  operation='9'*32;other='8'*32;old=time.time()-8*86400
  for ident in (operation,other):
   clone=self.base/'candidate-data'/ident;clone.mkdir(parents=True);(clone/'production.sqlite3').write_bytes(b'private clone')
   os.utime(clone/'production.sqlite3',(old,old));os.utime(clone,(old,old))
   storage.atomic_json(self.base/'operations'/(ident+'.json'),{'operation':ident,'phase':'preparing'})
  mounted=self.base/'candidate-data'/other
  with patch.object(storage,'active_mounts',return_value=[mounted,self.base/'data']):report=storage.expire_deployment_copies()
  self.assertIn(operation,report['expired']);self.assertFalse((self.base/'candidate-data'/operation).exists());self.assertTrue(mounted.exists());self.assertTrue((self.base/'data/production.sqlite3').exists())
  self.assertTrue(json.loads((self.base/'operations'/(operation+'.json')).read_text())['expired_artifacts'])
  self.assertTrue(list((self.base/'maintenance-history').glob('*.json')))


class CancellationTest(unittest.TestCase):
 def test_cancelled_transfer_terminates_and_reaps_ssh_child(self):
  class Child:
   returncode=None;terminated=False;reaped=False
   def communicate(self,timeout):raise subprocess.TimeoutExpired('ssh',timeout)
   def poll(self):return self.returncode
   def terminate(self):self.terminated=True;self.returncode=-15
   def wait(self,timeout):self.reaped=True;return self.returncode
  child=Child();clock=iter([0,0,40,40])
  with patch.object(delivery.sp,'Popen',return_value=child),patch.object(delivery.time,'monotonic',side_effect=lambda:next(clock)),self.assertRaises(RuntimeError):
   delivery.command(['ssh','fixture'],unittest.mock.Mock(side_effect=[None,RuntimeError('cancelled')]))
  self.assertTrue(child.terminated);self.assertTrue(child.reaped)
 def test_cancelled_remote_build_terminates_process_group(self):
  class Child:
   pid=123;returncode=None;calls=0
   def __enter__(self):return self
   def __exit__(self,*_):pass
   def communicate(self,timeout):
    self.calls+=1
    if self.calls==1:raise subprocess.TimeoutExpired('docker',timeout)
    self.returncode=-15;return ('','')
   def poll(self):return self.returncode
  child=Child()
  with patch.object(activate.subprocess,'Popen',return_value=child),patch.object(activate,'cancelled',side_effect=[None,RuntimeError('cancelled')]),patch.object(activate.os,'killpg',create=True) as kill,self.assertRaises(RuntimeError):activate.run(['docker','build'])
  kill.assert_called_once();self.assertEqual(child.returncode,-15)

if __name__=='__main__':unittest.main()
