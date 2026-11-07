"""Isolated infrastructure checks; fake decisions are never language evidence."""
import os
import threading
import time
import unittest
from unittest.mock import patch

import test_production as fixture


class SemanticSecurity(unittest.TestCase):
    setUp = fixture.ProductionTest.setUp
    tearDown = fixture.ProductionTest.tearDown
    register = fixture.ProductionTest.register
    hdr = fixture.ProductionTest.hdr

    def test_owner_and_csrf_checked_before_expensive_inference(self):
        a = self.register('reviewowner'); h = self.hdr(a['csrf'])
        sid = self.c.post('/api/missions', headers=h, json={'mission_id': 'lib_test_m1', 'request_id': 'review-start'}).json()['session']['id']
        body = {'request_id': 'review-request', 'text': 'Jag vill ha kaffe.'}
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(fixture.production.language_checker, 'check') as inference:
            self.assertEqual(self.c.post(f'/api/missions/{sid}/turn', headers=fixture.ORIGIN, json=body).status_code, 403)
            self.c.post('/api/auth/logout', headers=h, json={})
            b = self.register('reviewother')
            self.assertEqual(self.c.post(f'/api/missions/{sid}/turn', headers=self.hdr(b['csrf']), json=body).status_code, 404)
            inference.assert_not_called()

    def test_account_delete_and_expiry_during_inference_cannot_commit(self):
        for action in ('expiry', 'delete'):
            with self.subTest(action=action):
                a = self.register('reviewrace' + action); h = self.hdr(a['csrf'])
                sid = self.c.post('/api/missions', headers=h, json={'mission_id': 'lib_test_m1', 'request_id': 'start-' + action}).json()['session']['id']
                entered, release = threading.Event(), threading.Event()
                responses = []
                def slow(*args):
                    entered.set()
                    if not release.wait(5): raise RuntimeError('test synchronization timeout')
                    return {'intent_id': 'coffee', 'confidence': .9, 'source': 'semantic', 'language': 'sv', 'language_supported': True, 'language_evidence': 'detector', 'checker_revision': 'fixture-only'}
                def send():
                    responses.append(self.c.post(f'/api/missions/{sid}/turn', headers=h, json={'request_id': action, 'text': 'Jag vill ha kaffe.'}).status_code)
                with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(fixture.production.language_checker, 'check', side_effect=slow):
                    thread = threading.Thread(target=send); thread.start()
                    try:
                        self.assertTrue(entered.wait(3))
                        # This write must complete while inference is paused.
                        if action == 'expiry':
                            with fixture.st.connect() as db:
                                db.execute('UPDATE auth_sessions SET expires=? WHERE user_id=?', (time.time()-1, a['user']['id']))
                        else:
                            response = self.c.request('DELETE', '/api/account', headers=h, json={'password': 'correct horse battery staple'})
                            self.assertEqual(response.status_code, 200, response.text)
                    finally:
                        release.set(); thread.join(5)
                    self.assertFalse(thread.is_alive()); self.assertEqual(responses, [401])
                with fixture.st.connect() as db:
                    row = db.execute('SELECT payload FROM missions WHERE id=?', (sid,)).fetchone()
                if action == 'delete': self.assertIsNone(row)
                else: self.assertEqual(len(fixture.json.loads(row['payload'])['turns']), 1)


if __name__ == '__main__': unittest.main()
