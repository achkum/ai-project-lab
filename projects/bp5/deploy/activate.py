"""Recoverable single-host rollout; never restores over a database containing new writes."""
import argparse, hashlib, json, os, re, signal, subprocess, time, uuid
from pathlib import Path
from urllib.request import urlopen
import backup as storage

BASE=storage.BASE
URL='https://198.44.116.159.sslip.io/apps/bp5/'
NAME='prata-app'
_CANCELLED=False
_OPERATION=None


def cancelled():
    if _CANCELLED or (_OPERATION and storage.checked(BASE/'operations'/(_OPERATION+'.cancel')).exists()):
        raise RuntimeError('Deployment cancelled; recovering managed rollout state')


def run(args,timeout=120,honor_cancel=True,**kwargs):
    if honor_cancel:cancelled()
    with subprocess.Popen(args,text=True,stdout=kwargs.pop('stdout',subprocess.PIPE),stderr=kwargs.pop('stderr',subprocess.PIPE),start_new_session=True,**kwargs) as proc:
        started=time.monotonic()
        try:
            while True:
                try:
                    stdout,stderr=proc.communicate(timeout=.25);break
                except subprocess.TimeoutExpired:
                    if honor_cancel:cancelled()
                    if time.monotonic()-started>timeout:raise RuntimeError('Managed command timed out')
            if proc.returncode:raise RuntimeError('Managed command failed: '+str(args[0]))
            return subprocess.CompletedProcess(args,proc.returncode,stdout,stderr)
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate(timeout=5)
            raise


def inspect(name):
    result=subprocess.run(['docker','inspect',name],text=True,capture_output=True,timeout=20)
    if result.returncode:
        if 'no such object' in result.stderr.lower() or 'no such container' in result.stderr.lower():return None
        raise RuntimeError('Docker inspection failed; preserving existing state')
    return json.loads(result.stdout)[0]


def labels(container):return container.get('Config',{}).get('Labels') or {}


def identity(container):
    env=dict(x.split('=',1) for x in container['Config'].get('Env',[]) if '=' in x)
    return env.get('LAB_INSTANCE_ID','')


def wait_ready(port,instance,honor_cancel=True):
    for _ in range(60):
        if honor_cancel:cancelled()
        try:
            with urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as r:health=json.load(r)
            with urlopen(f'http://127.0.0.1:{port}/ready',timeout=2) as r:ready=json.load(r)
            if health.get('instance')==instance and ready.get('ok') is True:return
        except (OSError,ValueError):pass
        time.sleep(1)
    raise RuntimeError('Service did not pass liveness and readiness checks')


def start(name,image,data,port,instance,source,restart,operation):
    storage.directory(data)
    values={'HOST':'127.0.0.1','PORT':str(port),'LAB_DATA_DIR':'/data','LAB_INSTANCE_ID':instance,
        'BP5_PUBLIC_ORIGIN':'https://198.44.116.159.sslip.io','BP5_COOKIE_PATH':'/apps/bp5/',
        'BP5_SECURE_COOKIE':'1','BP5_ALLOWED_HOSTS':f'127.0.0.1:{port}',
        'BP5_FFMPEG':'/usr/bin/ffmpeg','BP5_WHISPER_BIN':'/usr/local/bin/whisper-cli',
        'BP5_WHISPER_MODEL':'/models/kb-whisper-base-q5_0.bin','BP5_PIPER_BIN':'/models/piper/piper',
        'BP5_PIPER_MODEL':'/models/sv-se-nst-medium.onnx'}
    args=['docker','run','-d','--name',name,'--network','host','--read-only','--user','996:987',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64',
        '--memory','1536m','--memory-swap','1536m','--cpus','1.8','--restart',restart,
        '--log-opt','max-size=10m','--log-opt','max-file=3',
        '--label','com.prata.managed=1','--label','com.prata.source='+source,'--label','com.prata.operation='+operation,
        '--tmpfs','/tmp:rw,nosuid,noexec,size=64m,mode=1777',
        '-v',str(data)+':/data','-v',str(storage.checked(BASE/'runtime','dir'))+':/models:ro',
        '--health-cmd',f'python -c "import urllib.request; urllib.request.urlopen(\'http://127.0.0.1:{port}/ready\',timeout=3)"',
        '--health-interval','60s','--health-timeout','5s','--health-retries','3','--health-start-period','30s']
    for key,value in values.items():args+=['-e',key+'='+value]
    run(args+[image],honor_cancel=False);cancelled();wait_ready(port,instance)


