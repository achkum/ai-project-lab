import copy
import json
import tempfile
import unittest
from pathlib import Path
from engine.workflow import Workflow, COMMON, EXTRA, validate_shortlist
from engine.discovery import parse
from engine.lab import export
from engine.discovery import Discovery
from unittest.mock import patch
from engine.github_control import sync, body_for


def document(lane='project', sid='batch1'):
    c = {k: 'A bounded, documented proposal' for k in COMMON + EXTRA[lane]}
    c.update(id='C1', eligible=True, evidence=[{'url':'https://example.org/evidence','finding':'Fixture only'}])
    return {'id':sid,'lane':lane,'version':1,'recommended':'C1','recommendation_reason':'Fixture', 'candidates':[c]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.now=1000
        self.path=Path(self.tmp.name)/'workflow.sqlite'
        self.w=Workflow(self.path,'owner','owner/private',clock=lambda:self.now)
        self.url='https://github.com/owner/private/issues/1'
    def tearDown(self): self.w.close(); self.tmp.cleanup()
    def published(self):
        self.w.submit(document()); self.w.publish('batch1',self.url)
    def test_no_work_before_visible_deadline(self):
        self.w.submit(document())
        self.now+=90000
        self.assertEqual(self.w.tick({self.url}),[])
        self.assertIsNone(self.w.claim('project'))
        self.w.publish('batch1',self.url)
        self.assertEqual(self.w.tick({self.url}),[])
        self.now+=86400
        self.assertEqual(self.w.tick(set()),[]) # inaccessible remote control fails closed
        self.assertEqual(self.w.tick({self.url}),['batch1'])
        self.assertEqual(self.w.tick({self.url}),[])
        self.assertEqual(self.w.claim('project')['origin'],'authorized_recommended_default')
    def test_owner_response_blocks_default(self):
        for action in ('hold','refine','more','reject','save'):
            with self.subTest(action=action):
                sid=action
                self.w.submit(document('thesis',sid)); self.w.publish(sid,self.url)
                self.w.command(sid,1,action,None,'owner',sid)
                self.now+=86401
                self.assertEqual(self.w.tick({self.url}),[])
                if action not in ('reject','save'):
                    self.w.command(sid,1,'reject',None,'owner',sid+'close')
    def test_owner_choice_wins_and_is_idempotent(self):
        self.published(); self.now+=86400
        expected=self.w.command('batch1',1,'select','C1','owner','cmd1')
        self.assertEqual(self.w.command('batch1',1,'select','C1','owner','cmd1'),expected)
        self.assertEqual(self.w.tick({self.url}),[])
        with self.assertRaises(ValueError): self.w.command('batch1',1,'hold',None,'owner','cmd1')
        self.assertEqual(self.w.claim('project')['origin'],'owner_choice')
    def test_immutable_scope_and_one_active_per_lane(self):
        self.published()
        changed=document(); changed['candidates'][0]['scope']='Different'
        with self.assertRaises(ValueError): self.w.submit(changed)
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError): self.w.submit(document(sid='other'))
        self.w.submit(document('thesis','research'))
        self.assertIsNone(self.w.claim('thesis'))
    def test_auth_version_and_private_destination(self):
        self.published()
        with self.assertRaises(PermissionError): self.w.command('batch1',1,'select','C1','stranger','cmd')
        with self.assertRaises(ValueError): self.w.command('batch1',2,'select','C1','owner','cmd')
        with self.assertRaises(ValueError): self.w.publish('batch1','https://github.com/owner/public/issues/1')
    def test_lease_fencing_recovery_and_owner_hold(self):
        self.published(); self.w.command('batch1',1,'select','C1','owner','cmd')
        first=self.w.claim('project',10)
        other=Workflow(self.path,'owner','owner/private',clock=lambda:self.now)
        try:
            self.assertIsNone(other.claim('project'))
            self.now+=11
            second=other.claim('project')
            with self.assertRaises(RuntimeError): self.w.check('batch1',first['token'])
            self.w.command('batch1',1,'hold',None,'owner','hold')
            with self.assertRaises(RuntimeError): other.heartbeat('batch1',second['token'])
        finally: other.close()
    def test_completion_requires_evidence_and_valid_lease(self):
        self.published(); self.w.command('batch1',1,'select','C1','owner','cmd')
        job=self.w.claim('project')
        with self.assertRaises(ValueError): self.w.finish('batch1',job['token'],{})
        self.w.finish('batch1',job['token'],{'artifact_url':'https://example.org/demo','validation':'Actual journey check','limitations':'Fixture'})
        self.assertEqual(self.w.get('batch1')['state'],'completed')
        self.w.submit(document(sid='next'))
    def test_public_export_never_leaks_candidate_content(self):
        d=document(); d['candidates'][0]['intro']='PRIVATE_CANARY'
        self.w.submit(d); self.w.publish('batch1',self.url)
        discovery=Discovery(Path(self.tmp.name)/'evidence.sqlite')
        try:
            snap=export({'public_root':self.tmp.name},self.w,discovery,[])
            self.assertNotIn('PRIVATE_CANARY',json.dumps(snap))
            self.assertEqual(snap['decisions'][0]['url'],self.url)
        finally: discovery.close()
    def test_github_crlf_transport_and_foreign_comment(self):
        self.published()
        def fake(*args, **kwargs):
            if args[0]=='repo': return json.dumps({'visibility':'PRIVATE'})
            if '--slurp' in args:
                return json.dumps([[{'id':1,'updated_at':'now','body':'/lab reject batch1 v1','user':{'login':'stranger'}}]])
            return json.dumps({'id':10,'updated_at':'now','state':'open','body':body_for(document()).replace('\n','\r\n')})
        with patch('engine.github_control.gh',side_effect=fake):
            verified, commands=sync(self.w)
        self.assertEqual(verified,{self.url})
        self.assertEqual(commands,[])
        self.assertEqual(self.w.get('batch1')['state'],'awaiting_owner_selection')
    def test_unstructured_owner_comment_holds_idempotently(self):
        self.published()
        def fake(*args, **kwargs):
            if args[0]=='repo': return json.dumps({'visibility':'PRIVATE'})
            if '--slurp' in args:
                return json.dumps([[{'id':1,'updated_at':'now','body':'Please rethink these options','user':{'login':'owner'}}]])
            return json.dumps({'id':10,'updated_at':'now','state':'open','body':body_for(document())})
        with patch('engine.github_control.gh',side_effect=fake):
            sync(self.w);sync(self.w)
        self.assertEqual(self.w.get('batch1')['state'],'held')
        self.now+=90000
        self.assertEqual(self.w.tick({self.url}),[])


class CollectorTests(unittest.TestCase):
    def test_feed_metadata_and_link(self):
        raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Problem &amp; evidence</title><link href="https://example.org/1"/><content>Do not retain full article</content></entry></feed>'
        result=parse({'kind':'feed'},raw)
        self.assertEqual(result[0]['url'],'https://example.org/1')
        self.assertEqual(result[0]['summary'],'')
    def test_xml_entities_and_api_backoff_fail(self):
        with self.assertRaises(ValueError): parse({'kind':'feed'},b'<!DOCTYPE foo><rss/>')
        with self.assertRaises(ValueError): parse({'kind':'stack'},b'{"items":[],"backoff":30}')
    def test_non_web_links_rejected(self):
        self.assertEqual(parse({'kind':'feed'},b'<rss><channel><item><title>X</title><link>file:///secret</link></item></channel></rss>'),[])


if __name__=='__main__': unittest.main()
