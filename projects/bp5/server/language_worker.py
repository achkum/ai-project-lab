"""Offline ONNX scoring worker. It communicates only through bounded JSON lines."""
import hashlib,json,math,os,re,sys
MAX_LINE=32768

def reply(value):
    data=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')+b'\n'
    if len(data)>16384:raise ValueError('response too large')
    sys.stdout.buffer.write(data);sys.stdout.buffer.flush()

def read():
    raw=sys.stdin.buffer.readline(MAX_LINE+1)
    if not raw:return None
    if len(raw)>MAX_LINE or not raw.endswith(b'\n'):raise ValueError('invalid input')
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('invalid input')
    return value

def verified(path,expected,limit):
    if not isinstance(path,str) or not 1<=len(path)<=1024 or not os.path.isabs(path):raise ValueError('invalid artifact')
    if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('invalid hash')
    if not os.path.isfile(path) or os.path.getsize(path)>limit:raise ValueError('invalid artifact')
    digest=hashlib.sha256()
    with open(path,'rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError('invalid artifact')

def main():
    first=read()
    if not first or set(first)!={'op','config'} or first['op']!='init' or not isinstance(first['config'],dict):raise ValueError('invalid initialization')
    c=first['config'];required={'model','model_sha256','tokenizer','tokenizer_sha256','language_model','language_model_sha256','runtime_hashes','max_tokens','threads'}
    if set(c)!=required or type(c['max_tokens']) is not int or not 16<=c['max_tokens']<=512 or type(c['threads']) is not int or not 1<=c['threads']<=2:raise ValueError('invalid initialization')
    verified(c['model'],c['model_sha256'],2*1024**3);verified(c['tokenizer'],c['tokenizer_sha256'],30*1024**2);verified(c['language_model'],c['language_model_sha256'],256*1024**2)
    import numpy as np
    import onnxruntime as ort
    import fasttext
    import fasttext_pybind
    import onnxruntime.capi.onnxruntime_pybind11_state as ort_native
    import tokenizers.tokenizers as tokenizers_native
    import numpy.core._multiarray_umath as numpy_native
    from tokenizers import Tokenizer
    runtimes=c['runtime_hashes'];required_runtime={'python','onnxruntime','tokenizers','numpy','fasttext'}
    if not isinstance(runtimes,dict) or set(runtimes)!=required_runtime:raise ValueError('invalid runtime')
    for key,path in {'python':sys.executable,'onnxruntime':ort_native.__file__,'tokenizers':tokenizers_native.__file__,'numpy':numpy_native.__file__,'fasttext':fasttext_pybind.__file__}.items():verified(os.path.abspath(path),runtimes[key],2*1024**3)
    language_model=fasttext.load_model(c['language_model'])
    tokenizer=Tokenizer.from_file(c['tokenizer']);tokenizer.no_truncation();tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
    options=ort.SessionOptions();options.intra_op_num_threads=c['threads'];options.inter_op_num_threads=1
    session=ort.InferenceSession(c['model'],sess_options=options,providers=['CPUExecutionProvider'])
    inputs={x.name:x for x in session.get_inputs()};outputs=session.get_outputs()
    if set(inputs)!={'input_ids','attention_mask'} or any(x.type!='tensor(int64)' for x in inputs.values()) or len(outputs)!=1 or len(outputs[0].shape)!=2 or outputs[0].shape[-1]!=3:raise ValueError('invalid model signature')
    reply({'ready':True,'protocol':1})
    while True:
        request=read()
        if request is None:return
        sequence=request.get('seq')
        try:
            if set(request)!={'op','text','pairs','seq'} or request['op']!='score' or type(sequence) is not int or not 1<=sequence<=2**63-1:raise ValueError('invalid request')
            text=request['text'];pairs=request['pairs']
            if not isinstance(text,str) or not 1<=len(text)<=2000 or not isinstance(pairs,list) or not 1<=len(pairs)<=6:raise ValueError('invalid request')
            if any(not isinstance(x,list) or len(x)!=2 or any(not isinstance(v,str) or not v or len(v)>4000 for v in x) for x in pairs):raise ValueError('invalid request')
            enc=tokenizer.encode_batch([(x[0],x[1]) for x in pairs]);counts=[sum(e.attention_mask) for e in enc]
            if max(counts)>c['max_tokens']:
                reply({'ok':False,'error':'token_limit','token_counts':counts,'truncated':False,'seq':sequence});continue
            feed={'input_ids':np.array([e.ids for e in enc],dtype=np.int64),'attention_mask':np.array([e.attention_mask for e in enc],dtype=np.int64)}
            logits=session.run(None,feed)[0]
            if logits.shape!=(len(pairs),3) or not np.isfinite(logits).all():raise ValueError('invalid output')
            exp=np.exp(logits-logits.max(axis=1,keepdims=True));probs=exp/exp.sum(axis=1,keepdims=True);scores=[float(x) for x in probs[:,0]]
            labels,probabilities=language_model.predict(text.replace('\n',' '),k=176)
            if any(not math.isfinite(float(value)) or not 0<=float(value)<=1.0001 for value in probabilities):raise ValueError('invalid language output')
            detected=labels[0].replace('__label__','',1);probabilities={label.replace('__label__','',1):min(float(value),1.0) for label,value in zip(labels,probabilities)}
            top=probabilities[detected];swedish=probabilities.get('sv',0.0)
            if not re.fullmatch('[a-z]{2,3}',detected) or any(not math.isfinite(x) or not 0<=x<=1 for x in scores+[top,swedish]):raise ValueError('invalid output')
            reply({'ok':True,'scores':scores,'language':detected,'language_probability':top,'swedish_probability':swedish,'token_counts':counts,'truncated':False,'seq':sequence})
        except Exception:reply({'ok':False,'seq':sequence})

if __name__=='__main__':
    try:main()
    except Exception:sys.exit(1)
