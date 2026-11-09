import copy,importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
class CandidateHelperTests(unittest.TestCase):
 def test_image_identity_and_mount_validation(self):
  spec=importlib.util.spec_from_file_location('receipt',HERE/'language_image_receipt.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  cid='a'*64;image='sha256:'+'b'*64
  good={'Id':cid,'Image':image,'State':{'Running':True},'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'PortBindings':{}},'Mounts':[{'Destination':'/data','RW':True},{'Destination':'/models','RW':False}]}
  self.assertEqual(mod.validate(good,cid,image)['image_id'],image)
  bad=[]
  for section,key,value in [('top','Image','sha256:'+'c'*64),('HostConfig','NetworkMode','host'),('HostConfig','ReadonlyRootfs',False),('HostConfig','Privileged',True)]:
   x=copy.deepcopy(good);(x if section=='top' else x[section])[key]=value;bad.append(x)
  x=copy.deepcopy(good);x['Mounts'][1]['RW']=True;bad.append(x)
  x=copy.deepcopy(good);x['Mounts']=[];bad.append(x)
  for x in bad:
   with self.assertRaises(ValueError):mod.validate(x,cid,image)
 def test_resource_probe_refuses_without_explicit_isolation(self):
  env=os.environ.copy();env.pop('BP5_STAGING_PROBE_TOKEN',None);env['BP5_STAGING_PROBE']='0'
  p=subprocess.run([sys.executable,str(HERE/'language_resource_probe.py')],env=env,capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertNotEqual(p.returncode,0);self.assertIn('isolated staging',p.stderr)
 def test_tokenizer_parity_refuses_tampered_artifact_before_loading_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'model.onnx').write_bytes(b'not-the-export');(root/'tokenizer.json').write_bytes(b'tokenizer');(root/'export-receipt.json').write_text(json.dumps({'status':'experimental_export_not_qualified','onnx_sha256':'0'*64,'tokenizer_sha256':'0'*64}))
   p=subprocess.run([sys.executable,str(HERE/'language_runtime_parity.py'),'--artifact-dir',str(root)],capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertNotEqual(p.returncode,0);self.assertIn('Parity check failed',p.stderr)
 def test_runtime_inventory_is_linux_only(self):
  if sys.platform.startswith('linux'):self.skipTest('Windows-only refusal check')
  p=subprocess.run([sys.executable,str(HERE/'language_runtime_inventory.py')],capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertNotEqual(p.returncode,0);self.assertIn('Linux candidate',p.stderr)
if __name__=='__main__':unittest.main()
