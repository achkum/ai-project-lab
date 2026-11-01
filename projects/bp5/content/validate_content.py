"""Check deployable content references and evidence boundaries without dependencies."""
import json
from pathlib import Path

root = Path(__file__).parent
curriculum = json.loads((root / 'curriculum.json').read_text(encoding='utf-8'))
scenarios = json.loads((root / 'scenarios.json').read_text(encoding='utf-8'))
criteria = {item['id']: item for item in curriculum['criteria']}
frameworks = {item['id']: item for item in curriculum['frameworks']}
assert len(criteria) == len(curriculum['criteria']), 'Duplicate criterion ID'
assert len({s['id'] for s in scenarios['scenarios']}) == len(scenarios['scenarios'])
assert {s['level'] for s in scenarios['scenarios']} == {'basic','medium','high'}
for criterion in criteria.values():
    framework = frameworks[criterion['framework_id']]
    course = next(c for c in framework['courses'] if c['id'] == criterion['course'])
    assert criterion['course_codes'] == course['course_codes']
    assert criterion['study_paths'] == course['study_paths']
    assert criterion['domain'] in {d['id'] for d in framework['domains']}
    assert criterion['source']['url'].startswith('https://')
    max_page = 7 if criterion['framework_id'].startswith('SKOLFS-2017') else 28
    assert all(1 <= p <= max_page for p in criterion['source']['pages'])
for scene in scenarios['scenarios']:
    for link in scene['criterion_links']:
        target = criteria[link['criterion_id']]
        assert target['framework_id'] == link['framework_id']
        assert link['coverage'] == 'partial' and link['limitation']
        assert link['activity'] in {'dialogue','dialogue_summary','listening','reading','writing','writing_copy_extension'}
    assert scene['listening']['prompt_sv'] != scene['reading']['text_sv'], 'Listening and reading stimuli should not be identical'
    assert scene['phrases'] and scene['supports'] and scene['recall']['suggested_delay_hours'] > 0
    assert scene['original_material'] is True
assert curriculum['selection_rules']['default_framework_id'] is None
assert curriculum['evidence_rules']['automatic_completion_state'] == 'practised'
assert curriculum['evidence_rules']['review_required_for_observed_states'] is True
assert {s['id'] for s in curriculum['evidence_states']} == {'unassessed','practised','observed_with_help','observed_independently'}
print(f'PASS: {len(criteria)} references; 3 complete scenes; explicit version and evidence boundaries.')
