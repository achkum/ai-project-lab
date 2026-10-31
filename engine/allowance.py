"""Read subscription limits through the authenticated local Codex app server."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from .subscription import validate_allowance
from pathlib import Path


def codex_executable():
    profile=Path(__file__).resolve().parents[1]/'config/profile.local.json'
    configured=json.loads(profile.read_text()).get('codex_executable') if profile.exists() else None
    value=configured or shutil.which('codex')
    if not value or not Path(value).is_file():raise RuntimeError('Codex CLI path is unavailable; update local profile')
    return value


def clean_env():
    return {k:v for k,v in os.environ.items() if not k.startswith(('OPENAI_','ANTHROPIC_','BROWSER_USE_')) and k not in ('CODEX_API_KEY','CODEX_HOME')}


def fresh_proof():
    p=subprocess.Popen([codex_executable(),'app-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,text=True,encoding='utf-8',env=clean_env())
    inbox=queue.Queue()
    def read():
        for line in p.stdout:
            try:inbox.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=read,daemon=True).start()
    def request(mid,method,params=None):
        p.stdin.write(json.dumps({'id':mid,'method':method,**({'params':params} if params is not None else {})})+'\n');p.stdin.flush()
        deadline=time.time()+45
        while time.time()<deadline:
            msg=inbox.get(timeout=max(.1,deadline-time.time()))
            if msg.get('id')==mid:
                if 'error' in msg:raise RuntimeError('Usage check failed: '+str(msg['error'].get('message','unknown')))
                return msg['result']
        raise RuntimeError('Usage check timed out')
    try:
        request(1,'initialize',{'clientInfo':{'name':'personal_ai_lab','title':'Personal AI Lab','version':'1.0'}})
        p.stdin.write('{"method":"initialized"}\n');p.stdin.flush()
        account=request(2,'account/read',{'refreshToken':False})
        if (account.get('account') or {}).get('type')!='chatgpt':raise RuntimeError('ChatGPT subscription login required')
        usage=request(3,'account/rateLimits/read')
        proof={'checked_at':time.time(),'usage':usage}
        validate_allowance(proof)
        return proof
    finally:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill()

if __name__=='__main__':
    proof=fresh_proof()
    print(json.dumps({'verified':True,'ordinaryUsageAllowed':proof['usage'].get('ordinaryUsageAllowed')}))
