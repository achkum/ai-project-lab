import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from engine.discovery import Discovery
from engine.remote import import_collection

class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.d=Discovery(Path(self.tmp.name)/'evidence.sqlite')
        self.now=time.time()
        url='https://example.org/lead'
        eid=hashlib.sha256(url.encode()).hexdigest()[:24]
        self.packet={'version':1,'generated_at':self.now,
          'checks':[{'source':'s1','checked':self.now,'status':'checked','error':'','count':1}],
          'evidence':[{'id':eid,'url':url,'title':'Public lead','summary':'','published':'null','first_seen':self.now,'last_seen':self.now}],
          'provenance':[{'source':'s1','evidence':eid}]}
    def tearDown(self): self.d.close();self.tmp.cleanup()
    def test_repeat_import_deduplicates(self):
        for _ in range(2): import_collection(self.d,self.packet,[{'id':'s1'}])
        for table in ('checks','evidence','provenance'):
            self.assertEqual(self.d.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)
    def test_stale_rejected_without_writes(self):
        self.packet['generated_at']-=49*3600
        with self.assertRaises(ValueError): import_collection(self.d,self.packet,[{'id':'s1'}])
        self.assertEqual(self.d.db.execute('SELECT COUNT(*) FROM checks').fetchone()[0],0)
    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError): import_collection(self.d,self.packet,[{'id':'different'}])

if __name__=='__main__': unittest.main()
