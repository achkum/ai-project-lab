"""Offline FP32 reconstruction/export for an experimental language candidate.

This does not qualify, deploy, or quantize a model. Run only after training has
stopped and an operator has pinned all input hashes in a private manifest.
"""
import argparse,hashlib,importlib.metadata,json,math,os,re,sys,time
from pathlib import Path

BASE_REVISION='8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c'
BASE_MODEL_SHA='65af59b1ff4450b09ecbf13ca35c840dbf038b26ff8e10e5ea89ca724828ed1e'
TOKENIZER_SHA='3aca3ce69a0a35aeb144a52c4f1d41c4246b8785f8f398315cc8fb6b24057810'
REQUIRED={'config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','spm.model','added_tokens.json'}
COMMON_PREFIXES=('classifier.','pooler.')

def checkpoint_inventory(parameters, state, settings):
    if not isinstance(settings,dict) or not isinstance(state,dict):raise ValueError('Unsupported training checkpoint')
    if settings.get('frozen_prefix')=='FP32' and settings.get('objective')=='binary match vs logsumexp(neutral,contradiction)' and settings.get('trainable')=='last encoder layer, pooler, classifier':
        layers=(11,);kind='last_one'
    elif settings.get('objective')=='entailment vs combined neutral or contradiction' and settings.get('max_tokens')==512 and settings.get('warm_start')=='inputs/00-full-checkpoint.pt':
        layers=(8,9,10,11);kind='last_four'
    elif settings.get('resume')=='checkpoint-200.pt' and settings.get('optimizer')=='AdamW state restored, learning rate unchanged' and settings.get('initial_optimizer_updates')==200 and settings.get('max_tokens')==512 and settings.get('schedule')=='schedule.json, each pair exactly once':
        layers=(8,9,10,11);kind='last_four_coverage'
    else:raise ValueError('Unsupported training checkpoint settings')
    prefixes=COMMON_PREFIXES+tuple(f'deberta.encoder.layer.{i}.' for i in layers)
    expected={name for name in parameters if name.startswith(prefixes)}
    if not expected or set(state)!=expected or any(not any(n.startswith(p) for n in expected) for p in prefixes):raise ValueError('Checkpoint parameter inventory mismatch')
    if kind=='last_four':
        declared=settings.get('trainable_names')
        if not isinstance(declared,list) or len(declared)!=len(expected) or set(declared)!=expected:raise ValueError('Checkpoint declared inventory mismatch')
    return kind,expected

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def check_inputs(base,checkpoint,manifest):
    if base.is_symlink() or checkpoint.is_symlink() or manifest.is_symlink() or not base.is_dir() or not checkpoint.is_file() or not manifest.is_file():raise ValueError('Input unavailable')
    if manifest.stat().st_size>65536:raise ValueError('Invalid input manifest')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate key')
            result[key]=value
        return result
    doc=json.loads(manifest.read_text(encoding='utf8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid number')))
    if not isinstance(doc,dict) or set(doc)!={'base_revision','base_files','checkpoint_sha256'} or doc['base_revision']!=BASE_REVISION:raise ValueError('Invalid input manifest')
    files=doc['base_files']
    if not isinstance(files,dict) or set(files)!=REQUIRED:raise ValueError('Base file inventory incomplete')
    if files['model.safetensors']!=BASE_MODEL_SHA or files['tokenizer.json']!=TOKENIZER_SHA:raise ValueError('Unrecognized original base artifacts')
    for name in sorted(REQUIRED):
        expected=files[name];p=base/name
        if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or not p.is_file() or p.is_symlink() or digest(p)!=expected:raise ValueError('Base artifact mismatch')
    expected=doc['checkpoint_sha256']
    if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or checkpoint.is_symlink() or digest(checkpoint)!=expected:raise ValueError('Checkpoint mismatch')
    # Avoid loading unpinned configuration/tokenizer/model files from a snapshot.
    extras=[p.name for p in base.iterdir() if p.is_file() and p.name not in REQUIRED and (p.suffix in ('.json','.bin','.safetensors','.py') or p.name.startswith('tokenizer'))]
    if extras:raise ValueError('Unpinned base files present')
    return doc

