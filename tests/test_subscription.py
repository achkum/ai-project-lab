import copy
import unittest
from engine.subscription import validate_allowance, run


class SubscriptionTests(unittest.TestCase):
    def test_implementation_requires_selected_packet_before_any_call(self):
        with self.assertRaisesRegex(RuntimeError,'selected worker packet'):
            run('implementation','build something','.','unused','missing-proof')
    def proof(self):
        return {'checked_at':1000,'usage':{'ordinaryUsageAllowed':True,'rateLimitsByLimitId':{'codex':{
            'primary':{'usedPercent':20},'credits':{'hasCredits':False,'unlimited':False,'balance':'0'}}}}}
    def test_valid_allowance_and_stale_proof(self):
        validate_allowance(self.proof(),now=1001)
        with self.assertRaises(RuntimeError): validate_allowance(self.proof(),now=1301)
        with self.assertRaises(RuntimeError): validate_allowance(self.proof(),now=999)
    def test_unknown_or_paid_credits_fail_closed(self):
        for credits in ({},{'hasCredits':True,'unlimited':False,'balance':'10'}, {'hasCredits':False,'unlimited':True,'balance':'0'}):
            p=self.proof();p['usage']['rateLimitsByLimitId']['codex']['credits']=credits
            with self.assertRaises(RuntimeError): validate_allowance(p,now=1001)
    def test_exhausted_or_unknown_limits_fail_closed(self):
        for percent in (90,100,None):
            p=self.proof();p['usage']['rateLimitsByLimitId']['codex']['primary']['usedPercent']=percent
            with self.assertRaises(RuntimeError): validate_allowance(p,now=1001)


if __name__=='__main__':unittest.main()
