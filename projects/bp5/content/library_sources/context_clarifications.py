"""Reviewed wording fixes keep a final response attached to its actual offer."""
import json
from pathlib import Path

CLARIFICATIONS = json.loads(Path(__file__).with_name('english_clarifications.json').read_text(encoding='utf-8'))
ENDINGS = {
    ('lib_clothes_m2', 'confirm_return', 'decline'):
        'Okej, jag lägger inte undan byxorna. Du är välkommen tillbaka.',
    ('lib_social_plans_m1', 'confirm_nextweek', 'confirm'):
        'Då hörs vi på måndag och bestämmer en tid för vår fika.',
    ('lib_social_plans_m1', 'confirm_nextweek', 'decline'):
        'Okej, vi hörs en annan dag för att bestämma en tid.',
}


def apply_context_clarifications(mission):
    for step in mission['steps']:
        for intent in step['intents']:
            key = (mission['id'], step['id'], intent['id'])
            correction = CLARIFICATIONS.get('/'.join(key))
            if correction:
                if intent['meaning_en'] != correction['old']:
                    raise ValueError('English clarification source changed: ' + '/'.join(key))
                intent['meaning_en'] = correction['new']
                if step['id'].startswith('confirm_'):
                    intent['feedback_en'] = 'Your meaning: ' + correction['new']
            if key in ENDINGS:
                intent['reply_sv'] = ENDINGS[key]
