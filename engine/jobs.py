"""Durable multi-selection queue. Public API never accepts code or shell commands."""
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager


class Jobs:
    def __init__(self, path, catalog, clock=time.time):
        self.clock = clock
        self.catalog = {x['id']: x for x in catalog}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, candidate TEXT, version INTEGER,
          lane TEXT, title TEXT, scope TEXT, state TEXT, created REAL, updated REAL,
          token TEXT, lease_until REAL, message TEXT, result TEXT,
          UNIQUE(candidate,version));
        CREATE UNIQUE INDEX IF NOT EXISTS serial_worker ON jobs((1)) WHERE state='running';
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, digest TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS worker(id INTEGER PRIMARY KEY CHECK(id=1), seen REAL, detail TEXT);
        CREATE TABLE IF NOT EXISTS job_events(id INTEGER PRIMARY KEY, job TEXT, at REAL, action TEXT);
        ''')

    def close(self): self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def event(self, job, action):
        self.db.execute('INSERT INTO job_events(job,at,action) VALUES(?,?,?)',(job,self.clock(),action))

    def enqueue(self, items, request_id):
        if not isinstance(request_id,str) or not 8 <= len(request_id) <= 100:
            raise ValueError('A request ID is required')
        if not isinstance(items,list) or not 1 <= len(items) <= 12:
            raise ValueError('Select between one and twelve options')
        cards=[]
        for item in items:
            if not isinstance(item,dict): raise ValueError('Invalid selection')
            c=self.catalog.get(item.get('id'))
            if not c or type(item.get('version')) is not int or c['version']!=item['version']:
                raise ValueError('Unknown or outdated option; refresh the dashboard')
            if c.get('archived'): raise ValueError('This option is archived')
            cards.append(c)
        digest=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
        with self.transaction():
            old=self.db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
            if old:
                if old['digest']!=digest: raise ValueError('Request ID reused with different options')
                return json.loads(old['result'])
            ids=[]
            for c in cards:
                existing=self.db.execute('SELECT id,scope FROM jobs WHERE candidate=? AND version=?',(c['id'],c['version'])).fetchone()
                if existing:
                    transient={'published_at','review_deadline','status','selected','recommended','decision_url'}
                    stable=lambda card:{k:v for k,v in card.items() if k not in transient}
                    if stable(json.loads(existing['scope']))!=stable(c):
                        raise ValueError('Option scope changed without a version bump; refresh after the catalog is corrected')
                    ids.append(existing['id']); continue
                jid=uuid.uuid4().hex
                now=self.clock()
                self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL,?,NULL)',
                    (jid,c['id'],c['version'],c['lane'].lower(),c['title'],json.dumps(c),'queued',now,now,'Waiting for the laptop worker'))
                self.event(jid,'owner_started'); ids.append(jid)
            ids=list(dict.fromkeys(ids))
            self.db.execute('INSERT INTO requests VALUES(?,?,?)',(request_id,digest,json.dumps(ids)))
        return ids

    def snapshot(self):
        rows=[]
        for r in self.db.execute('SELECT * FROM jobs ORDER BY created'):
            # Never expose execution leases or private artifact content to the browser.
            rows.append({k:r[k] for k in ('id','candidate','version','lane','title','state','created','updated','message')}
                        | {'result':json.loads(r['result']) if r['result'] else None})
        w=self.db.execute('SELECT seen,detail FROM worker WHERE id=1').fetchone()
        return {'jobs':rows,'worker':{'online':bool(w and self.clock()-w['seen']<100),
                'last_seen':w['seen'] if w else None,'detail':w['detail'] if w else 'Laptop worker has not connected'}}

    def seen(self, detail='Ready; one job at a time'):
        self.db.execute('INSERT OR REPLACE INTO worker VALUES(1,?,?)',(self.clock(),str(detail)[:250]))

    def claim(self):
        with self.transaction():
            now=self.clock()
            # Lost leases need review, never launch a second copy of possibly running work.
            self.db.execute("UPDATE jobs SET state='needs_attention',token=NULL,lease_until=NULL,message='Worker disconnected; review partial work before resuming',updated=? WHERE state='running' AND lease_until<=?",(now,now))
            if self.db.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone(): return None
            r=self.db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
            if not r: return None
            token=uuid.uuid4().hex
            self.db.execute("UPDATE jobs SET state='running',token=?,lease_until=?,updated=?,message='Starting scoped work' WHERE id=?",(token,now+180,now,r['id']))
            self.event(r['id'],'worker_started')
            return {'id':r['id'],'token':token,'scope':json.loads(r['scope']),'lane':r['lane']}

    def check(self, jid, token):
        r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not r or r['state']!='running' or not token or r['token']!=token or r['lease_until']<=self.clock():
            raise ValueError('Job stopped or lease expired')
        return r

    def heartbeat(self,jid,token,message='Working'):
        with self.transaction():
            self.check(jid,token)
            self.db.execute('UPDATE jobs SET lease_until=?,updated=?,message=? WHERE id=?',(self.clock()+180,self.clock(),str(message)[:400],jid))

    def finish(self,jid,token,state,message,result=None):
        if state not in ('review_ready','needs_attention','quota_wait'): raise ValueError('Invalid completion state')
        if result is not None:
            if not isinstance(result,dict) or set(result)-{'url','summary','files','validation'}: raise ValueError('Invalid result')
            url=result.get('url','')
            if url and not url.startswith('https://github.com/achkum/ai-thesis-lab/tree/main/research/jobs/'): raise ValueError('Invalid artifact URL')
        with self.transaction():
            self.check(jid,token)
            self.db.execute('UPDATE jobs SET state=?,message=?,result=?,token=NULL,lease_until=NULL,updated=? WHERE id=?',
                (state,str(message)[:400],json.dumps(result) if result else None,self.clock(),jid))
            self.event(jid,state)

    def control(self,jid,action):
        if action not in ('pause','resume','cancel'): raise ValueError('Invalid action')
        with self.transaction():
            r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not r: raise ValueError('Unknown job')
            if action=='resume' and r['state'] not in ('paused','needs_attention','quota_wait'):
                raise ValueError('Only paused or blocked jobs can resume')
            if r['state'] in ('review_ready','cancelled'): raise ValueError('Job is already closed')
            state={'pause':'paused','resume':'queued','cancel':'cancelled'}[action]
            self.db.execute('UPDATE jobs SET state=?,token=NULL,lease_until=NULL,updated=?,message=? WHERE id=?',
                (state,self.clock(),'Owner requested '+action,jid))
            self.event(jid,'owner_'+action)


def main():
    import sys
    root=Path(__file__).resolve().parents[1]
    req=json.load(sys.stdin)
    q=Jobs(root/'runtime/jobs.sqlite',json.loads((root/'config/public-opportunities.json').read_text()))
    try:
        op=req.pop('op')
        if op not in ('snapshot','seen','claim','check','heartbeat','finish','enqueue','control'): raise ValueError('Unknown operation')
        result=getattr(q,op)(**req)
        if isinstance(result,sqlite3.Row): result={'valid':True}
        print(json.dumps({'ok':True,'result':result}))
    except Exception as e:
        print(json.dumps({'ok':False,'error':str(e)}));sys.exit(1)
    finally:q.close()

if __name__=='__main__':main()