def run(base,checkpoint,manifest,out):
    inputs=check_inputs(base,checkpoint,manifest)
    if out.exists():raise ValueError('Output directory already exists')
    out.mkdir(parents=True,exist_ok=False);marker=out/'.incomplete';marker.write_text('Not qualified. Export not complete.\n',encoding='utf8')
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    import numpy as np
    import onnx,onnxruntime as ort,torch
    from transformers import AutoModelForSequenceClassification,AutoTokenizer
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    tokenizer=AutoTokenizer.from_pretrained(str(base),local_files_only=True,trust_remote_code=False,use_fast=True)
    model=AutoModelForSequenceClassification.from_pretrained(str(base),local_files_only=True,trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float32)
    labels={str(k):str(v).lower() for k,v in model.config.id2label.items()}
    if labels!={'0':'entailment','1':'neutral','2':'contradiction'}:raise ValueError('Unexpected label mapping')
    parameters=dict(model.named_parameters())
    checkpoint_data=torch.load(str(checkpoint),map_location='cpu',weights_only=True)
    state=checkpoint_data.get('trainable_state') if isinstance(checkpoint_data,dict) else None
    settings=checkpoint_data.get('settings') if isinstance(checkpoint_data,dict) else None
    inventory,expected=checkpoint_inventory(parameters,state,settings)
    with torch.no_grad():
        for name in sorted(expected):
            value=state[name];target=parameters[name]
            if not isinstance(value,torch.Tensor) or value.dtype!=torch.float32 or value.shape!=target.shape or not torch.isfinite(value).all().item():raise ValueError('Invalid checkpoint tensor')
            target.copy_(value)
    model.eval()
    class Logits(torch.nn.Module):
        def __init__(self,inner):super().__init__();self.inner=inner
        def forward(self,input_ids,attention_mask):return self.inner(input_ids=input_ids,attention_mask=attention_mask).logits
    wrapper=Logits(model).eval();question='Erbjudande: Vill du ha kaffe?\nFråga: Vill du ha kaffe?\nSvar: '
    hypothesis='Svaret betyder: Jag vill ha kaffe.'
    probes=[('short',question+'Ja, kaffe tack.',hypothesis),('negation',question+'Jag vill inte ha kaffe.',hypothesis)]
    longtext=None
    for n in range(80,140):
        candidate=question+('åäöø'*n)+' inte'
        if 490<=len(tokenizer(candidate,hypothesis,truncation=False)['input_ids'])<=512:longtext=candidate;break
    if longtext is None:raise ValueError('Could not construct near-limit probe')
    probes.append(('near_limit_late_negation',longtext,hypothesis))
    sample=tokenizer([probes[0][1]],[probes[0][2]],padding=True,truncation=False,return_tensors='pt');output=out/'model.onnx'
    with torch.inference_mode():
        torch.onnx.export(wrapper,(sample['input_ids'],sample['attention_mask']),str(output),input_names=['input_ids','attention_mask'],output_names=['logits'],dynamic_axes={'input_ids':{0:'batch',1:'sequence'},'attention_mask':{0:'batch',1:'sequence'},'logits':{0:'batch'}},opset_version=17,dynamo=False)
    if {p.name for p in out.iterdir()}!={'.incomplete','model.onnx'}:raise ValueError('Unexpected external export files')
    onnx.checker.check_model(str(output));options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;session=ort.InferenceSession(str(output),sess_options=options,providers=['CPUExecutionProvider'])
    if {x.name for x in session.get_inputs()}!={'input_ids','attention_mask'} or len(session.get_outputs())!=1 or session.get_outputs()[0].shape[-1]!=3:raise ValueError('Unexpected ONNX signature')
    checked=[]
    for name,premise,hyp in probes:
        enc=tokenizer([premise],[hyp],padding=True,truncation=False,return_tensors='pt');length=int(enc['attention_mask'].sum().item())
        if length>512:raise ValueError('Probe exceeds 512 tokens')
        with torch.inference_mode():pt=wrapper(enc['input_ids'],enc['attention_mask']).numpy()
        ortout=session.run(None,{'input_ids':enc['input_ids'].numpy().astype(np.int64),'attention_mask':enc['attention_mask'].numpy().astype(np.int64)})[0]
        if pt.shape!=(1,3) or ortout.shape!=(1,3) or not np.isfinite(pt).all() or not np.isfinite(ortout).all():raise ValueError('Invalid inference output')
        softmax=lambda z:np.exp(z-z.max(axis=1,keepdims=True))/np.exp(z-z.max(axis=1,keepdims=True)).sum(axis=1,keepdims=True)
        logit_error=float(np.max(np.abs(pt-ortout)));prob_error=float(np.max(np.abs(softmax(pt)-softmax(ortout))))
        if logit_error>.005 or prob_error>.001:raise ValueError('FP32 export parity failed')
        token_bytes=enc['input_ids'].numpy().astype('<i8').tobytes()+enc['attention_mask'].numpy().astype('<i8').tobytes()
        checked.append({'name':name,'token_count':length,'token_ids_sha256':hashlib.sha256(token_bytes).hexdigest(),'truncated':False,'max_logit_error':logit_error,'max_probability_error':prob_error})
    if check_inputs(base,checkpoint,manifest)!=inputs:raise ValueError('Input changed during export')
    # Save the exact pinned fast tokenizer consumed by the serving worker.
    (out/'tokenizer.json').write_bytes((base/'tokenizer.json').read_bytes())
    receipt={'status':'experimental_export_not_qualified','base_revision':BASE_REVISION,'base_files':inputs['base_files'],'checkpoint_sha256':inputs['checkpoint_sha256'],'checkpoint_examples':checkpoint_data.get('examples'),'checkpoint_inventory':inventory,'training_settings':{key:settings.get(key) for key in ('frozen_prefix','objective','trainable','max_tokens','batch','max_updates')},'onnx_sha256':digest(output),'onnx_bytes':output.stat().st_size,'tokenizer_sha256':digest(out/'tokenizer.json'),'label_mapping':{'entailment':0,'neutral':1,'contradiction':2},'opset':17,'threads':1,'probes':checked,'versions':{k:importlib.metadata.version(k) for k in ('torch','transformers','onnx','onnxruntime','tokenizers','numpy')},'exported_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (out/'export-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');marker.unlink();print(json.dumps({'status':receipt['status'],'onnx_sha256':receipt['onnx_sha256'],'onnx_bytes':receipt['onnx_bytes'],'probes':checked}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-dir',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--input-manifest',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    try:run(a.base_dir.absolute(),a.checkpoint.absolute(),a.input_manifest.absolute(),a.output_dir.absolute())
    except Exception as exc:print('Export failed: '+type(exc).__name__,file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
