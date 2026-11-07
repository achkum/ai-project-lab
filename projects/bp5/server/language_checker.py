"""Reusable experimental ONNX checker; the module default remains unavailable.

No model has passed the independent release gate. Constructing a Checker for
local testing is not a deployment declaration or evidence of model quality.
"""
import hashlib,json,math,os,re,sys
from pathlib import Path
from language_process import WorkerError,WorkerSupervisor
from language_support import language_support

class CheckerUnavailable(Exception):
    pass

class ContextUnknown(Exception):
    pass

class CheckerInputTooLong(CheckerUnavailable):
    def __init__(self,token_counts,evaluation_trace=None):
        super().__init__('Try a shorter reply for this turn. Your draft is still here.')
        self.token_counts=tuple(token_counts);self.evaluation_trace=evaluation_trace

def choose(scores, intent_ids, threshold, margin):
    """Return an intent or unknown from finite probabilities and calibrated limits."""
    if not isinstance(scores,list) or not isinstance(intent_ids,list) or not 1<=len(scores)==len(intent_ids)<=6 or len(set(intent_ids))!=len(intent_ids):raise ValueError('Invalid scores')
    if any(not isinstance(v,str) or not 1<=len(v)<=120 for v in intent_ids):raise ValueError('Invalid intents')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in scores):raise ValueError('Invalid scores')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in (threshold,margin)):raise ValueError('Invalid limits')
    order=sorted(range(len(scores)),key=lambda n:scores[n],reverse=True);winner=order[0];top=float(scores[winner]);gap=top-float(scores[order[1]]) if len(order)>1 else top
    return (intent_ids[winner] if top>=threshold and (len(order)==1 or (gap>0 and gap>=margin)) else None,top)

def _digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

