"""Authenticated owner-only HTTPS queue API, behind Caddy. No model credentials."""
import hashlib
import hmac
import json
import time
from collections import defaultdict,deque
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .jobs import Jobs

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://achkum.github.io'
LIMITS=defaultdict(deque)

class Handler(BaseHTTPRequestHandler):
    server_version='LabQueue'
    def log_message(self,*args): pass  # Never log bearer tokens or private job payloads.
    def send(self,status,value):
        raw=json.dumps(value).encode()
        self.send_response(status)
        if self.headers.get('Origin')==ORIGIN:
            self.send_header('Access-Control-Allow-Origin',ORIGIN)
            self.send_header('Vary','Origin')
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(raw)
    def do_OPTIONS(self):
        if self.headers.get('Origin')!=ORIGIN: return self.send(403,{'error':'Origin not allowed'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin',ORIGIN)
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
        self.send_header('Vary','Origin');self.end_headers()
    def authorized(self):
        if self.headers.get('Origin') not in (None,ORIGIN): return False
        token=self.headers.get('Authorization','')
        if not token.startswith('Bearer ') or len(token)>200: return False
        config=json.loads((ROOT/'runtime/api-auth.json').read_text())
        return self.server.auth_ok(config,token[7:])
    def do_GET(self):
        if self.path=='/health': return self.send(200,{'service':'lab-queue','ok':True})
        if not self.authorized():return self.send(401,{'error':'Connect this browser with your private dashboard key'})
        if self.path!='/jobs':return self.send(404,{'error':'Not found'})
        q=self.server.queue()
        try:self.send(200,q.snapshot())
        finally:q.close()
    def do_POST(self):
        if not self.authorized():return self.send(401,{'error':'Not connected'})
        # Only one owner token is issued. Bound requests globally, not by spoofable headers.
        now=time.time();bucket=LIMITS['owner']
        while bucket and bucket[0]<now-60:bucket.popleft()
        if len(bucket)>=30:return self.send(429,{'error':'Too many changes; wait one minute'})
        bucket.append(now)
        q=None
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=8192:raise ValueError('Request too large or empty')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
            self.connection.settimeout(10)
            body=json.loads(self.rfile.read(n))
            if not isinstance(body,dict):raise ValueError('JSON object required')
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
