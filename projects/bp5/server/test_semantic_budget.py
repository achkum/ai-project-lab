"""Persistent admission tests; all checker decisions are synthetic fixtures."""
import os
import sqlite3
import threading
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_production as f


class SemanticBudgetTests(unittest.TestCase):
    def setUp(self):
        f.ProductionTest.setUp(self)
        # Most tests isolate credit accounting from the separately tested clock.
        self.cooldown = patch.object(f.production, 'SEMANTIC_COOLDOWN_PERCENT', 0)
        self.cooldown.start(); self.addCleanup(self.cooldown.stop)
    tearDown = f.ProductionTest.tearDown
    register = f.ProductionTest.register
    hdr = f.ProductionTest.hdr

    def start(self, request_id):
        r = self.c.post('/api/missions', headers=self.headers, json={'mission_id': 'lib_test_m1', 'request_id': request_id})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()['session']['id']

    def account(self, name):
        a = self.register(name); self.uid = a['user']['id']; self.headers = self.hdr(a['csrf'])
        return a

    def turn(self, sid, request_id, text='Jag vill ha kaffe.'):
        return self.c.post(f'/api/missions/{sid}/turn', headers=self.headers, json={'request_id': request_id, 'text': text})

    def budget(self, uid=None):
        with f.st.connect() as db:
            row = db.execute('SELECT available,updated,blocked_until FROM semantic_budgets WHERE user_id=?', (uid or self.uid,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def decision(intent=None):
        return {'intent_id': intent, 'confidence': .9, 'source': 'semantic', 'language': 'sv', 'language_supported': True, 'language_evidence': 'detector', 'checker_revision': 'fixture-only'}

    def test_failures_resets_and_many_missions_share_persistent_budget(self):
        self.account('budgetfailures'); sid = self.start('budget-start')
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 2), patch.object(f.production.time, 'time', return_value=time.time()), patch.object(f.production.language_checker, 'check', side_effect=f.production.language_checker.CheckerUnavailable('fixture')) as check:
            self.assertEqual(self.turn(sid, 'failed-retry').status_code, 503)
            self.assertEqual(self.budget()['available'], 1)
            self.assertEqual(self.c.post(f'/api/missions/{sid}/reset', headers=self.headers, json={'request_id': 'budget-reset'}).status_code, 200)
            other = self.start('other-budget-mission')
            self.assertEqual(self.turn(other, 'failed-retry').status_code, 503)
            # init/new connection models a service restart; persisted credit is unchanged.
            f.st.init(); self.assertEqual(self.budget()['available'], 0)
            self.assertEqual(self.turn(sid, 'failed-retry').status_code, 429)
            self.assertEqual(check.call_count, 2)
            self.assertEqual(len(self.c.get(f'/api/missions/{sid}').json()['session']['turns']), 1)

    def test_cached_retry_and_payload_conflict_cost_nothing_even_when_exhausted(self):
        self.account('budgetretry'); sid = self.start('retry-start')
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 1), patch.object(f.production.time, 'time', return_value=time.time()), patch.object(f.production.language_checker, 'check', return_value=self.decision('coffee')) as check:
            self.assertEqual(self.turn(sid, 'once').status_code, 200)
            self.assertEqual(self.budget()['available'], 0)
            self.assertEqual(self.turn(sid, 'once').status_code, 200)
            self.assertEqual(self.turn(sid, 'once', 'changed').status_code, 409)
            self.assertEqual(self.turn(sid, 'new').status_code, 429)
            self.assertEqual(self.budget()['available'], 0); self.assertEqual(check.call_count, 1)

    def test_busy_rejection_is_not_charged_and_other_account_has_own_budget(self):
        self.account('budgetbusy'); sid = self.start('busy-start'); owner = self.uid
        entered, release = threading.Event(), threading.Event(); responses = []
        def slow(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('test synchronization')
            return self.decision()
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 2), patch.object(f.production.time, 'time', return_value=time.time()), patch.object(f.production.language_checker, 'check', side_effect=slow):
            thread = threading.Thread(target=lambda: responses.append(self.turn(sid, 'busy-first').status_code)); thread.start()
            try:
                self.assertTrue(entered.wait(3)); self.assertEqual(self.turn(sid, 'busy-second').status_code, 429)
                self.assertEqual(self.budget()['available'], 1)
            finally: release.set(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertEqual(responses, [200])
        self.c.post('/api/auth/logout', headers=self.headers, json={})
        self.account('budgetseparate'); other = self.start('separate-start')
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 2), patch.object(f.production.language_checker, 'check', return_value=self.decision()):
            self.assertEqual(self.turn(other, 'separate-turn').status_code, 200)
        self.assertEqual(self.budget()['available'], 1); self.assertEqual(self.budget(owner)['available'], 1)

    def test_reset_or_logout_between_snapshot_and_admission_is_free(self):
        for action in ('reset', 'logout'):
            self.account('budgetstale' + action); sid = self.start('stale-' + action)
            real = f.production.LANGUAGE_CHECK_LOCK; outer = self
            class BoundaryLock:
                def acquire(self, blocking=False):
                    if action == 'reset':
                        response = outer.c.post(f'/api/missions/{sid}/reset', headers=outer.headers, json={'request_id': 'before-admission'})
                    else: response = outer.c.post('/api/auth/logout', headers=outer.headers, json={})
                    outer.assertEqual(response.status_code, 200)
                    return real.acquire(blocking=blocking)
                def release(self): real.release()
            with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'LANGUAGE_CHECK_LOCK', BoundaryLock()), patch.object(f.production.language_checker, 'check') as check:
                self.assertEqual(self.turn(sid, 'stale-turn').status_code, 409 if action == 'reset' else 401)
                self.assertIsNone(self.budget()); check.assert_not_called()

    def test_account_deletion_during_admitted_work_cascades_budget(self):
        self.account('budgetdelete'); sid = self.start('delete-start'); entered, release = threading.Event(), threading.Event(); responses = []
        def slow(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('test synchronization')
            return self.decision()
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production.language_checker, 'check', side_effect=slow):
            thread = threading.Thread(target=lambda: responses.append(self.turn(sid, 'delete-turn').status_code)); thread.start()
            try:
                self.assertTrue(entered.wait(3)); self.assertIsNotNone(self.budget())
                self.assertEqual(self.c.request('DELETE', '/api/account', headers=self.headers, json={'password': 'correct horse battery staple'}).status_code, 200)
                self.assertIsNone(self.budget())
            finally: release.set(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertEqual(responses, [401]); self.assertIsNone(self.budget())

    def test_refill_is_persistent_capped_and_backward_clock_grants_nothing(self):
        self.account('budgetclock'); sid = self.start('clock-start'); now = time.time()
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 3), patch.object(f.production, 'SEMANTIC_REFILL_UNITS_PER_MINUTE', 1), patch.object(f.production.language_checker, 'check', return_value=self.decision()):
            for index in range(3):
                with patch.object(f.production.time, 'time', return_value=now): self.assertEqual(self.turn(sid, 'clock-'+str(index)).status_code, 200)
            with patch.object(f.production.time, 'time', return_value=now-60): self.assertEqual(self.turn(sid, 'backward').status_code, 429)
            with patch.object(f.production.time, 'time', return_value=now+60): self.assertEqual(self.turn(sid, 'refilled').status_code, 200)
            self.assertEqual(self.budget()['available'], 0)
            with patch.object(f.production.time, 'time', return_value=now+3600): self.assertEqual(self.turn(sid, 'capped').status_code, 200)
            self.assertEqual(self.budget()['available'], 2)

    def test_occupancy_cooldown_persists_on_success_and_failure_without_blocking_response(self):
        for failed in (False, True):
            self.account('budgetcooldown' + str(failed).lower()); sid = self.start('cooldown-' + str(failed)); now = time.time()
            def work(*args):
                time.sleep(.03)
                if failed: raise f.production.language_checker.CheckerUnavailable('fixture')
                return self.decision()
            with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'SEMANTIC_COOLDOWN_PERCENT', 100), patch.object(f.production.time, 'time', return_value=now), patch.object(f.production.language_checker, 'check', side_effect=work) as check:
                self.assertEqual(self.turn(sid, 'first').status_code, 503 if failed else 200)
                before = self.budget(); self.assertGreaterEqual(before['blocked_until']-now, .02)
                self.assertLess(before['blocked_until']-now, 2)
                f.st.init()
                blocked = self.turn(sid, 'blocked')
                self.assertEqual(blocked.status_code, 429); self.assertEqual(blocked.headers['retry-after'], '1')
                self.assertIn('Keep your draft', blocked.json()['error'])
                self.assertEqual(check.call_count, 1); self.assertEqual(self.budget(), before)
                with patch.object(f.production.time, 'time', return_value=now+3):
                    self.assertEqual(self.turn(sid, 'later').status_code, 503 if failed else 200)
                self.assertEqual(check.call_count, 2)

    def test_retry_committed_between_snapshot_and_admission_is_not_double_charged(self):
        self.account('budgetoverlap'); sid = self.start('overlap-start'); real = f.production.LANGUAGE_CHECK_LOCK; outer = self
        class BoundaryLock:
            entered = False
            def acquire(self, blocking=False):
                if not self.entered:
                    self.entered = True
                    outer.assertEqual(outer.turn(sid, 'same-request').status_code, 200)
                return real.acquire(blocking=blocking)
            def release(self): real.release()
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.production, 'LANGUAGE_CHECK_LOCK', BoundaryLock()), patch.object(f.production, 'SEMANTIC_BURST_UNITS', 2), patch.object(f.production.time, 'time', return_value=time.time()), patch.object(f.production.language_checker, 'check', return_value=self.decision('coffee')) as check:
            response = self.turn(sid, 'same-request')
            self.assertEqual(response.status_code, 200); self.assertEqual(len(response.json()['session']['turns']), 3)
            self.assertEqual(self.budget()['available'], 1); self.assertEqual(check.call_count, 1)

    def test_failed_budget_commit_rolls_back_and_never_calls_inference(self):
        self.account('budgetcommit'); sid = self.start('commit-start'); connect = f.st.connect
        class FailingCommit:
            def __init__(self): self.db = connect(); self.debited = False
            def __enter__(self): return self
            def __exit__(self, *args): return self.db.__exit__(*args)
            @property
            def in_transaction(self): return self.db.in_transaction
            def execute(self, sql, args=()):
                if sql.startswith('INSERT INTO semantic_budgets'): self.debited = True
                if sql == 'COMMIT' and self.debited: raise sqlite3.OperationalError('synthetic commit failure')
                return self.db.execute(sql, args)
        with patch.dict(os.environ, {'BP5_SEMANTIC_REQUIRED': '1'}), patch.object(f.st, 'connect', FailingCommit), patch.object(f.production.language_checker, 'check') as check:
            with self.assertRaises(sqlite3.OperationalError): self.turn(sid, 'failed-commit')
            check.assert_not_called()
        self.assertIsNone(self.budget())
        self.assertTrue(f.production.LANGUAGE_CHECK_LOCK.acquire(blocking=False)); f.production.LANGUAGE_CHECK_LOCK.release()

    def test_cost_weights_long_replies_and_candidates_without_tiny_practice_cap(self):
        short = f.production.semantic_cost('En kaffe tack.', {'intents': [{}, {}]})
        long = f.production.semantic_cost('Jag vill gärna planera nästa vecka. ' * 35, {'intents': [{}, {}]})
        many = f.production.semantic_cost('En kaffe tack.', {'intents': [{}] * 6})
        self.assertEqual(short, 1); self.assertGreater(long, short); self.assertGreater(many, short)
        self.assertGreaterEqual(f.production.SEMANTIC_BURST_UNITS//short, 40)
        self.assertGreaterEqual(f.production.SEMANTIC_BURST_UNITS//long, 4)
        self.assertLessEqual(f.production.semantic_cost('😀'*2000, {'intents': [{}]*6}), 48)
        for value in ('0', '241', 'not-an-int'):
            with patch.dict(os.environ, {'BP5_TEST_BUDGET_SETTING': value}), self.assertRaises(RuntimeError):
                f.production.semantic_budget_setting('BP5_TEST_BUDGET_SETTING', 48, 48, 240)

    def test_existing_budget_schema_upgrade_preserves_credit_and_cascade(self):
        with tempfile.TemporaryDirectory(prefix='bp5-budget-migration-') as tmp, patch.object(f.st, 'DB', Path(tmp)/'fixture.sqlite3'):
            f.st.init()
            with f.st.connect() as db:
                db.execute("INSERT INTO users VALUES('fixture-owner','fixture-user','unused','{}',0)")
                db.execute('DROP TABLE semantic_budgets')
                db.execute('CREATE TABLE semantic_budgets(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, available REAL NOT NULL, updated REAL NOT NULL)')
                db.execute("INSERT INTO semantic_budgets VALUES('fixture-owner',9,123)")
            f.st.init(); f.st.init()
            with f.st.connect() as db:
                row = db.execute('SELECT * FROM semantic_budgets').fetchone()
                self.assertEqual((row['available'], row['updated'], row['blocked_until']), (9, 123, 0))
                db.execute("DELETE FROM users WHERE id='fixture-owner'")
                self.assertEqual(db.execute('SELECT count(*) FROM semantic_budgets').fetchone()[0], 0)


if __name__ == '__main__': unittest.main()
