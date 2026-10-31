import copy
import json
import tempfile
import unittest
from pathlib import Path
from engine.queue import Queue
from engine.routing import required_tier, resolve_model, SetupRequired

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=1000
        self.q=Queue(Path(self.tmp.name)/"queue.sqlite",clock=lambda:self.now)
    def tearDown(self):
        self.q.close()
        self.tmp.cleanup()
    def test_idempotent_and_conflicting_requests(self):
        first=self.q.enqueue("same","thesis","fetch",{"x":1})
        self.assertEqual(first,self.q.enqueue("same","thesis","fetch",{"x":1}))
        with self.assertRaises(ValueError): self.q.enqueue("same","project","fetch")
    def test_single_claim_across_connections_and_restart(self):
        self.q.enqueue("one","thesis","fetch")
        other=Queue(Path(self.tmp.name)/"queue.sqlite",clock=lambda:self.now)
        try:
            self.assertIsNotNone(self.q.claim("a","thesis"))
            self.assertIsNone(other.claim("b","thesis"))
        finally: other.close()
    def test_expired_attempt_cannot_publish(self):
        jid=self.q.enqueue("one","project","build")
        first=self.q.claim("a","project",10)
        self.now+=11
        second=self.q.claim("b","project",10)
        with self.assertRaises(RuntimeError): self.q.finish(jid,first["token"],{})
        self.q.finish(jid,second["token"],{"ok":True})
        self.assertEqual(self.q.summary(),{"completed":1})
    def test_bounded_attempts(self):
        self.q.enqueue("one","thesis","fetch",max_attempts=1)
        self.q.claim("a","thesis",10)
        self.now+=11
        self.assertIsNone(self.q.claim("b","thesis"))
        self.assertEqual(self.q.summary(),{"failed":1})
    def test_expired_worker_cannot_extend_lease(self):
        jid=self.q.enqueue("one","thesis","fetch")
        first=self.q.claim("a","thesis",10)
        self.now+=10
        with self.assertRaises(RuntimeError): self.q.heartbeat(jid,first["token"])

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.policy=json.loads(Path("config/model-policy.example.json").read_text())
    def test_required_quality(self):
        self.assertEqual(required_tier("initial_analysis"),"analysis")
        self.assertEqual(required_tier("approved_spec_implementation"),"implementation")
        self.assertEqual(required_tier("bounded_formatting"),"economy")
        self.assertIsNone(required_tier("hash"))
        self.assertEqual(required_tier("routine_fixes",repair_attempts=2),"analysis")
        self.assertEqual(required_tier("schema_checked_extraction",ambiguous=True),"analysis")
    def test_subscription_only_requires_verified_auth_and_no_overage(self):
        with self.assertRaises(SetupRequired): resolve_model(self.policy,"initial_analysis")
        p=copy.deepcopy(self.policy)
        p["tiers"]["analysis"]["model_id"]="fixture-only"
        with self.assertRaises(SetupRequired): resolve_model(p,"initial_analysis")
        with self.assertRaises(SetupRequired):
            resolve_model(p,"initial_analysis",auth_method="api_key",overage_disabled=True)
        with self.assertRaises(SetupRequired):
            resolve_model(p,"initial_analysis",auth_method="chatgpt_subscription")
        self.assertEqual(resolve_model(p,"initial_analysis",auth_method="chatgpt_subscription",
                                       overage_disabled=True)["model_id"],"fixture-only")
        p["monthly_cap_sek"]=100
        with self.assertRaises(SetupRequired):
            resolve_model(p,"initial_analysis",auth_method="chatgpt_subscription",overage_disabled=True)
    def test_unknown_task_is_not_cheap_by_default(self):
        with self.assertRaises(ValueError): required_tier("unclassified")

if __name__ == "__main__": unittest.main()

