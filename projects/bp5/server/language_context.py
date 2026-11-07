"""Resolve the authored offer a learner is answering, without guessing from 'it'."""
import unicodedata


class ContextUnavailable(ValueError):
    """The current offer cannot be resolved safely from this snapshot/history."""


def _key(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def current_offer(mission, current_step, recent_turns=()):
    """Return an actual authored utterance, retaining context omitted by a suffix.

    The persisted mission graph is authoritative. Learner text is never used to
    invent an assistant offer. A unique incoming utterance also works for an
    older saved session whose bounded history no longer includes the offer.
    Distinct incoming offers require a matching recent assistant utterance.
    """
    if not isinstance(mission, dict):
        raise ContextUnavailable('Invalid mission snapshot')
    steps = mission.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
        raise ContextUnavailable('Invalid mission graph')
    sid = current_step.get('id') if isinstance(current_step, dict) else current_step
    found = [step for step in steps if isinstance(step, dict) and step.get('id') == sid]
    if len(found) != 1:
        raise ContextUnavailable('Current step is missing or ambiguous')
    offers = {}
    if sid == mission.get('start_step'):
        opening = mission.get('opening_sv')
        if isinstance(opening, str) and opening.strip():
            offers[_key(opening)] = opening.strip()
    for previous in steps:
        if not isinstance(previous, dict):
            raise ContextUnavailable('Invalid mission graph')
        intents = previous.get('intents', [])
        if not isinstance(intents, list) or len(intents) > 16:
            raise ContextUnavailable('Invalid mission choices')
        for intent in intents:
            if not isinstance(intent, dict):
                raise ContextUnavailable('Invalid mission choice')
            text = intent.get('reply_sv')
            if intent.get('next_step') == sid and isinstance(text, str) and text.strip():
                offers[_key(text)] = text.strip()
    if not offers or any(len(text) > 4000 for text in offers.values()):
        raise ContextUnavailable('Current offer is missing or too long')
    if isinstance(recent_turns, (list, tuple)):
        for turn in reversed(recent_turns[-16:]):
            if not isinstance(turn, dict) or turn.get('role') != 'assistant':
                continue
            text = turn.get('text', turn.get('content'))
            if isinstance(text, str) and len(text) <= 4000 and _key(text) in offers:
                return offers[_key(text)]
    if len(offers) == 1:
        return next(iter(offers.values()))
    raise ContextUnavailable('Different offers need the actual conversation context')