def save(state):storage.atomic_json(BASE/'operations'/(state['operation']+'.json'),state)


def remove_owned(name,operation):
    container=inspect(name)
    if container:
        if labels(container).get('com.prata.managed')!='1' or labels(container).get('com.prata.operation')!=operation:
            raise RuntimeError('Refusing to remove a container owned by another rollout')
        run(['docker','rm','-f',container['Id']],honor_cancel=False)


def cleanup(state):
    remove_owned(state['candidate'],state['operation'])
    trial=storage.checked(BASE/'candidate-data'/state['operation'],'dir')
    if trial.exists():
        if storage.in_use(trial,storage.active_mounts()):raise RuntimeError('Candidate data is still mounted by an active container')
        storage.remove_tree(trial,BASE/'candidate-data')


def recover(state):
    # This can be re-run after a process/SSH failure; container IDs identify the old service.
    operation=state['operation']
    if not re.fullmatch('[a-f0-9]{32}',operation):raise RuntimeError('Invalid recovery journal')
    try:
        if state.get('cutover'):
            current=inspect(NAME)
            if current and current['Id']!=state.get('old_id'):remove_owned(NAME,operation)
            if state.get('old_id'):
                old=inspect(state['old_id'])
                if not old or labels(old).get('com.prata.managed')!='1':raise RuntimeError('Previous managed container is missing; database preserved')
                if old.get('Name','').lstrip('/')!=NAME:run(['docker','rename',old['Id'],NAME],honor_cancel=False)
                run(['docker','update','--restart='+state['old_restart'],NAME],honor_cancel=False)
                if state.get('old_running'):
                    if not inspect(NAME)['State']['Running']:run(['docker','start',NAME],honor_cancel=False)
                    wait_ready(8788,state['old_instance'],honor_cancel=False)
            # Never overwrite live data. Recovery snapshots are encrypted ordinary backups.
            # Backward-compatible migrations are required for automatic container rollback.
    finally:cleanup(state)
    state['phase']='recovered';save(state)


def recover_pending():
    for path in sorted((BASE/'operations').glob('*.json')):
        if not re.fullmatch(r'[a-f0-9]{32}\.json',path.name):continue
        storage.checked(path,'file');state=json.loads(path.read_text())
        if state.get('phase')=='complete':
            if not state.get('cleanup_done'):cleanup(state);state['cleanup_done']=True;save(state)
        elif state.get('phase')!='recovered':
            try:recover(state)
            except BaseException:
                state['phase']='recovery_failed';save(state)
                raise RuntimeError('An interrupted rollout needs operator recovery; database and snapshot preserved') from None


