"""Allowlisted, content-addressed BP5 delivery; never uploads data or job outputs."""
import hashlib, io, json, os, re, shlex, stat, tarfile, tempfile, time, uuid
from pathlib import Path
from . import background_process as sp
from .product_delivery import contract, source_fingerprint

BASE='/home/openclaw/prata'
URL='https://198.44.116.159.sslip.io/apps/bp5/'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','openclaw']
MAX_SOURCE_BYTES=20*1024*1024
ROOT_FILES={'product.json','README.md','PRODUCT.md','.dockerignore'}
DEPLOY_FILES={'deploy/activate.py','deploy/backup.py','deploy/Dockerfile'}
REQUIRED={'product.json','server/run.py','server/production.py','server/production_store.py','server/requirements.txt','content/library.json','content/curriculum.json','web/index.html','web/app.js','web/style.css',*DEPLOY_FILES}


def allowed(name):
    parts=Path(name).parts
    if name in ROOT_FILES or name in DEPLOY_FILES:return True
    if any(p.startswith('.') or p in ('tests','test','data','runtime','node_modules','__pycache__') for p in parts):return False
    if len(parts)<2:return False
    suffix=Path(name).suffix
    if parts[0]=='server':return suffix=='.py' and not parts[-1].startswith('test_') or name=='server/requirements.txt'
    if parts[0]=='content':return name in ('content/library.json','content/curriculum.json')
    return parts[0]=='web' and suffix in ('.html','.css','.js','.svg')


def source_workspace(workspace):
    workspace=Path(os.path.abspath(workspace))
    for path in (workspace,*workspace.parents):
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('Source workspace cannot traverse links')
    return workspace.resolve()


def payload(workspace):
    workspace=source_workspace(workspace);files={};total=0
    candidates=[workspace/name for name in ROOT_FILES|DEPLOY_FILES]
    for root in ('server','content','web'):
        folder=workspace/root
        if folder.is_symlink() or getattr(folder,'is_junction',lambda:False)():raise ValueError('Source directory cannot be a link')
        candidates.extend(folder.rglob('*'))
    for path in sorted(set(candidates)):
        name=path.relative_to(workspace).as_posix()
        if not allowed(name):continue
        for item in (path,*path.parents):
            if item==workspace:break
            if item.is_symlink() or getattr(item,'is_junction',lambda:False)():raise ValueError('Linked source is not allowed')
        if not path.exists():continue
        info=path.stat()
        if stat.S_ISDIR(info.st_mode):continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Source must be a regular, unlinked file')
        with path.open('rb') as handle:content=handle.read(MAX_SOURCE_BYTES+1)
        after=path.stat()
        if (info.st_ino,info.st_size,info.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('Source changed during packaging')
        total+=len(content)
        if total>MAX_SOURCE_BYTES:raise ValueError('BP5 source exceeds packaging limit')
        files[name]=content
    if not REQUIRED.issubset(files):raise ValueError('Required BP5 production source is missing')
    rows=[{'path':name,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()} for name,content in sorted(files.items())]
    fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return fingerprint,rows,files


def package(workspace,archive):
    workspace=source_workspace(workspace)
    reviewed=source_fingerprint(workspace);fingerprint,rows,files=payload(workspace)
    with tarfile.open(archive,'x:gz') as tar:
        for name,content in [*sorted(files.items()),('release-manifest.json',json.dumps({'source':fingerprint,'files':rows},sort_keys=True).encode())]:
            item=tarfile.TarInfo(name);item.size=len(content);item.mode=0o600;item.mtime=0
            tar.addfile(item,io.BytesIO(content))
    # Verify both the review input and exact uploaded payload after snapshotting it.
    if reviewed!=source_fingerprint(workspace) or payload(workspace)[0]!=fingerprint:
        archive.unlink(missing_ok=True);raise RuntimeError('Source changed while packaging; rerun release checks')
    return fingerprint


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=5)
        except sp.TimeoutExpired:process.kill();process.wait(timeout=5)


def command(args,checkpoint,timeout=120):
    checkpoint();process=sp.Popen(args,stdout=sp.PIPE,stderr=sp.PIPE);started=last=time.monotonic()
    try:
        while True:
            try:out,err=process.communicate(timeout=.25);break
            except sp.TimeoutExpired:
                if time.monotonic()-started>timeout:raise RuntimeError('Managed transfer timed out')
                if time.monotonic()-last>30:checkpoint();last=time.monotonic()
        if process.returncode:raise RuntimeError('Managed transfer failed; existing service was preserved')
        checkpoint();return out
    except BaseException:stop_process(process);raise


