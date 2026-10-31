"""Bounded public RSS/Atom/API collection. Stores metadata, never full articles."""
import concurrent.futures
import hashlib
import html
import json
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

AGENT = "ResearchBuildLab/1.0 (personal research; public feed metadata only)"


def fetch(url):
    if urlsplit(url).scheme != 'https':
        raise ValueError('HTTPS required')
    req = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json, application/atom+xml, application/rss+xml, application/xml, text/xml'})
    with urllib.request.urlopen(req, timeout=18) as response:
        content = response.read(3_000_001)
        if len(content) > 3_000_000:
            raise ValueError('Response exceeds metadata limit')
        return content


def clean(value, limit=300):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', ' ', str(value or '')))).strip()[:limit]


def parse(source, raw):
    kind = source['kind']
    if kind == 'feed':
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('XML entity declarations rejected')
        root = ET.fromstring(raw)
        rows = []
        for item in root.iter():
            if item.tag.rsplit('}', 1)[-1] not in ('entry', 'item'):
                continue
            fields = {child.tag.rsplit('}', 1)[-1]: child for child in item}
            def val(key):
                return ''.join(fields[key].itertext()) if key in fields else ''
            links = [x for x in item if x.tag.rsplit('}', 1)[-1] == 'link']
            link = next((x.get('href') for x in links if x.get('href') and x.get('rel', 'alternate') == 'alternate'), val('link'))
            rows.append({'title': val('title'), 'url': link, 'published': val('published') or val('pubDate') or val('updated'),
                         'summary': ''})
    else:
        data = json.loads(raw)
        if isinstance(data, dict) and (data.get('error_id') or data.get('backoff')):
            raise ValueError('API rate limit/backoff; wait until next scheduled collection')
        if kind == 'stack':
            rows = [{'title': x['title'], 'url': x['link'], 'published': x.get('creation_date'), 'summary': ''} for x in data['items']]
        elif kind == 'github':
            rows = [{'title': x['full_name'], 'url': x['html_url'], 'published': x['created_at'], 'summary': clean(x.get('description'), 200)} for x in data['items']]
        elif kind == 'hn':
            rows = [{'title': x.get('title'), 'url': 'https://news.ycombinator.com/item?id=' + x['objectID'], 'published': x.get('created_at'), 'summary': ''} for x in data['hits']]
        elif kind == 'huggingface':
            rows = [{'title': x['id'], 'url': 'https://huggingface.co/datasets/' + x['id'], 'published': x.get('lastModified'), 'summary': ''} for x in data]
        else:
            raise ValueError('Unsupported connector')
    result = []
    for x in rows[:20]:
        url = x.get('url') or ''
        if not urlsplit(url).hostname or urlsplit(url).scheme not in ('https', 'http'):
            continue
        title = clean(x['title'])
        if title:
            result.append({'title': title, 'url': url, 'published': x.get('published'), 'summary': clean(x.get('summary'), 200)})
    return result


class Discovery:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY,source TEXT,checked REAL,status TEXT,error TEXT,count INTEGER);
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,url TEXT UNIQUE,title TEXT,summary TEXT,published TEXT,first_seen REAL,last_seen REAL);
        CREATE TABLE IF NOT EXISTS provenance(evidence TEXT,source TEXT,PRIMARY KEY(evidence,source));
        ''')

    def close(self):
        self.db.close()

    def collect(self, sources, force=False):
        now = time.time()
        due = []
        for s in sources:
            last = self.db.execute('SELECT MAX(checked) FROM checks WHERE source=?', (s['id'],)).fetchone()[0]
            zone = ZoneInfo('Europe/Stockholm')
            if force or last is None or datetime.fromtimestamp(last,zone).date() != datetime.fromtimestamp(now,zone).date():
                due.append(s)
        def one(s):
            try:
                recent = (datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()
                records = parse(s, fetch(s['endpoint'].replace('{recent_date}',recent)))
                return s, records, 'checked' if records else 'empty', ''
            except Exception as exc:
                # Never retain raw response bodies or credentials in errors.
                return s, [], 'unavailable', type(exc).__name__ + ': ' + str(exc)[:160]
        outcomes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for s, rows, status, error in pool.map(one, due):
                self.db.execute('INSERT INTO checks(source,checked,status,error,count) VALUES(?,?,?,?,?)', (s['id'], now, status, error, len(rows)))
                for item in rows:
                    eid = hashlib.sha256(item['url'].encode()).hexdigest()[:24]
                    self.db.execute('''INSERT INTO evidence VALUES(?,?,?,?,?,?,?) ON CONFLICT(url)
                      DO UPDATE SET last_seen=excluded.last_seen''',
                      (eid, item['url'], item['title'], item['summary'], json.dumps(item['published']), now, now))
                    self.db.execute('INSERT OR IGNORE INTO provenance VALUES(?,?)', (eid, s['id']))
                self.db.commit()
                outcomes.append({'source': s['id'], 'status': status, 'items': len(rows), 'error': error})
        return outcomes

    def coverage(self, sources):
        cutoff = time.time() - 7 * 86400
        success = {x[0] for x in self.db.execute("SELECT DISTINCT source FROM checks WHERE checked>=? AND status='checked'", (cutoff,))}
        rows = []
        for s in sources:
            last = self.db.execute('SELECT * FROM checks WHERE source=? ORDER BY id DESC LIMIT 1', (s['id'],)).fetchone()
            rows.append({**s, 'status': last['status'] if last else 'not_checked', 'last_checked': last['checked'] if last else None})
        families = {s['family'] for s in sources if s['id'] in success}
        return {'checked': len(success), 'target': 20, 'registered': len(sources),
                'blocked': sum(s['status'] == 'unavailable' for s in rows), 'source_families': len(families), 'rows': rows}

    def digest(self, sources):
        # Per-source sampling prevents a busy technical feed drowning out other communities.
        entries = []
        for s in sources:
            rows = self.db.execute('''SELECT e.* FROM evidence e JOIN provenance p ON e.id=p.evidence
              WHERE p.source=? ORDER BY e.first_seen DESC,e.id LIMIT 6''', (s['id'],))
            entries.append({'source': s['name'], 'family': s['family'], 'domain': s['domain'], 'records': [dict(r) for r in rows]})
        return {'generated_at': time.time(), 'untrusted_source_content': True, 'coverage': self.coverage(sources), 'sources': entries}
