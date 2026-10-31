"""Single-owner password authentication; password and bearer tokens are never stored raw."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path


class Auth:
    def __init__(self,root,clock=time.time):
        self.root=Path(root);self.clock=clock
        self.db=sqlite3.connect(self.root/'auth.sqlite',isolation_level=None,timeout=15)
        self.db.executescript('CREATE TABLE IF NOT EXISTS password(id INTEGER PRIMARY KEY,salt TEXT,digest TEXT); CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,expires REAL); CREATE TABLE IF NOT EXISTS attempts(at REAL);')
    def close(self):self.db.close()
    def configured(self):return bool(self.db.execute('SELECT 1 FROM password').fetchone())
    def bootstrap(self,token):
        c=json.loads((self.root/'api-auth.json').read_text())
        return bool(token and c.get('setup_expires',0)>self.clock() and hmac.compare_digest(c.get('setup_hash',''),hashlib.sha256(token.encode()).hexdigest()))
    def valid(self,token):
        if not token:return False
        digest=hashlib.sha256(token.encode()).hexdigest()
        if self.db.execute('SELECT 1 FROM sessions WHERE digest=? AND expires>?',(digest,self.clock())).fetchone():return True
        if self.configured():return False  # Password setup revokes every legacy dashboard key.
        c=json.loads((self.root/'api-auth.json').read_text())
        return c.get('expires_at',0)>self.clock() and hmac.compare_digest(c.get('token_hash',''),digest)
    def throttle(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('DELETE FROM attempts WHERE at<?',(self.clock()-60,))
            if self.db.execute('SELECT count(*) FROM attempts').fetchone()[0]>=10:raise ValueError('Too many sign-in attempts. Try again in one minute.')
            self.db.execute('INSERT INTO attempts VALUES(?)',(self.clock(),));self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def session(self,remember):
        token=secrets.token_urlsafe(32);expiry=self.clock()+(30*86400 if remember else 12*3600)
        self.db.execute('DELETE FROM sessions WHERE expires<=?',(self.clock(),))
        self.db.execute('INSERT INTO sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),expiry))
        return {'token':token,'expires_at':expiry}
    def setup(self,password,token,remember=False):
        self.throttle()
        if not isinstance(password,str) or not 12<=len(password)<=128:raise ValueError('Use a password between 12 and 128 characters.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.configured():raise ValueError('A password is already set. Sign in instead.')
            if not self.bootstrap(token):raise PermissionError('This setup link is invalid or expired. Ask for a fresh private setup link.')
            salt=secrets.token_bytes(32)
            digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()
            self.db.execute('INSERT INTO password VALUES(1,?,?)',(salt.hex(),digest))
            self.db.execute('DELETE FROM sessions')
            result=self.session(remember);self.db.execute('COMMIT');return result
        except BaseException:self.db.execute('ROLLBACK');raise
    def login(self,password,remember=False):
        self.throttle()
        if not isinstance(password,str) or len(password)>128:raise PermissionError('Incorrect password.')
        row=self.db.execute('SELECT salt,digest FROM password WHERE id=1').fetchone()
        if not row:raise PermissionError('Password setup is not complete.')
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row[0]),600000).hex()
        if not hmac.compare_digest(digest,row[1]):raise PermissionError('Incorrect password.')
        return self.session(remember)
    def logout(self,token):self.db.execute('DELETE FROM sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),))
