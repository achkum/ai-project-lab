"""Checks and managed localhost delivery for owner-selected operating prototypes.

Model and customer data stay on the laptop. This is not a production-hosting claim.
"""
import hashlib
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from . import background_process as sp
from .allowance import clean_env

_LOCAL_PROCESSES={}
MAX_APP_MEMORY_MB=5120
TOTAL_APP_MEMORY_MB=6144


def reap_local_processes():
    for key,proc in list(_LOCAL_PROCESSES.items()):
        if proc.poll() is not None:_LOCAL_PROCESSES.pop(key,None)


def product_env():
    env=clean_env()
    for name in list(env):
        if name in ('GH_TOKEN','GITHUB_TOKEN') or name.endswith(('_API_KEY','_SECRET','_TOKEN','_PASSWORD')):
            env.pop(name,None)
    env.update(PYTHONUNBUFFERED='1',NO_COLOR='1')
    return env


def contract(workspace,target):
    workspace=Path(workspace).resolve()
    d=json.loads((workspace/'product.json').read_text(encoding='utf-8-sig'))
    if target not in ('static','local_service') or d.get('delivery')!=target:
        raise ValueError('Product delivery does not match the selected scope')
    if not (workspace/'README.md').is_file() or not (workspace/'PRODUCT.md').is_file():
        raise ValueError('Runnable instructions and the selected workflow acceptance record are required')
    if target=='local_service':
        if d.get('runtime') not in ('python','node'):raise ValueError('Supported local runtimes are Python and Node')
        relative=Path(str(d.get('entry','')))
        if relative.is_absolute():raise ValueError('Application entry must be relative')
        entry=workspace/relative
        if not entry.is_file() or entry.is_symlink() or not entry.resolve().is_relative_to(workspace):
            raise ValueError('The application entry must be a real file inside its workspace')
        if entry.suffix not in (('.py',) if d['runtime']=='python' else ('.js','.cjs','.mjs')):raise ValueError('Unsupported application entry')
        if type(d.get('memory_mb')) is not int or not 128<=d['memory_mb']<=MAX_APP_MEMORY_MB:
            raise ValueError(f'Declare a local prototype memory budget between 128 and {MAX_APP_MEMORY_MB} MB')
    return d


def python_for(workspace):
    venv=Path(workspace)/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    return str(venv) if venv.is_file() else sys.executable


def check_product(workspace,target,checkpoint=lambda:None):
    workspace=Path(workspace).resolve();d=contract(workspace,target)
    node=sorted((workspace/'tests').glob('*.test.cjs'))
    py=sorted((workspace/'tests').glob('test*.py'))
    commands=[]
    if node:commands.append(['node','--test',*[str(p) for p in node]])
    if py:commands.append([python_for(workspace),'-m','unittest','discover','-s','tests','-p','test*.py'])
    if not commands:raise ValueError('A working product needs executable acceptance tests')
    validation=workspace/'VALIDATION.txt';validation.write_text('',encoding='utf-8')
    for command in commands:
        checkpoint();offset=validation.stat().st_size
        with validation.open('a',encoding='utf-8') as log:
            log.write('COMMAND: '+' '.join(command)+'\n');log.flush()
            proc=sp.Popen(command,cwd=workspace,stdout=log,stderr=sp.STDOUT,env=product_env())
            started=last=time.monotonic()
            try:
                while proc.poll() is None:
                    if time.monotonic()-started>300:raise RuntimeError('Product checks exceeded five minutes; preserve partial results')
                    if time.monotonic()-last>20:checkpoint();last=time.monotonic()
                    time.sleep(.2)
                checkpoint()
            except BaseException:
                proc.terminate()
                try:proc.wait(timeout=10)
                except sp.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                raise
        with validation.open('rb') as output:output.seek(offset);out=output.read().decode('utf-8',errors='replace')
        if proc.returncode:raise RuntimeError('Product checks failed; inspect private VALIDATION.txt')
        if command[0]!='node' and not re.search(r'Ran [1-9][0-9]* tests?',out):
            raise RuntimeError('Python acceptance suite did not execute any tests')
        if command[0]=='node' and re.search(r'(?:# |ℹ )?tests[: ]+0(?:\s|$)',out):
            raise RuntimeError('Node acceptance suite did not execute any tests')
    return d


def live_instance(url,instance):
    try:
        with urlopen(url+'health',timeout=2) as response:
            data=json.loads(response.read(4096))
        return data.get('ok') is True and data.get('instance')==instance
    except (OSError,ValueError):return False


def process_alive(pid):
    if type(pid) is not int or pid<=0:return False
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return ctypes.get_last_error()==5  # Access denied: preserve it.
        code=wintypes.DWORD()
        try:return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True


