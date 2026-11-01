"""Disposable, sanitized end-to-end check against a running BP5 service.

Run inside the service container with its LAB_DATA_DIR and BP5_* environment.
Creates only two invitation-backed QA accounts and deletes them in finally.
"""
import http.cookies
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_store as store

BASE = os.getenv('BP5_SMOKE_BASE', 'http://127.0.0.1:8788').rstrip('/')
ORIGIN = os.getenv('BP5_PUBLIC_ORIGIN', BASE).rstrip('/')
if BASE not in ('http://127.0.0.1:8788', 'http://localhost:8788'):
    raise SystemExit('Smoke target must be the local service on port 8788')

class Failure(Exception):
    pass

class Client:
    def __init__(self):
        self.cookies = {}
        self.csrf = ''
        self.username = 'qa_' + secrets.token_hex(10)
        self.password = secrets.token_urlsafe(24)
        self.created = False
        self.ever_created = False
        self.attempted = False
        self.password_candidates = [self.password]
        self.invite = None

    def request(self, method, path, data=None, content_type=None, extra=None, timeout=60):
        headers = {'Origin': ORIGIN, 'Accept': 'application/json'}
        if self.cookies:
            headers['Cookie'] = '; '.join(k + '=' + v for k, v in self.cookies.items())
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        if data is not None:
            if content_type is None:
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                content_type = 'application/json'
            headers['Content-Type'] = content_type
        if extra:
            headers.update(extra)
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            for value in response.headers.get_all('Set-Cookie', []):
                parsed = http.cookies.SimpleCookie()
                parsed.load(value)
                for name, morsel in parsed.items():
                    if morsel.value:
                        self.cookies[name] = morsel.value
                    else:
                        self.cookies.pop(name, None)
            raw = response.read()
            ctype = response.headers.get('Content-Type', '')
            body = json.loads(raw) if ctype.startswith('application/json') and raw else raw
            return response.status, body, response.headers

    def register(self):
        self.invite = store.create_invite()
        self.attempted = True
        status, body, _ = self.request('POST', '/api/auth/register', {
            'username': self.username, 'password': self.password, 'invite': self.invite,
        })
        require(status == 200 and isinstance(body, dict), 'register')
        # Mark the account as owned immediately once the server accepted it, even
        # if the response is incomplete, so cleanup will still attempt deletion.
        self.created = True
        self.ever_created = True
        self.csrf = body.get('csrf', '') or self.cookies.get('bp5_csrf', '')
        codes = body.get('recovery_codes', [])
        require(bool(self.csrf) and bool(self.cookies.get('bp5_session')) and len(codes) == 8, 'registration response')
        return codes

    def cleanup(self):
        # Detect a committed registration even if the HTTP response was interrupted.
        if self.attempted and not self.created:
            with store.connect() as c:
                self.created = bool(c.execute('SELECT 1 FROM users WHERE username=?', (self.username,)).fetchone())
            self.ever_created = self.created
        self.csrf = self.csrf or self.cookies.get('bp5_csrf', '')
        deleted = not self.created
        if self.created:
            for password in reversed(self.password_candidates):
                try:
                    if self.cookies.get('bp5_session') and self.csrf:
                        status, _, _ = self.request('DELETE', '/api/account', {'password': password}, timeout=30)
                        if status == 200:
                            deleted = True
                            break
                    status, body, _ = self.request('POST', '/api/auth/login', {'username': self.username, 'password': password}, timeout=30)
                    if status == 200:
                        self.csrf = body.get('csrf', '')
                        status, _, _ = self.request('DELETE', '/api/account', {'password': password}, timeout=30)
                        if status == 200:
                            deleted = True
                            break
                except Exception:
                    continue
            self.created = not deleted
        if self.invite:
            # This only touches this script's own invitation, used or unused.
            with store.connect() as c:
                c.execute('DELETE FROM invitations WHERE token_hash=?', (store.digest(self.invite),))
        return deleted


def require(condition, label):
    if not condition:
        raise Failure(label)


def start(client, mission_id):
    status, body, _ = client.request('POST', '/api/missions', {
        'mission_id': mission_id, 'request_id': str(uuid.uuid4()),
        'framework_id': 'SKOLFS-2017-91-consolidated', 'course': '2B', 'study_path': '2',
    })
    require(status == 200 and isinstance(body, dict) and body.get('session'), 'mission start')
    return body['session']


