"""Local coordinator CLI. Run python -m engine.lab --help from the public repo."""
import argparse
import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .discovery import Discovery
from .workflow import Workflow
from .github_control import publish, sync


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp is not None else None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def export(profile, workflow, discovery, sources):
    coverage = discovery.coverage(sources)
    now = time.time()
    rows = workflow.rows()
    def lane_state(lane):
        return next((r for r in rows if r['lane'] == lane), None)
    thesis, project = lane_state('thesis'), lane_state('project')
    success = discovery.db.execute("SELECT MAX(checked) FROM checks WHERE status='checked'").fetchone()[0]
    local = datetime.now(ZoneInfo('Europe/Stockholm'))
    next_run = local.replace(hour=8, minute=0, second=0, microsecond=0)
    if next_run <= local:
        next_run += timedelta(days=1)
    scheduled = profile.get('scheduler_status') == 'active'
    decisions = []
    for r in rows:
        if not r['issue_url']:
            continue
        decisions.append({'id': r['id'], 'lane': r['lane'], 'state': r['state'], 'url': r['issue_url'],
                          'deadline': iso(r['deadline']), 'selection_origin': r['origin'],
                          'recommended': json.loads(r['document'])['recommended'], 'selected': r['selected']})
    snapshot = {
        'schema_version': 1, 'mode': 'live', 'generated_at': iso(now), 'connected': True,
        'thesis': {'state': thesis['state'] if thesis else 'research_collected', 'last_success': iso(success),
                   'next_run': next_run.isoformat() if scheduled else None},
        'project': {'state': project['state'] if project else 'awaiting_shortlist',
                    'stage': project['state'].replace('_', ' ') if project else 'Evidence collected; analysis pending',
                    'window_start': iso(project['decided']) if project else None,
                    'target_at': iso(project['decided'] + 7*86400) if project and project['decided'] else None},
        'releases_last_7_days': sum(r['lane']=='project' and r['state']=='completed' and
            bool(workflow.db.execute("SELECT 1 FROM events WHERE shortlist=? AND kind='completed' AND occurred>=?", (r['id'],now-7*86400)).fetchone()) for r in rows),
        'usage': {'spent_sek': 0, 'limit_sek': 0},
        'coverage': {k: coverage[k] for k in ('checked','target','registered','blocked','source_families')},
        'sources': [{k: s[k] for k in ('id','name','category','url','access','status')} for s in coverage['rows']],
        'opportunities': [], 'decisions': decisions,
        'collector_host': profile.get('collector_host','laptop'),
        'events': [
            {'title': 'Collector host', 'detail': 'VPS collects daily at 07:30 Stockholm while the laptop is off. Analysis/builds and dashboard synchronization wait for the laptop.' if profile.get('collector_host')=='vps' else 'Collection runs on the laptop.'},
            {'title': 'Public collection connected', 'detail': f"{coverage['checked']} channels returned records across {coverage['source_families']} source families in seven days. Counts are not validated market opportunities."},
            {'title': 'Local subscription workflow', 'detail': 'Daily discovery and recurring project checks scheduled.' if scheduled else 'Coordinator works locally. Recurring scheduling is not yet active.'},
            {'title': 'Options before work', 'detail': 'Open a private shortlist to choose or hold. After 24 hours without a response, the recommendation is selected on the next successful check.'}
        ]}
    # Construct an allowlist object; never merge private candidate dictionaries into this output.
    write_json(Path(profile['public_root'])/'docs/data/status.json', snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Local-first lab coordinator; no paid model APIs')
    parser.add_argument('--profile', default='config/profile.local.json')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('collect')
    sub.add_parser('status')
    sub.add_parser('cycle')
    sub.add_parser('export')
    sub.add_parser('backup')
    submit = sub.add_parser('submit'); submit.add_argument('file')
    pub = sub.add_parser('publish'); pub.add_argument('id')
    claim = sub.add_parser('claim'); claim.add_argument('lane', choices=['thesis','project'])
    for cmd in ('check','heartbeat','finish'):
        p = sub.add_parser(cmd); p.add_argument('id'); p.add_argument('token')
        if cmd == 'finish': p.add_argument('result')
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text(encoding='utf-8'))
    root = Path(profile['runtime_root'])
    sources = json.loads((Path(profile['public_root'])/'config/collectors.json').read_text(encoding='utf-8'))
    flow = Workflow(root/'workflow.sqlite', profile['owner'], profile['private_repo'])
    discovery = Discovery(root/'evidence.sqlite')
    try:
        if args.command == 'collect':
            if profile.get('collector_host') == 'vps':
                from .remote import pull
                result = pull(discovery,sources)
            else:
                result = discovery.collect(sources)
            write_json(Path(profile['private_root'])/'digests/latest-evidence.json', discovery.digest(sources))
        elif args.command == 'submit':
            result = {'id': flow.submit(json.loads(Path(args.file).read_text(encoding='utf-8')))}
        elif args.command == 'publish':
            row = publish(flow, args.id, profile.get('review_window_hours',24))
            result = {k: row[k] for k in ('id','state','issue_url','deadline')}
        elif args.command in ('cycle','claim','check','finish'):
            verified, commands = sync(flow)
            chosen = flow.tick(verified)
            result = {'automatic_selections': chosen, 'commands': commands}
            if args.command == 'claim': result = flow.claim(args.lane)
            elif args.command == 'check':
                row = flow.check(args.id, args.token)
                result = {'valid': True, 'state': row['state']}
            elif args.command == 'finish':
                flow.finish(args.id, args.token, json.loads(Path(args.result).read_text(encoding='utf-8')))
                result = {'state':'completed'}
        elif args.command == 'heartbeat':
            # Re-read remote decisions before extending a worker lease.
            sync(flow)
            flow.heartbeat(args.id, args.token)
            result = {'renewed': True}
        elif args.command == 'backup':
            import sqlite3
            backup = root/'backups'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
            backup.mkdir(parents=True, exist_ok=True)
            for name, db in [('workflow',flow.db),('evidence',discovery.db)]:
                with sqlite3.connect(backup/(name+'.sqlite')) as target:
                    db.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Backup integrity failed')
            result = {'backup': str(backup), 'integrity': 'ok', 'off_device': False}
        else:
            result = {'lanes': [{k:r[k] for k in ('id','lane','state','deadline','origin','issue_url')} for r in flow.rows()],
                      'coverage': {k:v for k,v in discovery.coverage(sources).items() if k!='rows'}}
        export(profile, flow, discovery, sources)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        flow.close(); discovery.close()


if __name__ == '__main__':
    main()