def verify_release(release,source):
    manifest=json.loads(storage.checked(release/'release-manifest.json','file').read_text())
    rows=manifest['files']
    expected=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if manifest.get('source')!=source or expected!=source:raise RuntimeError('Release manifest mismatch')
    for row in rows:
        path=storage.checked(release/row['path'],'file')
        if not path.is_relative_to(release) or path.stat().st_size!=row['size'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise RuntimeError('Release source changed after packaging')
    files={p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file() or p.is_symlink()}
    if files!={row['path'] for row in rows}|{'release-manifest.json'}:raise RuntimeError('Unexpected file in release source')


def activate(source,instance,operation=None):
    global _OPERATION
    if not re.fullmatch('[a-f0-9]{64}',source) or not re.fullmatch('[a-zA-Z0-9_-]{1,80}',instance):raise ValueError('Invalid release identity')
    operation=operation or uuid.uuid4().hex
    if not re.fullmatch('[a-f0-9]{32}',operation):raise ValueError('Invalid operation identity')
    storage.operator();storage.directory(BASE)
    for name in ('operations','candidate-data','rollback'):storage.directory(BASE/name)
    _OPERATION=operation
    with storage.locked('deploy.lock'):
        recover_pending();cancelled()
        release=storage.checked(BASE/'releases'/source,'dir')
        if not storage.checked(release/'deploy/Dockerfile','file').is_file():raise RuntimeError('Release sources are missing')
        verify_release(release,source)
        # Legacy fixed-name snapshots are never replayed; daily maintenance expires them.
        storage.checked(BASE/'rollback.sqlite3','file')
        old=inspect(NAME)
        if old and labels(old).get('com.prata.managed')!='1':raise RuntimeError('Existing container is not managed Prata; preserving it')
        if old and labels(old).get('com.prata.source')==source and old['State']['Running']:
            wait_ready(8788,identity(old));return {'url':URL,'source':source,'instance':identity(old),'already_running':True}
        for path in ['piper/piper','sv-se-nst-medium.onnx','sv-se-nst-medium.onnx.json','kb-whisper-base-q5_0.bin','age/age']:
            if not storage.checked(BASE/'runtime'/path,'file').is_file():raise RuntimeError('Pinned speech/backup runtime is not installed')
        recipient=storage.checked(BASE/'backup-recipient.txt','file').read_text().strip()
        if not re.fullmatch(r'age1[a-z0-9]{58}',recipient):raise RuntimeError('Backup encryption recipient is not configured')
        state={'operation':operation,'source':source,'instance':instance,'phase':'preparing','cutover':False,
            'candidate':'prata-check-'+operation,'old_id':old['Id'] if old else None,
            'old_running':bool(old and old['State']['Running']),'old_instance':identity(old) if old else '',
            'old_restart':(old.get('HostConfig',{}).get('RestartPolicy',{}).get('Name') or 'no') if old else 'no'}
        if old and state['old_restart']=='on-failure':state['old_restart']+=':'+str(old.get('HostConfig',{}).get('RestartPolicy',{}).get('MaximumRetryCount',0))
        save(state);image='prata:'+source;data=storage.directory(BASE/'data');trial=BASE/'candidate-data'/operation
        try:
            log=storage.checked(BASE/'operations'/(operation+'-build.log'),'file')
            with log.open('x') as output:run(['docker','build','-t',image,'-f','deploy/Dockerfile','.'],cwd=release,stdout=output,stderr=subprocess.STDOUT,timeout=1800)
            if trial.exists():raise RuntimeError('Candidate directory already exists')
            storage.directory(trial)
            if storage.checked(data/'production.sqlite3','file').exists():storage.snapshot(data/'production.sqlite3',trial/'production.sqlite3')
            start(state['candidate'],image,trial,8789,instance,source,'no',operation)
            remove_owned(state['candidate'],operation)
            # Journal BEFORE the first mutation; even stop/rename/copy failures recover the old ID.
            state['cutover']=True;state['phase']='cutover';save(state);cancelled()
            if old:
                run(['docker','update','--restart=no',old['Id']],honor_cancel=False);run(['docker','stop','-t','25',old['Id']],honor_cancel=False);run(['docker','rename',old['Id'],'prata-previous-'+operation],honor_cancel=False)
            if storage.checked(data/'production.sqlite3','file').exists():
                state['recovery_backup']=storage.backup().get('filename');save(state)
            start(NAME,image,data,8788,instance,source,'unless-stopped',operation)
            with urlopen(URL+'health',timeout=15) as r:health=json.load(r)
            with urlopen(URL+'ready',timeout=15) as r:ready=json.load(r)
            if health.get('instance')!=instance or ready.get('ok') is not True:raise RuntimeError('Public HTTPS route does not serve this release')
            cancelled();storage.backup();cancelled()
            record={'url':URL,'source':source,'instance':instance,'image':image,'deployed_at':time.time(),
                'previous_container':'prata-previous-'+operation if old else None,'memory_mb':1536,'cpu_limit':1.8,'voice_inference_parallelism':1}
            storage.atomic_json(BASE/'deployment.json',record)
            state['phase']='complete';save(state)
        except BaseException:
            try:recover(state)
            except BaseException:
                state['phase']='recovery_failed';save(state)
                raise RuntimeError('Rollout failed and recovery is incomplete; preserved journal, snapshot and active database') from None
            raise
        # Cleanup failure after commit must not roll back a healthy, publicly used service.
        try:cleanup(state);state['cleanup_done']=True;save(state)
        except BaseException:record['cleanup_pending']=True;storage.atomic_json(BASE/'deployment.json',record)
        return record


if __name__=='__main__':
    def cancel_signal(*_):
        global _CANCELLED
        _CANCELLED=True
    for sig in (signal.SIGHUP,signal.SIGTERM,signal.SIGINT):signal.signal(sig,cancel_signal)
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--instance',required=True);p.add_argument('--operation');args=p.parse_args()
    print(json.dumps(activate(args.source,args.instance,args.operation)))
