"""Import metadata via existing pinned SSH; never share a live SQLite file."""
import json
import math
import subprocess
import time
from urllib.parse import urlsplit

def import_collection(discovery,packet,sources):
    allowed={s['id'] for s in sources}
    stamp=packet.get('generated_at')
    if packet.get('version')!=1 or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):
        raise ValueError('Invalid collector snapshot')
    if not -300<=time.time()-stamp<=48*3600:
        raise ValueError('Collector snapshot stale or future-dated')
    for r in packet['checks']:
        if r['source'] not in allowed or r['status'] not in ('checked','empty','unavailable') or type(r['count']) is not int or r['count']<0:
            raise ValueError('Invalid source check')
    ids={r['id'] for r in packet['evidence']}
    for r in packet['evidence']:
        if urlsplit(r['url']).scheme not in ('http','https') or not isinstance(r['title'],str):
            raise ValueError('Invalid evidence metadata')
    for r in packet['provenance']:
        if r['source'] not in allowed or r['evidence'] not in ids:
            raise ValueError('Invalid provenance')
    with discovery.db:
        for r in packet['checks']:
            if not discovery.db.execute('SELECT 1 FROM checks WHERE source=? AND checked=?',(r['source'],r['checked'])).fetchone():
                discovery.db.execute('INSERT INTO checks(source,checked,status,error,count) VALUES(?,?,?,?,?)',tuple(r[k] for k in ('source','checked','status','error','count')))
        for r in packet['evidence']:
            discovery.db.execute('''INSERT INTO evidence VALUES(?,?,?,?,?,?,?) ON CONFLICT(url)
              DO UPDATE SET last_seen=MAX(last_seen,excluded.last_seen),title=excluded.title,summary=excluded.summary,published=excluded.published''',tuple(r[k] for k in ('id','url','title','summary','published','first_seen','last_seen')))
        for r in packet['provenance']:
            discovery.db.execute('INSERT OR IGNORE INTO provenance VALUES(?,?)',(r['evidence'],r['source']))
    return {'mode':'vps_import','snapshot_at':stamp,'records':len(packet['evidence'])}

def pull(discovery,sources):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
                           'openclaw','cat /home/openclaw/ai-discovery/runtime/collection.json'],capture_output=True,timeout=60)
    if result.returncode:
        raise RuntimeError('VPS collection unavailable; local evidence retained. Check SSH and collector service.')
    if len(result.stdout)>20_000_000:
        raise ValueError('Collector snapshot exceeds transport bound')
    return import_collection(discovery,json.loads(result.stdout.decode('utf-8')),sources)