class Checker:
    def __init__(self,config,threshold,margin,revision,*,timeout=15,startup_timeout=30,context_resolver=None,premise_builder=None):
        if not isinstance(config,dict) or set(config)!={'model','model_sha256','tokenizer','tokenizer_sha256','language_model','language_model_sha256','vocabulary','vocabulary_sha256','vocabulary_source','vocabulary_source_sha256','runtime_hashes','max_tokens','threads'}:raise ValueError('Invalid configuration')
        if not isinstance(revision,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',revision):raise ValueError('Invalid revision')
        choose([.5],['test'],threshold,margin)
        if context_resolver is not None and not callable(context_resolver):raise ValueError('Invalid context resolver')
        if premise_builder is not None and (not callable(premise_builder) or context_resolver is not None):raise ValueError('Invalid premise builder')
        for key in ('model','tokenizer','language_model','vocabulary','vocabulary_source'):
            if not isinstance(config[key],str) or not os.path.isabs(config[key]) or not re.fullmatch('[a-f0-9]{64}',str(config[key+'_sha256'])):raise ValueError('Invalid artifact')
        hashes=config['runtime_hashes']
        if not isinstance(hashes,dict) or set(hashes)!={'python','onnxruntime','tokenizers','numpy','fasttext'} or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in hashes.values()):raise ValueError('Invalid runtime')
        if type(config['max_tokens']) is not int or not 16<=config['max_tokens']<=512 or type(config['threads']) is not int or not 1<=config['threads']<=2:raise ValueError('Invalid bounds')
        self.config=dict(config);self.threshold=threshold;self.margin=margin;self.revision=revision;self.context_resolver=context_resolver;self.premise_builder=premise_builder;self._fingerprints=None;self._vocabulary=None
        script=str(Path(__file__).with_name('language_worker.py').resolve())
        startup={k:self.config[k] for k in ('model','model_sha256','tokenizer','tokenizer_sha256','language_model','language_model_sha256','runtime_hashes','max_tokens','threads')}
        self.worker=WorkerSupervisor([sys.executable,'-I',script],startup,timeout=timeout,startup_timeout=startup_timeout)

    def _verify(self):
        current=[]
        for key,limit in (('model',2*1024**3),('tokenizer',30*1024**2),('language_model',256*1024**2),('vocabulary',2*1024**2),('vocabulary_source',8*1024**2)):
            p=Path(self.config[key]);stat=p.stat()
            if not p.is_file() or stat.st_size>limit:raise CheckerUnavailable('Model unavailable')
            current.append((stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_dev,stat.st_ino,stat.st_nlink))
        fingerprint=tuple(current)
        if fingerprint!=self._fingerprints:
            self.worker.close()
            for key in ('model','tokenizer','language_model','vocabulary','vocabulary_source'):
                if _digest(self.config[key])!=self.config[key+'_sha256']:raise CheckerUnavailable('Model unavailable')
            try:
                with open(self.config['vocabulary'],encoding='utf8') as handle:vocab=json.load(handle)
                words=vocab['words']
                if vocab.get('schema_version')!='1' or vocab.get('source_sha256')!=self.config['vocabulary_source_sha256'] or not isinstance(words,list) or not 1<=len(words)<=100000 or any(not isinstance(w,str) or not 1<=len(w)<=100 for w in words):raise ValueError('Invalid vocabulary')
                self._vocabulary=frozenset(words)
            except (KeyError,ValueError,TypeError) as exc:raise CheckerUnavailable('Model unavailable') from exc
            self._fingerprints=fingerprint

    def ready(self):
        try:self._verify();return self.worker.ready()
        except (OSError,WorkerError,CheckerUnavailable):return False

    def check(self,mission_snapshot,current_step,recent_turns,text,*,evaluation_trace=False):
        if not isinstance(mission_snapshot,dict) or not isinstance(current_step,dict) or not isinstance(recent_turns,list) or len(recent_turns)>8 or not isinstance(text,str) or not 1<=len(text)<=2000:raise CheckerUnavailable('Invalid input')
        try:
            if self.premise_builder:
                premise=self.premise_builder(mission_snapshot,current_step,recent_turns,text)
            else:
                prompt=self.context_resolver(mission_snapshot,current_step,recent_turns) if self.context_resolver else current_step.get('prompt_sv')
                if not isinstance(prompt,str) or not 1<=len(prompt)<=1000:raise ValueError('Invalid prompt')
                premise='Fråga: '+prompt+' Svar: '+text
        except ContextUnknown:
            if not self.ready():raise CheckerUnavailable('Checker unavailable')
            result={'intent_id':None,'confidence':0.0,'source':'semantic','language':'und','language_supported':False,'language_evidence':'unresolved','checker_revision':self.revision}
            if evaluation_trace is True:result['evaluation_trace']={'input_characters':len(text),'input_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),'token_counts':[],'truncated':False,'context_unresolved':True}
            return result
        except Exception as exc:raise CheckerUnavailable('Context unavailable') from exc
        intents=current_step.get('intents')
        if not isinstance(premise,str) or not 1<=len(premise)<=4000 or text not in premise or not isinstance(intents,list) or not 1<=len(intents)<=6:raise CheckerUnavailable('Invalid input')
        pairs=[];ids=[]
        for intent in intents:
            if not isinstance(intent,dict):raise CheckerUnavailable('Invalid input')
            ident=intent.get('id');meaning=intent.get('meaning_sv');examples=intent.get('examples_sv',[])
            if not meaning and isinstance(examples,list) and examples:meaning=examples[0]
            if not isinstance(ident,str) or not 1<=len(ident)<=120 or not isinstance(meaning,str) or not 1<=len(meaning)<=1000:raise CheckerUnavailable('Invalid input')
            ids.append(ident);pairs.append([premise,'Svaret betyder: '+meaning])
        if len(set(ids))!=len(ids):raise CheckerUnavailable('Invalid input')
        try:
            self._verify();out=self.worker.request({'op':'score','text':text,'pairs':pairs})
            if out.get('ok') is False and out.get('error')=='token_limit':
                counts=out.get('token_counts')
                if set(out)!={'ok','error','token_counts','truncated'} or out.get('truncated') is not False or not isinstance(counts,list) or len(counts)!=len(ids) or any(type(x) is not int or x<1 for x in counts):raise CheckerUnavailable('Checker unavailable')
                trace={'input_characters':len(text),'input_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),'token_counts':counts,'truncated':False} if evaluation_trace is True else None
                raise CheckerInputTooLong(counts,trace)
            if set(out)!={'ok','scores','language','language_probability','swedish_probability','token_counts','truncated'} or out['ok'] is not True or out['truncated'] is not False:raise CheckerUnavailable('Checker unavailable')
            counts=out['token_counts']
            if not isinstance(counts,list) or len(counts)!=len(ids) or any(type(x) is not int or not 1<=x<=self.config['max_tokens'] for x in counts):raise CheckerUnavailable('Checker unavailable')
            selected,confidence=choose(out['scores'],ids,self.threshold,self.margin)
            supported,evidence=language_support(text,current_step.get('objective'),out['language'],out['language_probability'],out['swedish_probability'],self._vocabulary)
        except (OSError,WorkerError,ValueError) as exc:raise CheckerUnavailable('Checker unavailable') from exc
        if not supported:selected=None
        result={'intent_id':selected,'confidence':confidence,'source':'semantic','language':out['language'],'language_supported':supported,'language_evidence':evidence,'checker_revision':self.revision}
        if evaluation_trace is True:result['evaluation_trace']={'input_characters':len(text),'input_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),'token_counts':counts,'truncated':False}
        return result

    def close(self):self.worker.close()

# Fixed manifest and operator-owned artifact root; absent configuration fails closed.
def check(mission_snapshot,current_step,recent_turns,text,*,evaluation_trace=False):
    from language_binding import candidate
    return candidate().check(mission_snapshot,current_step,recent_turns,text,evaluation_trace=evaluation_trace)

def ready():
    try:
        from language_binding import candidate
        return candidate().ready()
    except Exception:return False
