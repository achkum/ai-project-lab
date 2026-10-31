import json
import unittest
from pathlib import Path
from engine.opportunity_quality import validate_card

class OpportunityQualityTests(unittest.TestCase):
    def test_published_project_cards_pass_and_incomplete_or_false_default_fails(self):
        cards=json.loads((Path(__file__).resolve().parents[1]/'config/public-opportunities.json').read_text(encoding='utf-8'))
        projects=[c for c in cards if c['lane']=='Project']
        self.assertTrue(projects)
        for c in projects:
            self.assertEqual(c['quality_gate_version'],2)
            validate_card(c)
            with self.assertRaises(ValueError):validate_card(dict(c,buyer=''))
            with self.assertRaises(ValueError):validate_card(dict(c,auto_eligible=False,recommended=True))
