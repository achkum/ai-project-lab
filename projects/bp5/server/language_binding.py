"""Operator-only binding for a qualified language candidate. No manifest is shipped."""
import atexit,hashlib,json,math,os,re,stat,sys,threading
from pathlib import Path,PurePosixPath
from language_checker import Checker,CheckerUnavailable,ContextUnknown,choose
from language_context import current_offer,ContextUnavailable

PROJECT=Path(__file__).resolve().parent.parent
MANIFEST='LANGUAGE_CHECKER_MANIFEST.json'
CONFIG_KEYS={'model','tokenizer','language_model','runtime_artifacts','library_sha256','library_version','vocabulary_sha256','checkpoint_id','base_model_revision','tokenizer_revision','calibration_source','threshold','margin','max_tokens','threads','timeout_seconds','startup_timeout_seconds','label_mapping','premise_format','hypothesis_format','language_policy'}
RUNTIME_ROLES={'python','onnxruntime','tokenizers','numpy','fasttext'}
TOKENIZER_REVISION='8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c'
_lock=threading.Lock();_bound=None

def _json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid number')))

def _sha(raw):return hashlib.sha256(raw).hexdigest()

def _bounded_bytes(path,limit):
    with path.open('rb') as handle:data=handle.read(limit+1)
    if len(data)>limit:raise ValueError('File too large')
    return data
def _hex(value):return isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value) is not None

def _root(path):
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (path,*path.parents)):raise ValueError('Invalid root')
    resolved=path.resolve(strict=True)
    if not resolved.is_dir():raise ValueError('Invalid root')
    return resolved

def _relative(root,name):
    if not isinstance(name,str) or not 1<=len(name)<=500 or '\\' in name or ':' in name:raise ValueError('Invalid artifact')
    p=PurePosixPath(name)
    if p.is_absolute() or any(part in ('','.','..') for part in name.split('/')):raise ValueError('Invalid artifact')
    current=root
    for part in p.parts:
        current=current/part
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):raise ValueError('Invalid artifact')
    resolved=current.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():raise ValueError('Invalid artifact')
    return resolved

def _fingerprint(path):
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>2*1024**3 or info.st_nlink!=1:raise ValueError('Invalid artifact')
    return (info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_dev,info.st_ino,info.st_nlink)

def _hashfile(path):
    before=_fingerprint(path);h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    if before!=_fingerprint(path):raise ValueError('Artifact changed')
    return h.hexdigest(),before

def _premise(mission,step,recent_turns,text):
    try:offer=current_offer(mission,step,recent_turns)
    except ContextUnavailable as exc:raise ContextUnknown('Offer unavailable') from exc
    prompt=step.get('prompt_sv')
    if not isinstance(prompt,str) or not 1<=len(prompt)<=1000:raise ValueError('Invalid prompt')
    return 'Erbjudande: '+offer+'\nFråga: '+prompt+'\nSvar: '+text

