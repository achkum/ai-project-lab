"""Check exported synthetic tokenizer vectors inside the candidate Linux image.

Run before resource measurement in a separate disposable container; this is an
engineering parity check, not language quality or release acceptance.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--artifact-dir',type=Path,required=True);a=p.parse_args();root=a.artifact_dir.resolve(strict=True)
    receipt_path=root/'export-receipt.json';model=root/'model.onnx';token=root/'tokenizer.json'
    if any(p.is_symlink() or not p.is_file() for p in (receipt_path,model,token)) or receipt_path.stat().st_size>65536:raise ValueError('Invalid artifacts')
    receipt=json.loads(receipt_path.read_text(encoding='utf8'))
    if receipt.get('status')!='experimental_export_not_qualified' or digest(model)!=receipt.get('onnx_sha256') or digest(token)!=receipt.get('tokenizer_sha256'):raise ValueError('Artifact mismatch')
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(token));tok.no_truncation();question='Erbjudande: Vill du ha kaffe?\nFråga: Vill du ha kaffe?\nSvar: ';hypothesis='Svaret betyder: Jag vill ha kaffe.'
    inputs=[('short',question+'Ja, kaffe tack.'),('negation',question+'Jag vill inte ha kaffe.')];longtext=None
    for n in range(80,140):
        candidate=question+('åäöø'*n)+' inte'
        if 490<=len(tok.encode(candidate,hypothesis).ids)<=512:longtext=candidate;break
    if longtext is None:raise ValueError('Near-limit tokenization mismatch')
    inputs.append(('near_limit_late_negation',longtext));expected={x['name']:x for x in receipt.get('probes',[])};checks=[]
    if set(expected)!={x[0] for x in inputs}:raise ValueError('Invalid export receipt')
    for name,text in inputs:
        enc=tok.encode(text,hypothesis);ids=enc.ids;mask=enc.attention_mask;raw=struct.pack('<'+'q'*len(ids),*ids)+struct.pack('<'+'q'*len(mask),*mask);sha=hashlib.sha256(raw).hexdigest();want=expected[name]
        if len(ids)!=want.get('token_count') or sha!=want.get('token_ids_sha256') or want.get('truncated') is not False:raise ValueError('Tokenizer parity failed')
        checks.append({'name':name,'token_count':len(ids),'truncated':False})
    print(json.dumps({'status':'tokenizer_parity_pass_not_acceptance','checks':checks}))

if __name__=='__main__':
    try:main()
    except Exception as exc:print('Parity check failed: '+type(exc).__name__,file=sys.stderr);raise SystemExit(1)
