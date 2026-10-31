import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from engine.queue_server import Handler

class PasswordHTTPTests(unittest.TestCase):
    def test_setup_login_authenticated_access_and_revoked_logout(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'runtime').mkdir()
            (root/'runtime/api-auth.json').write_text(json.dumps({'setup_hash':hashlib.sha256(b'test-setup').hexdigest(),'setup_expires':9999999999,'token_hash':'unused','expires_at':0}))
            class Queue:
                def snapshot(self):return {'jobs':[]}
                def close(self):pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.queue=Queue
            with patch('engine.queue_server.ROOT',root):
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                def call(path,body=None,token='',origin='https://achkum.github.io'):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    headers={'Origin':origin,'Content-Type':'application/json','Authorization':'Bearer '+token}
                    conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
                    r=conn.getresponse();result=(r.status,json.loads(r.read()));conn.close();return result
                try:
                    self.assertEqual(call('/jobs')[0],401)
                    self.assertEqual(call('/auth/setup',{'password':'test password only'},'wrong')[0],401)
                    self.assertEqual(call('/auth/setup',{'password':'test password only'},'test-setup',origin='https://evil.example')[0],403)
                    status,result=call('/auth/setup',{'password':'test password only','remember':True},'test-setup')
                    self.assertEqual(status,200);token=result['token']
                    self.assertEqual(call('/jobs',token=token)[0],200)
                    self.assertEqual(call('/auth/logout',{},token)[0],200)
                    self.assertEqual(call('/jobs',token=token)[0],401)
                    self.assertEqual(call('/auth/login',{'password':'wrong'})[0],401)
                    self.assertEqual(call('/auth/login',{'password':'test password only'})[0],200)
                    self.assertEqual(call('/auth/setup',{'password':'test password only'},'test-setup')[0],400)
                finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
