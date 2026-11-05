"""Publish curated public dashboard data from the VPS, without model credentials."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat() if t else None


def read_jobs(path, clock=time.time):
    from .jobs import Jobs
    queue = Jobs(path, [], clock=clock)
    try:
        rows = queue.snapshot()['jobs']
        # Renewing a live lease must not cause a public commit every minute.
        return [{k: (None if k == 'updated' and row['state'] == 'running' else row[k])
                 for k in ('candidate', 'version', 'lane', 'state', 'updated')} for row in rows]
    finally:
        queue.close()


def load_ltu_catalog(path):
    if not path.exists():
        return None
    catalog=json.loads(path.read_text(encoding='utf-8'))
    text=lambda value:isinstance(value,str) and bool(value.strip())
    if (not isinstance(catalog,dict) or catalog.get('mode')=='sample' or type(catalog.get('schema_version')) is not int or
            catalog['schema_version']!=1 or not text(catalog.get('generated_at')) or
            not text(catalog.get('directory_url')) or not isinstance(catalog.get('coverage'),dict) or
            not isinstance(catalog.get('subjects'),list)):
        raise ValueError('Invalid LTU research catalog schema')
    for subject in catalog['subjects']:
        if (not isinstance(subject,dict) or not all(text(subject.get(key)) for key in ('id','name','url')) or
                subject.get('review_status') not in ('reviewed','not_reviewed','inaccessible') or
                not isinstance(subject.get('topics',[]),list)):
            raise ValueError('Invalid LTU research subject schema')
        for topic in subject.get('topics',[]):
            if not isinstance(topic,dict) or not all(text(topic.get(key)) for key in ('id','title','url')):
                raise ValueError('Invalid LTU research listing schema')
    json.dumps(catalog,allow_nan=False)
    return catalog


def write_catalog(path,catalog):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                         prefix='.ltu-research-',suffix='.tmp',delete=False) as handle:
            temporary=Path(handle.name)
            json.dump(catalog,handle,ensure_ascii=False,indent=2,allow_nan=False)
            handle.write('\n')
            handle.flush()
            # The publisher's private umask must not make public data unreadable to nginx.
            os.chmod(temporary,0o644)
            os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def compose(seed, catalog, audit, collection, jobs, sources, now, thesis_research=None):
    out=copy.deepcopy(seed)
    visible=set(audit.get('manual_start_ids',[]))
    cards=[copy.deepcopy(c) for c in catalog if c.get('publication')=='owner_requested_visual_summary' and (not audit.get('hold') or c['id'] in visible)]
    for c in cards:
        job=next((j for j in jobs if j['candidate']==c['id'] and j['version']==c['version']),None)
        c.update(recommended=False,selected=bool(job and job['state']!='cancelled'),status=job['state'] if job else 'Possibility')
    out.update(opportunities=cards,audit=audit,connected=True,mode='live',collector_host='vps',generated_at=iso(now))
    latest={}
    for check in collection['checks']:
        if check['checked']>latest.get(check['source'],{}).get('checked',0):latest[check['source']]=check
    source_rows=[]
    for s in sources:
        r={k:s[k] for k in ('id','name','category','url','access')}
        r['status']=latest.get(s['id'],{}).get('status','unavailable');source_rows.append(r)
    out['sources']=source_rows
    out['coverage'].update(registered=len(sources),checked=sum(r['status']=='checked' for r in source_rows),blocked=sum(r['status']=='unavailable' for r in source_rows),source_families=len({r['category'] for r in source_rows if r['status']=='checked'}))
    local=datetime.fromtimestamp(now,ZoneInfo('Europe/Stockholm'));nxt=local.replace(hour=8,minute=0,second=0,microsecond=0)
    if nxt<=local:nxt+=timedelta(days=1)
    out['thesis'].update(last_success=thesis_research.get('last_completed_at') if thesis_research else None,
                        collection_last_success=iso(collection['generated_at']),next_run=nxt.isoformat())
    if thesis_research:
        out['thesis']['research_run']=copy.deepcopy(thesis_research)
    for lane in ('thesis','project'):
        current=[j for j in jobs if any(c['id']==j['candidate'] and c['version']==j['version'] for c in cards) and j['lane']==lane]
        states={j['state'] for j in current}
        state=next((s for s in ('running','needs_attention','quota_wait','queued','paused','completed','review_ready') if s in states),'awaiting_selection')
        out[lane]['state']=state
        if lane=='project':out[lane]['stage']=state.replace('_',' ')
    if thesis_research and out['thesis']['state'] not in ('running','queued'):
        out['thesis']['state']=thesis_research['state']
    out['releases_last_7_days']=sum(j['lane']=='project' and j['state']=='completed' and j['updated']>=now-7*86400 for j in jobs)
    out['events']=[{'title':'VPS publishes directly','detail':'Collection and curated dashboard updates publish to GitHub without the laptop. Only changed public data is committed.'},
      {'title':'Rolling project batches','detail':'When selected builds finish, prepare fresh options without waiting for next week. New builds require selection; automatic defaults remain paused.'},
      {'title':'Subscription analysis','detail':'AI research and builds run on the laptop when available. Collection success is not completed research.'}]
    return out


def main(refresh_assets=False):
    root=Path(__file__).resolve().parents[1]
    checkout=Path('/home/openclaw/ai-dashboard-publish')
    runtime=root/'runtime'
    import fcntl
    with (runtime/'dashboard-publish.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX if refresh_assets else fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        load=lambda p:json.loads(p.read_text(encoding='utf-8'))
        catalog=load(root/'config/public-opportunities.json');audit=load(root/'config/discovery-audit.json')
        collection=load(runtime/'collection.json');sources=load(root/'config/collectors.json');jobs=read_jobs(runtime/'jobs.sqlite')
        # Heartbeats and credentials never enter either the fingerprint or the public snapshot.
        signals_file=root/'config/discovery-signals.json'
        signals=load(signals_file) if signals_file.exists() else None
        batch_file=root/'config/discovery-batches.json'
        batches=load(batch_file) if batch_file.exists() else None
        copy_file=root/'config/opportunity-copy.json'
        presentation=load(copy_file) if copy_file.exists() else {}
        inputs={'catalog':catalog,'audit':audit,'collected_at':collection['generated_at'],'jobs':jobs,'sources':sources,'signals':signals,'batches':batches,'presentation':presentation}
        ltu_catalog=load_ltu_catalog(root/'config/ltu-research.json')
        if ltu_catalog is not None:
            inputs['ltu_research']=ltu_catalog
        fingerprint=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
        receipt=runtime/'dashboard-publish.json'
        unchanged=receipt.exists() and load(receipt).get('fingerprint')==fingerprint
        if unchanged and not refresh_assets:
            print('No public changes; no GitHub request.');return
        env={**os.environ,'GIT_SSH_COMMAND':'ssh -i /home/openclaw/.ssh/ai_dashboard_publish -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/openclaw/.ssh/ai_dashboard_known_hosts'}
        def git(*args):return subprocess.run(['git',*args],cwd=checkout,env=env,check=True,capture_output=True,text=True,timeout=60).stdout.strip()
        if not checkout.exists():
            subprocess.run(['git','clone','git@github.com:achkum/ai-project-lab.git',str(checkout)],env=env,check=True,capture_output=True,timeout=90)
        git('pull','--rebase')
        if unchanged:
            print('Published assets refreshed; no snapshot commit needed.');return
        path=checkout/'docs/data/status.json';seed=load(path)
        snapshot=compose(seed,catalog,audit,collection,jobs,sources,datetime.now(timezone.utc).timestamp(),
                         batches.get('thesis_research') if batches else None)
        if signals: snapshot['discovery_signals']=signals
        if batches:
            snapshot['discovery_run']=batches['last_run']
            current=batches.get('current_project_batch')
            if current:
                snapshot['project']['current_batch']={k:current[k] for k in ('id','project_ids','published_at','state') if k in current}
        snapshot['opportunity_copy']=presentation
        path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        publish_paths=['docs/data/status.json']
        if ltu_catalog is not None:
            write_catalog(checkout/'docs/data/ltu-research.json',ltu_catalog)
            publish_paths.append('docs/data/ltu-research.json')
        git('add','--',*publish_paths)
        if git('diff','--cached','--name-only','--',*publish_paths):
            git('-c','user.name=Lab VPS publisher','-c','user.email=achkum@users.noreply.github.com','commit','--only','-m','Refresh public dashboard from VPS','--',*publish_paths)
        for attempt in range(3):
            try:
                git('push','origin','HEAD:main')
                break
            except subprocess.CalledProcessError:
                if attempt==2:raise
                git('pull','--rebase')
        receipt.write_text(json.dumps({'fingerprint':fingerprint,'published_at':datetime.now(timezone.utc).isoformat(),'commit':git('rev-parse','HEAD')}))
        print('Public dashboard published.')


if __name__=='__main__':main('--refresh-assets' in sys.argv)
