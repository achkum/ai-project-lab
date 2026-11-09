import json
from pathlib import Path
import unittest

from language_context import ContextUnavailable, current_offer


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = json.loads((Path(__file__).parents[1] / 'content/library.json').read_text(encoding='utf-8'))
        cls.missions = {m['id']: m for s in library['situations'] for m in s['missions']}

    def test_trousers_offer_is_not_just_does_that_work(self):
        mission = self.missions['lib_clothes_m2']
        self.assertEqual(current_offer(mission, 'confirm_return'),
                         'Jag lägger byxorna åt sidan så länge. Går det bra?')

    def test_planning_contact_is_distinct_from_meeting_next_week(self):
        mission = self.missions['lib_social_plans_m1']
        self.assertEqual(current_offer(mission, 'confirm_nextweek'),
                         'Vi hörs på måndag och väljer en tid. Går det bra?')

    def test_clarification_does_not_erase_the_offer(self):
        mission = self.missions['lib_clothes_m2']
        turns = [{'role': 'assistant', 'text': 'Jag lägger byxorna åt sidan så länge. Går det bra?'},
                 {'role': 'user', 'text': 'Jag förstår inte.'},
                 {'role': 'assistant', 'text': 'Kan du säga det på ett annat sätt?'}]
        self.assertIn('byxorna', current_offer(mission, 'confirm_return', turns))

    def test_distinct_offers_require_assistant_history(self):
        mission = {'start_step': 'choose', 'opening_sv': 'Välj en dag.', 'steps': [
            {'id': 'choose', 'intents': [
                {'reply_sv': 'Vi ses på tisdag. Går det bra?', 'next_step': 'confirm'},
                {'reply_sv': 'Vi ses på onsdag. Går det bra?', 'next_step': 'confirm'}]},
            {'id': 'confirm', 'prompt_sv': 'Går det bra?', 'intents': []}]}
        with self.assertRaises(ContextUnavailable):
            current_offer(mission, 'confirm', [{'role': 'user', 'content': 'Vi ses på tisdag. Går det bra?'}])
        self.assertEqual(current_offer(mission, 'confirm', [
            {'role': 'assistant', 'content': 'Vi ses på onsdag. Går det bra?'}]),
            'Vi ses på onsdag. Går det bra?')

    def test_missing_step_never_falls_back_to_another_question(self):
        with self.assertRaises(ContextUnavailable):
            current_offer(self.missions['lib_clothes_m2'], 'missing')


if __name__ == '__main__':
    unittest.main()
