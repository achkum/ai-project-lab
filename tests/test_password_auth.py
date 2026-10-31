import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from engine.password_auth import Auth

class PasswordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=1000
        self.root.joinpath('api-auth.json').write_text(json.dumps({'setup_hash':hashlib.sha256(b'one-time-setup').hexdigest(),'setup_expires':2000,'token_hash':hashlib.sha256(b'legacy').hexdigest(),'expires_at':999999}))
        self.auth=Auth(self.root,lambda:self.now)
    def tearDown(self):self.auth.close();self.tmp.cleanup()
    def test_setup_is_protected_and_cannot_be_reused(self):
        with self.assertRaises(PermissionError):self.auth.setup('test passphrase 123','wrong')
        self.assertFalse(self.auth.configured())
        result=self.auth.setup('test passphrase 123','one-time-setup')
        self.assertTrue(self.auth.valid(result['token']))
        with self.assertRaises(ValueError):self.auth.setup('another passphrase','one-time-setup')
        self.assertFalse(self.auth.valid('legacy'))
    def test_hash_only_storage_and_wrong_password(self):
        result=self.auth.setup('test passphrase 123','one-time-setup')
        raw=self.root.joinpath('auth.sqlite').read_bytes()
        self.assertNotIn(b'test passphrase 123',raw);self.assertNotIn(result['token'].encode(),raw)
        with self.assertRaises(PermissionError):self.auth.login('not the password')
        self.assertTrue(self.auth.valid(self.auth.login('test passphrase 123')['token']))
    def test_session_expiry_and_logout(self):
        short=self.auth.setup('test passphrase 123','one-time-setup')
        long=self.auth.login('test passphrase 123',True)
        self.now+=12*3600+1
        self.assertFalse(self.auth.valid(short['token']));self.assertTrue(self.auth.valid(long['token']))
        self.auth.logout(long['token']);self.assertFalse(self.auth.valid(long['token']))
    def test_expired_setup_cannot_claim_account(self):
        self.now=2001
        with self.assertRaises(PermissionError):self.auth.setup('test passphrase 123','one-time-setup')
    def test_persistent_rate_limit(self):
        for i in range(10):self.auth.throttle()
        other=Auth(self.root,lambda:self.now)
        try:
            with self.assertRaisesRegex(ValueError,'Too many'):other.throttle()
        finally:other.close()
        self.now+=61;self.auth.throttle()

if __name__=='__main__':unittest.main()
