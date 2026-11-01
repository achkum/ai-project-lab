import unittest
from engine.vps_publish import compose


class PublisherTests(unittest.TestCase):
    def test_only_curated_allowlisted_cards_and_public_status(self):
        seed={'coverage':{'target':20},'thesis':{},'project':{}}
        cards=[{'id':'A','version':1,'publication':'owner_requested_visual_summary'}, {'id':'B','version':1,'publication':'owner_requested_visual_summary'}]
        jobs=[{'candidate':'A','version':1,'lane':'project','state':'completed','updated':100}]
        out=compose(seed,cards,{'hold':True,'manual_start_ids':['A']},{'generated_at':100,'checks':[]},jobs,[],101)
        self.assertEqual([c['id'] for c in out['opportunities']],['A'])
        self.assertTrue(out['opportunities'][0]['selected'])
        self.assertFalse(out['opportunities'][0]['recommended'])
        self.assertEqual(out['project']['state'],'completed')
        self.assertEqual(seed['thesis'],{})
