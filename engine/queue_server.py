"""Authenticated owner-only HTTPS queue API, behind Caddy. No model credentials."""
import hashlib
import hmac
import json
import time
from collections import defaultdict,deque
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .jobs import Jobs
from .password_auth import Auth

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://achkum.github.io'
ORIGINS={ORIGIN,'https://198.44.116.159.sslip.io'}
LIMITS=defaultdict(deque)

class Handler(BaseHTTPRequestHandler):
    server_version='LabQueue'
    def log_message(self,*args): pass  # Never log bearer tokens or private job payloads.
    def send(self,status,value):
        raw=json.dumps(value).encode()
        self.send_response(status)
        if self.headers.get('Origin') in ORIGINS:
            self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
            self.send_header('Vary','Origin')
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(raw)
    def do_OPTIONS(self):
        if self.headers.get('Origin') not in ORIGINS: return self.send(403,{'error':'Origin not allowed'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
        self.send_header('Vary','Origin');self.end_headers()
    def token(self):
        value=self.headers.get('Authorization','')
        return value[7:] if value.startswith('Bearer ') and len(value)<200 else ''
    def authorized(self):
        if self.headers.get('Origin') not in (None,*ORIGINS):return False
        auth=Auth(ROOT/'runtime')
        try:return auth.valid(self.token())
        finally:auth.close()
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if not 0<n<=8192:raise ValueError('Request too large or empty')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
        self.connection.settimeout(10)
        value=json.loads(self.rfile.read(n))
        if not isinstance(value,dict):raise ValueError('JSON object required')
        return value
    def do_GET(self):
        self.path=self.path.split('?',1)[0]
        if self.path in ('/password','/password.js'):
            path=ROOT/'deploy'/('password.html' if self.path=='/password' else 'password.js')
            raw=path.read_bytes();self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/password' else 'text/javascript; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(raw);return
        if self.path=='/auth/status':
            auth=Auth(ROOT/'runtime')
            try:self.send(200,{'configured':auth.configured()})
            finally:auth.close()
            return
        if self.path=='/health': return self.send(200,{'service':'lab-queue','ok':True})
        if not self.authorized():return self.send(401,{'error':'Sign in to start work'})
        if self.path!='/jobs':return self.send(404,{'error':'Not found'})
        q=self.server.queue()
        try:self.send(200,q.snapshot())
        finally:q.close()
    def do_POST(self):
        if self.headers.get('Origin') not in (None,*ORIGINS):return self.send(403,{'error':'Origin not allowed'})
        if self.path in ('/auth/setup','/auth/login','/auth/logout'):
            auth=Auth(ROOT/'runtime')
            try:
                body=self.body()
                if self.path=='/auth/setup':result=auth.setup(body.get('password'),self.token(),body.get('remember') is True)
                elif self.path=='/auth/login':result=auth.login(body.get('password'),body.get('remember') is True)
                else:auth.logout(self.token());result={'ok':True}
                self.send(200,result)
            except PermissionError as e:self.send(401,{'error':str(e)})
            except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)})
            finally:auth.close()
            return
        if not self.authorized():return self.send(401,{'error':'Not connected'})
        # Only one owner token is issued. Bound requests globally, not by spoofable headers.
        now=time.time();bucket=LIMITS['owner']
        while bucket and bucket[0]<now-60:bucket.popleft()
        if len(bucket)>=30:return self.send(429,{'error':'Too many changes; wait one minute'})
        bucket.append(now)
        q=None
        try:
            body=self.body()
            q=self.server.queue()
            if self.path=='/jobs':
                ids=q.enqueue(body.get('items'),body.get('request_id'))
                self.send(200,{'ids':ids,**q.snapshot()})
            elif self.path=='/control':
                q.control(body.get('id'),body.get('action'));self.send(200,q.snapshot())
            else:self.send(404,{'error':'Not found'})
        except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)})
        finally:
            if q:q.close()

def main():
    server=ThreadingHTTPServer(('127.0.0.1',8787),Handler)
    server.queue=lambda:Jobs(ROOT/'runtime/jobs.sqlite',json.loads((ROOT/'config/public-opportunities.json').read_text()))
    server.auth_ok=lambda config,token:config['expires_at']>time.time() and hmac.compare_digest(config['token_hash'],hashlib.sha256(token.encode()).hexdigest())
    server.serve_forever()

if __name__=='__main__':main()