# The remote unpacker verifies every byte before publishing an immutable directory.
# No tar extraction API follows links; no archive-supplied path can leave staging.
UNPACK=r"""
import hashlib,json,os,re,shutil,stat,tarfile,sys
from pathlib import Path
base=Path('/home/openclaw/prata');op,source=sys.argv[1:]
if os.geteuid()!=996 or not re.fullmatch('[a-f0-9]{32}',op) or not re.fullmatch('[a-f0-9]{64}',source):raise RuntimeError('Invalid managed operation')
os.umask(0o077)
def safe(p):
 for x in [*reversed(p.parents),p]:
  if x.is_symlink():raise RuntimeError('Symlink managed path')
 if not p.is_relative_to(base):raise RuntimeError('Unsafe path')
 return p
releases=safe(base/'releases');archive=safe(releases/('.upload-'+op+'.tgz'));stage=safe(releases/('.stage-'+op));target=safe(releases/source)
def digest(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify(folder,manifest):
 actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
 if actual!={r['path'] for r in manifest['files']}|{'release-manifest.json'}:raise RuntimeError('Unexpected release files')
 for row in manifest['files']:
  p=safe(folder/row['path']);s=p.stat()
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=row['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Release hash mismatch')
try:
 info=archive.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>22*1024*1024:raise RuntimeError('Invalid uploaded file')
 with tarfile.open(archive,'r:gz') as tar:
  members=[];total=0;names=set()
  for member in tar:
   total+=member.size
   if len(members)>=2000 or member.name in names or not member.isfile() or total>21*1024*1024:raise RuntimeError('Invalid archive members')
   members.append(member);names.add(member.name)
  manifest=json.load(tar.extractfile('release-manifest.json'));rows=manifest['files']
  if manifest['source']!=source or digest(rows)!=source:raise RuntimeError('Manifest mismatch')
  expected={r['path']:r for r in rows}
  if len(expected)!=len(rows) or set(expected)|{'release-manifest.json'}!={m.name for m in members}:raise RuntimeError('Manifest entries mismatch')
  for name in expected:
   p=Path(name)
   if p.is_absolute() or '..' in p.parts or chr(92) in name or not p.parts or name=='release-manifest.json':raise RuntimeError('Unsafe member')
  stage.mkdir(mode=0o700)
  for m in members:
   dest=safe(stage/m.name);dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
   with tar.extractfile(m) as src,dest.open('xb') as out:shutil.copyfileobj(src,out,1024*1024)
   # Docker COPY preserves source modes; the image's uid996 must be able to read them.
   # The release parent remains0700, so source is still private on the host.
   os.chmod(dest,0o644)
   for parent in dest.parents:
    if parent==stage:break
    os.chmod(parent,0o755)
  verify(stage,manifest)
 if target.exists():verify(target,manifest)
 else:stage.rename(target)
finally:
 if stage.exists():shutil.rmtree(stage)
 archive.unlink(missing_ok=True)
"""


def deploy(profile,job,workspace,checkpoint=lambda:None):
    workspace=source_workspace(workspace)
    scope=job.get('scope',{})
    if scope.get('id')!='BP5' or type(scope.get('version')) is not int or scope['version']<3:raise ValueError('No VPS deployment is configured for this selection')
    if not re.fullmatch('[a-zA-Z0-9_-]{1,80}',job['id']):raise ValueError('Invalid job identity')
    product=contract(workspace,'vps_service')
    if product.get('name')!='Prata' or product.get('runtime')!='python' or product.get('entry')!='server/run.py' or type(product.get('version')) is not int or product['version']<3:raise ValueError('Unexpected BP5 product contract')
    local=Path(profile['runtime_root'])/'vps-products'/'bp5';local.mkdir(parents=True,exist_ok=True)
    operation=uuid.uuid4().hex;work=Path(tempfile.mkdtemp(prefix=job['id']+'-',dir=local));archive=work/'source.tgz'
    fingerprint=package(workspace,archive);dest=BASE+'/releases/'+fingerprint
    prepare="import os\nfrom pathlib import Path\nb=Path("+repr(BASE)+")\nif os.geteuid()!=996:raise RuntimeError('Unexpected operator')\nos.umask(0o077)\npaths=[b,b/'releases',b/'operations']\nif any(x.is_symlink() for p in paths for x in [p,*p.parents]):raise RuntimeError('Linked managed path')\nfor p in paths:\n p.mkdir(mode=0o700,exist_ok=True)\n if p.stat().st_uid!=996:raise RuntimeError('Unexpected directory owner')\n os.chmod(p,0o700)\np=b/'releases'/"+repr('.upload-'+operation+'.tgz')+"\nfd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)\nos.close(fd)"
    command(SSH+['python3 -B -c '+shlex.quote(prepare)],checkpoint,20)
    command(['scp','-q','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',str(archive),'openclaw:'+BASE+'/releases/.upload-'+operation+'.tgz'],checkpoint,120)
    command(SSH+['python3 -B -c '+shlex.quote(UNPACK)+' '+operation+' '+fingerprint],checkpoint,45)
    activation='cd '+shlex.quote(dest)+'/deploy && python3 -B activate.py --source '+fingerprint+' --instance '+job['id']+' --operation '+operation
    result_file=work/'deploy-result.json';log=work/'deploy-error.log';checkpoint()
    with result_file.open('x',encoding='utf-8') as out,log.open('x',encoding='utf-8') as err:
        process=sp.Popen(SSH+[activation],stdout=out,stderr=err);started=last=time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic()-started>2100:raise RuntimeError('Deployment timed out')
                if time.monotonic()-last>30:checkpoint();last=time.monotonic()
                time.sleep(.25)
            if process.returncode:raise RuntimeError('VPS delivery failed; inspect this operation private deploy-error.log and remote journal')
            checkpoint()
        except BaseException as exc:
            cancel="import os;from pathlib import Path;p=Path("+repr(BASE+'/operations/'+operation+'.cancel')+");assert os.geteuid()==996;assert not any(x.is_symlink() for x in [p,*p.parents]);fd=os.open(p,os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)"
            try:sp.run(SSH+['python3 -B -c '+shlex.quote(cancel)],check=True,capture_output=True,timeout=15)
            except BaseException:pass # Connectivity loss cannot promise remote cancellation; journal recovery is required.
            finally:stop_process(process)
            exc.add_note('Deployment interrupted; cancellation requested. Check remote operation '+operation+' before retrying; connectivity loss cannot guarantee remote cancellation.')
            raise
    result=json.loads(result_file.read_text(encoding='utf-8'))
    if result.get('source')!=fingerprint or result.get('url')!=URL:raise RuntimeError('Unexpected deployment result')
    return result['url']
