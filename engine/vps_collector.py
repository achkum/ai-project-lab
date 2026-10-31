"""Standalone collector: no GitHub credentials, model login or build execution."""
import json
import time
from pathlib import Path
from .discovery import Discovery

def main():
    root=Path(__file__).resolve().parent.parent
    sources=json.loads((root/'config/collectors.json').read_text(encoding='utf-8'))
    d=Discovery(root/'runtime/evidence.sqlite')
    try:
        results=d.collect(sources)
        now=time.time()
        packet={'version':1,'generated_at':now,
                'checks':[dict(r) for r in d.db.execute('SELECT source,checked,status,error,count FROM checks WHERE checked>=?',(now-7*86400,))],
                'evidence':[dict(r) for r in d.db.execute('SELECT * FROM evidence WHERE last_seen>=?',(now-30*86400,))],
                'provenance':[dict(r) for r in d.db.execute('SELECT p.* FROM provenance p JOIN evidence e ON p.evidence=e.id WHERE e.last_seen>=?',(now-30*86400,))]}
        path=root/'runtime/collection.json'
        path.with_suffix('.tmp').write_text(json.dumps(packet,ensure_ascii=False),encoding='utf-8')
        path.with_suffix('.tmp').replace(path)
        c=d.coverage(sources)
        print(json.dumps({'checked':c['checked'],'source_families':c['source_families'],
                          'empty':sum(r['status']=='empty' for r in c['rows']),
                          'unavailable':c['blocked'],'new_checks':len(results),'snapshot_at':now}))
    finally: d.close()

if __name__=='__main__': main()