def source_fingerprint(workspace):
    digest=hashlib.sha256()
    for p in sorted(Path(workspace).rglob('*')):
        rel=p.relative_to(workspace)
        if p.name.startswith('RELEASE_REVIEW_'):continue
        if any(part.startswith('.') or part in ('node_modules','__pycache__','starter') for part in rel.parts):continue
        if p.is_file() and not p.is_symlink() and p.suffix in ('.py','.js','.cjs','.mjs','.html','.css','.json'):
            digest.update(str(rel).encode());digest.update(p.read_bytes())
    return digest.hexdigest()


def start_local(profile,job,workspace,checkpoint):
    """Only call after independent tests and subscription-verified release review.

    Caller holds the normal publication lock. Existing running versions and data
    are preserved; a later migration is engineering work, never a new approval.
    """
    workspace=Path(workspace).resolve();d=contract(workspace,'local_service')
    reap_local_processes()
    runtime=Path(profile['runtime_root']);registry=runtime/'local-products.json'
    saved=json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else {}
    active={k:v for k,v in saved.items() if process_alive(v['pid'])}
    slug=job['scope']['id'].lower()
    if not re.fullmatch('[a-z0-9-]+',slug):raise ValueError('Invalid product identity')
    if slug in active:
        if active[slug]['job']==job['id'] and active[slug].get('source_hash')==source_fingerprint(workspace) and live_instance(active[slug]['url'],job['id']):return active[slug]['url']
        raise RuntimeError('An earlier local version is running; preserve it and complete a managed data migration')
    if len(active)>=4 or sum(v['memory_mb'] for v in active.values())+d['memory_mb']>TOTAL_APP_MEMORY_MB:
        raise RuntimeError('Local prototype resource budget is in use; preserve existing apps')
    # No service is exposed on a public interface. The app contract consumes HOST/PORT.
    offset=int(hashlib.sha256(slug.encode()).hexdigest()[:8],16)%900
    port=None
    for i in range(900):
        attempt=19100+(offset+i)%900
        try:
            with socket.socket() as probe:probe.bind(('127.0.0.1',attempt))
            port=attempt;break
        except OSError:continue
    if port is None:raise RuntimeError('No localhost prototype port is available')
    app_data=runtime/'local-products'/slug;app_data.mkdir(parents=True,exist_ok=True)
    env=product_env();env.update(HOST='127.0.0.1',PORT=str(port),LAB_DATA_DIR=str(app_data),LAB_INSTANCE_ID=job['id'])
    command=[python_for(workspace) if d['runtime']=='python' else 'node',str((workspace/d['entry']).resolve())]
    url=f'http://127.0.0.1:{port}/'
    checkpoint()
    with (app_data/'server.log').open('a',encoding='utf-8') as log:
        proc=sp.Popen(command,cwd=workspace,env=env,stdin=sp.DEVNULL,stdout=log,stderr=sp.STDOUT)
    try:
        last=time.monotonic()
        for _ in range(45):
            if time.monotonic()-last>20:checkpoint();last=time.monotonic()
            if proc.poll() is not None:raise RuntimeError('Local app exited; inspect its private server log')
            if live_instance(url,job['id']):
                # Confirm the actual Windows listener, not merely the model's promise.
                if os.name=='nt':
                    check=sp.run(['powershell','-NoProfile','-NonInteractive','-Command',
                        f'Get-NetTCPConnection -State Listen -LocalPort {port} | Select-Object LocalAddress,OwningProcess | ConvertTo-Json -Compress'],
                        capture_output=True,text=True,check=True,timeout=15)
                    listeners=json.loads(check.stdout);listeners=listeners if isinstance(listeners,list) else [listeners]
                    if not listeners or any(r['LocalAddress']!='127.0.0.1' or r['OwningProcess']!=proc.pid for r in listeners):
                        raise RuntimeError('Local app must bind only 127.0.0.1 in its managed process')
                with urlopen(url,timeout=10) as page:
                    if 'text/html' not in page.headers.get('Content-Type','') or not page.read(512):
                        raise RuntimeError('Local app did not serve its user interface')
                checkpoint()
                saved[slug]={'job':job['id'],'pid':proc.pid,'url':url,'workspace':str(workspace),'source_hash':source_fingerprint(workspace),'memory_mb':d['memory_mb'],'started_at':time.time()}
                # Keep stopped apps' restart information and data ownership records.
                temp=registry.with_suffix('.next');temp.write_text(json.dumps(saved,indent=2)+'\n',encoding='utf-8');os.replace(temp,registry)
                _LOCAL_PROCESSES[slug]=proc
                return url
            time.sleep(1)
        raise RuntimeError('Local app did not become ready; inspect its private server log')
    except BaseException:
        proc.terminate()
        try:proc.wait(timeout=10)
        except sp.TimeoutExpired:proc.kill()
        raise