def _load_configuration(project_root,artifact_root):
    project_root=_root(project_root)
    if not isinstance(artifact_root,(str,Path)) or not Path(artifact_root).is_absolute():raise ValueError('Invalid root')
    root=_root(artifact_root)
    manifest=_relative(project_root,MANIFEST);raw=_bounded_bytes(manifest,65536)
    d=_json(raw)
    if not isinstance(d,dict) or set(d)!={'schema_version','adapter','artifacts'} or type(d['schema_version']) is not int or d['schema_version']!=1:raise ValueError('Invalid manifest')
    a=d['adapter']
    if not isinstance(a,dict) or set(a)!={'entrypoint','configuration','execution_mode','environment','runtime_platform','evaluation_target'}:raise ValueError('Invalid adapter')
    if a['entrypoint']!='server/language_checker.py:check' or a['execution_mode']!='production_adapter' or a['runtime_platform']!='linux' or a['evaluation_target'] not in ('isolated_vps_candidate','identical_linux_container'):raise ValueError('Invalid adapter')
    environment=a['environment'];limits={'BP5_SEMANTIC_BURST_UNITS':(48,48,240),'BP5_SEMANTIC_REFILL_UNITS_PER_MINUTE':(24,1,120),'BP5_SEMANTIC_COOLDOWN_PERCENT':(100,25,200)}
    if not isinstance(environment,dict) or set(environment)!={'BP5_SEMANTIC_REQUIRED',*limits} or environment['BP5_SEMANTIC_REQUIRED']!='1' or os.getenv('BP5_SEMANTIC_REQUIRED')!='1':raise ValueError('Invalid environment')
    for key,(default,minimum,maximum) in limits.items():
        value=environment[key]
        if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,3}',value) or not minimum<=int(value)<=maximum or os.getenv(key,str(default))!=value:raise ValueError('Invalid budget environment')
    c=a['configuration']
    if not isinstance(c,dict) or set(c)!=CONFIG_KEYS:raise ValueError('Invalid configuration')
    if c['premise_format']!='offer-question-reply-v1' or c['hypothesis_format']!='meaning-sv-v1' or c['language_policy']!='fasttext-vocab-v1' or c['label_mapping']!={'entailment':0,'neutral':1,'contradiction':2} or c['tokenizer_revision']!=TOKENIZER_REVISION or c['base_model_revision']!=TOKENIZER_REVISION:raise ValueError('Invalid model format')
    if any(type(value) is not int for value in c['label_mapping'].values()):raise ValueError('Invalid model format')
    for key in ('checkpoint_id','calibration_source','library_version'):
        if not isinstance(c[key],str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',c[key]):raise ValueError('Invalid configuration')
    if not _hex(c['library_sha256']) or not _hex(c['vocabulary_sha256']) or type(c['max_tokens']) is not int or c['max_tokens']!=512 or type(c['threads']) is not int or c['threads'] not in (1,2):raise ValueError('Invalid configuration')
    for key in ('timeout_seconds','startup_timeout_seconds'):
        v=c[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<v<=120:raise ValueError('Invalid deadline')
    choose([.5],['fixture'],c['threshold'],c['margin'])
    items=d['artifacts']
    if not isinstance(items,list) or not 8<=len(items)<=1024:raise ValueError('Invalid artifacts')
    artifacts={};fingerprints={}
    for item in items:
        if not isinstance(item,dict) or set(item)!={'path','sha256'} or not _hex(item['sha256']) or item['path'] in artifacts:raise ValueError('Invalid artifact')
        path=_relative(root,item['path']);digest,fp=_hashfile(path)
        if digest!=item['sha256']:raise ValueError('Artifact mismatch')
        artifacts[item['path']]=(path,digest);fingerprints[path]=fp
    runtime=c['runtime_artifacts']
    if not isinstance(runtime,dict) or set(runtime)!=RUNTIME_ROLES:raise ValueError('Invalid runtime')
    rolepaths=[c['model'],c['tokenizer'],c['language_model']]+list(runtime.values())
    if any(not isinstance(name,str) or name not in artifacts for name in rolepaths) or len(set(rolepaths))!=len(rolepaths):raise ValueError('Invalid artifact roles')
    if _hashfile(Path(sys.executable).resolve(strict=True))[0]!=artifacts[runtime['python']][1]:raise ValueError('Interpreter mismatch')
    library=_relative(project_root,'content/library.json');vocabulary=_relative(project_root,'server/swedish_support_vocabulary.json')
    libhash,libfp=_hashfile(library);vocabhash,vocabfp=_hashfile(vocabulary)
    if libhash!=c['library_sha256'] or vocabhash!=c['vocabulary_sha256']:raise ValueError('Source mismatch')
    lib=_json(_bounded_bytes(library,8*1024**2));vocab=_json(_bounded_bytes(vocabulary,2*1024**2))
    if lib.get('content_version')!=c['library_version'] or vocab.get('source_sha256')!=libhash:raise ValueError('Source version mismatch')
    runtime_hashes={role:artifacts[name][1] for role,name in runtime.items()}
    config={'model':str(artifacts[c['model']][0]),'model_sha256':artifacts[c['model']][1], 'tokenizer':str(artifacts[c['tokenizer']][0]),'tokenizer_sha256':artifacts[c['tokenizer']][1], 'language_model':str(artifacts[c['language_model']][0]),'language_model_sha256':artifacts[c['language_model']][1], 'vocabulary':str(vocabulary),'vocabulary_sha256':vocabhash,'vocabulary_source':str(library),'vocabulary_source_sha256':libhash,'runtime_hashes':runtime_hashes,'max_tokens':512,'threads':c['threads']}
    fingerprints[library]=libfp;fingerprints[vocabulary]=vocabfp
    return {'config':config,'threshold':c['threshold'],'margin':c['margin'],'revision':c['checkpoint_id'],'timeout':c['timeout_seconds'],'startup_timeout':c['startup_timeout_seconds'],'project_root':project_root,'artifact_root':root,'environment':dict(environment),'artifact_paths':{name:value[0] for name,value in artifacts.items()},'manifest':manifest,'manifest_sha256':_sha(raw),'fingerprints':fingerprints}

class Binding:
    def __init__(self,info):
        self.info=info
        self.checker=Checker(info['config'],info['threshold'],info['margin'],info['revision'],timeout=info['timeout'],startup_timeout=info['startup_timeout'],premise_builder=_premise)
    def valid(self):
        try:
            project=self.info['project_root'];root=self.info['artifact_root'];environment=self.info['environment']
            configured=os.getenv('BP5_LANGUAGE_ARTIFACT_ROOT','')
            if not configured or _root(configured)!=root or _root(project)!=project:return False
            defaults={'BP5_SEMANTIC_BURST_UNITS':'48','BP5_SEMANTIC_REFILL_UNITS_PER_MINUTE':'24','BP5_SEMANTIC_COOLDOWN_PERCENT':'100'}
            if os.getenv('BP5_SEMANTIC_REQUIRED')!='1' or any(os.getenv(key,default)!=environment[key] for key,default in defaults.items()):return False
            if _relative(project,MANIFEST)!=self.info['manifest']:return False
            if any(_relative(root,name)!=path for name,path in self.info['artifact_paths'].items()):return False
            for name in ('content/library.json','server/swedish_support_vocabulary.json'):
                path=_relative(project,name)
                if path not in self.info['fingerprints']:return False
            raw=_bounded_bytes(self.info['manifest'],65536)
            return _sha(raw)==self.info['manifest_sha256'] and all(_fingerprint(path)==fp for path,fp in self.info['fingerprints'].items())
        except (OSError,ValueError):return False
    def ready(self):return self.valid() and self.checker.ready() and self.valid()
    def check(self,*args,**kwargs):
        if not self.valid():raise CheckerUnavailable('Semantic checker unavailable')
        result=self.checker.check(*args,**kwargs)
        if not self.valid():raise CheckerUnavailable('Semantic checker unavailable')
        return result
    def close(self):self.checker.close()

def candidate():
    global _bound
    if sys.platform!='linux':raise CheckerUnavailable('Semantic checker unavailable')
    # The binding is immutable after construction. Do not report a healthy
    # initialized worker unavailable merely because another caller checks it.
    bound=_bound
    if bound is not None:
        if not bound.valid():raise CheckerUnavailable('Semantic checker unavailable')
        return bound
    if not _lock.acquire(blocking=False):raise CheckerUnavailable('Semantic checker unavailable')
    try:
        if _bound is None:
            root=os.getenv('BP5_LANGUAGE_ARTIFACT_ROOT','')
            try:_bound=Binding(_load_configuration(PROJECT,root))
            except Exception as exc:raise CheckerUnavailable('Semantic checker unavailable') from exc
        if not _bound.valid():raise CheckerUnavailable('Semantic checker unavailable')
        return _bound
    finally:_lock.release()

def _shutdown():
    if _bound is not None:
        try:_bound.close()
        except Exception:pass
atexit.register(_shutdown)