def main():
    started = time.monotonic()
    checks = {}
    clients = [Client(), Client()]
    error = None
    cleanup = []
    try:
        a, b = clients
        status, body, _ = a.request('GET', '/health')
        require(status == 200 and body.get('ok') is True, 'health')
        status, body, _ = a.request('GET', '/ready')
        require(status == 200 and body.get('ok') is True, 'readiness')
        checks['readiness'] = 'pass'
        codes = a.register()
        b.register()
        checks['accounts_created'] = 2
        status, library, _ = a.request('GET', '/api/library')
        require(status == 200, 'library')
        situations = library.get('situations', [])
        missions = [m for situation in situations for m in situation.get('missions', [])]
        require(len(situations) == 18 and len(missions) == 54, 'library count')
        basic_ids = [m['id'] for s in situations if s.get('level') == 'basic' for m in s.get('missions', [])]
        require(len(basic_ids) >= 2 and basic_ids[0] != basic_ids[1], 'basic task diversity')
        first_session = None
        turns = 0
        for mission in missions:
            session = start(a, mission['id'])
            if first_session is None:
                first_session = session
            steps = {step['id']: step for step in mission['steps']}
            attempt = 0
            while session.get('status') != 'completed':
                attempt += 1
                require(attempt <= len(steps), 'mission loop')
                step = steps[session['current_step']]
                text = step['intents'][0]['examples_sv'][0]
                status, result, _ = a.request('POST', '/api/missions/' + session['id'] + '/turn', {
                    'request_id': str(uuid.uuid4()), 'text': text, 'input_mode': 'text',
                    'transcript_edited': False, 'help_used': [],
                })
                require(status == 200 and result.get('matched') is True, 'mission turn')
                session = result['session']
                turns += 1
            require(set(mission['completion_objectives']).issubset(session.get('completed_objectives', [])), 'mission objectives')
        checks['missions_completed'] = len(missions)
        checks['authored_turns'] = turns
        next_session = start(a, basic_ids[1])
        require(next_session['mission_id'] != basic_ids[0] and next_session['status'] == 'in_progress', 'next different basic')
        status, reloaded, _ = a.request('GET', '/api/missions/' + next_session['id'])
        require(status == 200 and reloaded['session']['id'] == next_session['id'], 'reload session')
        checks['next_and_reload'] = 'pass'
        status, result, _ = a.request('POST', '/api/missions/' + next_session['id'] + '/evidence', {
            'request_id': str(uuid.uuid4()), 'activity': 'writing', 'response': 'Tack så mycket.', 'help_used': [],
        })
        require(status == 200 and result['session'].get('evidence'), 'save evidence')
        snap = result['session']['snapshot']
        criteria = {criterion['id']: criterion for criterion in snap.get('criteria', [])}
        writing_links = [link for link in snap.get('criterion_links', [])
                         if link.get('activity') == 'writing' and link.get('criterion_id') in criteria
                         and criteria[link['criterion_id']].get('source', {}).get('url')]
        require(snap['selection']['course'] == 'B' and snap['selection']['study_path'] == '2'
                and bool(writing_links) and result['session']['evidence'][-1]['activity'] == 'writing', 'connected evidence snapshot')
        checks['evidence_snapshot'] = 'pass'
        b_session = start(b, basic_ids[0])
        status, _, _ = b.request('GET', '/api/missions/' + next_session['id'])
        require(status == 404, 'cross-account read')
        status, _, _ = b.request('POST', '/api/missions/' + next_session['id'] + '/turn', {
            'request_id': str(uuid.uuid4()), 'text': 'Hej', 'input_mode': 'text', 'help_used': [],
        })
        require(status == 404, 'cross-account mutation')
        status, exported, headers = b.request('GET', '/api/export')
        require(status == 200 and 'attachment' in headers.get('Content-Disposition', '') and
                [s['id'] for s in exported['sessions']] == [b_session['id']] and
                next_session['id'] not in json.dumps(exported), 'cross-account export')
        status, _, _ = a.request('GET', '/api/missions/' + b_session['id'])
        require(status == 404, 'reverse cross-account read')
        status, exported_a, _ = a.request('GET', '/api/export')
        require(status == 200 and b_session['id'] not in json.dumps(exported_a), 'reverse cross-account export')
        checks['account_isolation'] = 'pass'
        # Real local TTS, ffmpeg conversion and local ASR. Synthetic speech only.
        job = str(uuid.uuid4())
        t0 = time.monotonic()
        status, wav, _ = a.request('POST', '/api/speech', {'text': 'Hej, jag vill ha en kopp kaffe, tack.', 'slow': False},
                                   extra={'X-Audio-Job': job}, timeout=120)
        require(status == 200 and isinstance(wav, bytes) and wav.startswith(b'RIFF'), 'speech synthesis')
        tts_seconds = time.monotonic() - t0
        with tempfile.TemporaryDirectory(dir=store.DATA, prefix='bp5-smoke-') as d:
            src, dst = Path(d) / 'sample.wav', Path(d) / 'sample.m4a'
            src.write_bytes(wav)
            r = subprocess.run([os.getenv('BP5_FFMPEG', 'ffmpeg'), '-v', 'error', '-y', '-i', str(src), str(dst)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            require(r.returncode == 0 and dst.is_file(), 'm4a conversion')
            t0 = time.monotonic()
            status, transcribed, _ = a.request('POST', '/api/transcribe', dst.read_bytes(), 'audio/mp4',
                                                {'X-Audio-Job': str(uuid.uuid4())}, timeout=300)
            asr_seconds = time.monotonic() - t0
        require(status == 200 and bool(transcribed.get('text', '').strip()), 'speech recognition')
        checks['synthetic_audio'] = {'result': 'pass', 'tts_seconds': round(tts_seconds, 2), 'asr_seconds': round(asr_seconds, 2),
                                     'accuracy': 'not assessed; synthetic audio only'}
        # Probe busy/cancellation only while a real long speech job is running.
        long_job = str(uuid.uuid4())
        speech_result = []
        def speak_long():
            try:
                speech_result.append(a.request('POST', '/api/speech', {'text': ('Jag vill prata svenska. ' * 35).strip(), 'slow': True},
                                               extra={'X-Audio-Job': long_job}, timeout=120)[0])
            except Exception:
                speech_result.append(None)
        worker = threading.Thread(target=speak_long, daemon=True)
        worker.start()
        time.sleep(0.15)
        status, _, _ = b.request('POST', '/api/speech', {'text': 'Hej.', 'slow': False},
                                  extra={'X-Audio-Job': str(uuid.uuid4())}, timeout=60)
        require(status in (200, 429), 'audio busy probe')
        busy_observed = status == 429
        cancel_status, _, _ = a.request('DELETE', '/api/audio/jobs/' + long_job, timeout=30)
        require(cancel_status in (200, 404), 'audio cancellation probe')
        worker.join(30)
        checks['audio_busy'] = 'pass' if busy_observed else 'not observed; first job finished too soon'
        require(not worker.is_alive(), 'audio cancellation wait')
        if cancel_status == 200:
            require(bool(speech_result) and speech_result[0] != 200, 'audio cancellation result')
        checks['audio_cancellation'] = 'pass' if cancel_status == 200 else 'not observed; first job finished too soon'
        # Recovery must invalidate the session that existed before the reset.
        old_password = a.password
        new_password = secrets.token_urlsafe(24)
        a.password_candidates.append(new_password)
        status, _, _ = a.request('POST', '/api/auth/recover', {
            'username': a.username, 'recovery_code': codes[0], 'new_password': new_password,
        })
        require(status == 200, 'recovery')
        a.password = new_password
        status, info, _ = a.request('GET', '/api/auth/session')
        require(status == 200 and info.get('authenticated') is False, 'recovery session invalidation')
        status, _, _ = a.request('POST', '/api/auth/login', {'username': a.username, 'password': old_password})
        require(status == 401, 'invalid login')
        status, signed_in, _ = a.request('POST', '/api/auth/login', {'username': a.username, 'password': a.password})
        require(status == 200 and signed_in.get('csrf'), 'recovery new login')
        a.csrf = signed_in['csrf']
        checks['recovery_revocation'] = 'pass'
    except Exception as exc:
        error = str(exc) if isinstance(exc, Failure) else type(exc).__name__
    finally:
        for client in clients:
            try:
                cleanup.append(client.cleanup())
            except Exception:
                cleanup.append(False)
        checks['qa_accounts_deleted'] = sum(bool(ok) and client.ever_created for ok, client in zip(cleanup, clients))
    ok = error is None and all(cleanup)
    result = {'ok': ok, 'checks': checks, 'elapsed_seconds': round(time.monotonic() - started, 2),
              'scope': 'container loopback and synthetic audio; no physical device tested'}
    if error:
        result['failed_check'] = error
    if not all(cleanup):
        result['cleanup'] = 'One or more disposable accounts could not be deleted; operator cleanup required.'
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
