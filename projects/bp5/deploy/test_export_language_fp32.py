import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).with_name('export_language_fp32.py');spec=importlib.util.spec_from_file_location('export_language_fp32',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class ExportInputTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.base=self.root/'base';self.base.mkdir();self.checkpoint=self.root/'checkpoint.pt';self.checkpoint.write_bytes(b'checkpoint')
  for name in mod.REQUIRED:(self.base/name).write_bytes(('fixture-'+name).encode())
  sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest();self.data={'base_revision':mod.BASE_REVISION,'base_files':{name:sha(self.base/name) for name in mod.REQUIRED},'checkpoint_sha256':sha(self.checkpoint)};self.manifest=self.root/'input.json';self.manifest.write_text(json.dumps(self.data));self.patches=[patch.object(mod,'BASE_MODEL_SHA',self.data['base_files']['model.safetensors']),patch.object(mod,'TOKENIZER_SHA',self.data['base_files']['tokenizer.json'])]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def test_pinned_inputs_validate_without_loading_model(self):self.assertEqual(mod.check_inputs(self.base,self.checkpoint,self.manifest),self.data)
 def test_rejects_checkpoint_tamper_and_unpinned_base(self):
  self.checkpoint.write_bytes(b'tampered')
  with self.assertRaises(ValueError):mod.check_inputs(self.base,self.checkpoint,self.manifest)
  self.checkpoint.write_bytes(b'checkpoint');(self.base/'extra.json').write_text('{}')
  with self.assertRaises(ValueError):mod.check_inputs(self.base,self.checkpoint,self.manifest)
 def test_duplicate_manifest_keys_and_wrong_revision_rejected(self):
  self.manifest.write_text('{"base_revision":"a","base_revision":"b"}')
  with self.assertRaises(ValueError):mod.check_inputs(self.base,self.checkpoint,self.manifest)
  self.data['base_revision']='unrecognized';self.manifest.write_text(json.dumps(self.data))
  with self.assertRaises(ValueError):mod.check_inputs(self.base,self.checkpoint,self.manifest)
 def test_existing_output_never_overwritten(self):
  output=self.root/'existing';output.mkdir();marker=output/'keep';marker.write_text('preserve')
  with self.assertRaises(ValueError):mod.run(self.base,self.checkpoint,self.manifest,output)
  self.assertEqual(marker.read_text(),'preserve')
 def test_audited_checkpoint_inventories_and_rejections(self):
  names=['classifier.weight','pooler.weight']+[f'deberta.encoder.layer.{i}.weight' for i in range(12)]
  parameters=dict.fromkeys(names);one={'frozen_prefix':'FP32','objective':'binary match vs logsumexp(neutral,contradiction)','trainable':'last encoder layer, pooler, classifier'}
  four={'objective':'entailment vs combined neutral or contradiction','max_tokens':512,'warm_start':'inputs/00-full-checkpoint.pt'}
  wanted=lambda layers:{n:None for n in names if n.startswith(('classifier.','pooler.')) or any(n.startswith(f'deberta.encoder.layer.{i}.') for i in layers)}
  state1=wanted([11]);state4=wanted([8,9,10,11]);four['trainable_names']=list(state4)
  self.assertEqual(mod.checkpoint_inventory(parameters,state1,one)[0],'last_one')
  self.assertEqual(mod.checkpoint_inventory(parameters,state4,four)[0],'last_four')
  coverage={'resume':'checkpoint-200.pt','optimizer':'AdamW state restored, learning rate unchanged','initial_optimizer_updates':200,'max_tokens':512,'schedule':'schedule.json, each pair exactly once'}
  self.assertEqual(mod.checkpoint_inventory(parameters,state4,coverage)[0],'last_four_coverage')
  for state,settings in [(state1,four),(state4,one),({**state4,'deberta.encoder.layer.7.weight':None},coverage),(state4,{**coverage,'max_tokens':256}),(state4,{**four,'trainable_names':list(state1)})]:
   with self.assertRaises(ValueError):mod.checkpoint_inventory(parameters,state,settings)
if __name__=='__main__':unittest.main()
