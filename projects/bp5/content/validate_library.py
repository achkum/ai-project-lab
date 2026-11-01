"""Validate every guided path plus separate paraphrase/negative fixtures.

Implements the published content contract independently of server code. Backend
tests must also consume these cases; agreement is useful, not pedagogical proof.
"""
import json,re,unicodedata,hashlib
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).parent

def tokens(text): return re.findall(r"[^\W_]+",unicodedata.normalize('NFKC',text).casefold(),re.UNICODE)
def contains(text,phrase):
    a=tokens(text);b=tokens(phrase)
    return bool(b) and any(a[i:i+len(b)]==b for i in range(len(a)-len(b)+1))
def match(step,text):
    results=[i for i in step['intents'] if any(tokens(text)==tokens(p) for p in i.get('exact_replies_sv',[])) or (i.get('required_groups') and all(any(contains(text,p) for p in group) for group in i['required_groups']) and not any(contains(text,p) for p in i.get('reject_terms',[])))]
    return results[0]['id'] if len(results)==1 else None

def main():
    library=json.loads((ROOT/'library.json').read_text(encoding='utf-8'))
    curriculum=json.loads((ROOT/'curriculum.json').read_text(encoding='utf-8'))
    criteria={c['id']:c for c in curriculum['criteria']}
    situations=library['situations']; assert len(situations)==18
    assert Counter(s['level'] for s in situations)=={'basic':8,'medium':6,'high':4}
    missions={m['id']:m for s in situations for m in s['missions']}; assert len(missions)==54
    assert all(len(s['missions'])==3 for s in situations)
    paths=examples=rejects=exact_examples=0; failures=[]
    for mid,m in missions.items():
        steps={s['id']:s for s in m['steps']}; assert len(steps)==len(m['steps'])
        assert len({m2['goal'] for m2 in missions.values()})==54
        assert m['mode']=='guided' and m['learner_brief_en']
        if m['level']=='high': assert len(m['completion_objectives'])>=6 and m['mode_label']=='Guided discussion'
        assert m['reading']['text_sv']!=m['listening']['prompt_sv']
        for link in m['criterion_links']:
            assert link['criterion_id'] in criteria
            assert criteria[link['criterion_id']]['framework_id']==link['framework_id']
            assert link['coverage']=='partial' and link['limitation']
        for step in steps.values():
            assert step['unknown_reply_sv'] and step['unknown_feedback_en']
            for intent in step['intents']:
                assert intent['next_step'] is None or intent['next_step'] in steps
                assert (intent['required_groups'] and all(g for g in intent['required_groups'])) or intent.get('exact_replies_sv')
                for example in intent['examples_sv']:
                    examples+=1
                    if match(step,example)!=intent['id']: failures.append((mid,step['id'],example,'authored example mismatch'))
                for example in intent.get('exact_replies_sv',[]):
                    exact_examples+=1
                    if match(step,example)!=intent['id']:failures.append((mid,step['id'],example,'approved exact reply conflicts'))
                    extra=example+' Nej, jag vill inte.'
                    if match(step,extra)==intent['id']:failures.append((mid,step['id'],extra,'contradictory suffix accepted'))
                for reject in intent.get('reject_terms',[]):
                    rejects+=1
                    test=intent['examples_sv'][0]+' '+reject
                    if match(step,test)==intent['id']: failures.append((mid,step['id'],test,'rejected term accepted'))
            for random in ['blå bananer kör bil','Jag vill prata om en film på månen.','', '???']:
                if match(step,random) is not None: failures.append((mid,step['id'],random,'off-topic advancement'))
        reached=set()
        def walk(step_id,objectives,trail):
            nonlocal paths
            assert step_id not in trail, f'Unbounded cycle {mid} {trail}'
            reached.add(step_id); step=steps[step_id]; done=objectives|{step['objective']}
            for intent in step['intents']:
                if intent['next_step'] is None:
                    paths+=1
                    assert set(m['completion_objectives'])<=done, f'Premature completion {mid}'
                else: walk(intent['next_step'],done,trail+[step_id])
        walk(m['start_step'],set(),[])
        assert reached==set(steps),f'Unreachable content {mid}'
        # Combining distinct offered options must clarify, not silently pick one.
        choice=steps['choice']; both=' '.join(i['examples_sv'][0] for i in choice['intents'])
        if match(choice,both) is not None: failures.append((mid,'choice',both,'ambiguous options advanced'))
    cases=json.loads((ROOT/'library_evaluation.json').read_text(encoding='utf-8'))['cases']
    for c in cases:
        step=next(s for s in missions[c['mission_id']]['steps'] if s['id']==c['step_id'])
        actual=match(step,c['text_sv'])
        if actual!=c['expected_intent']: failures.append((c['mission_id'],c['step_id'],c['text_sv'],f"{c['kind']} expected {c['expected_intent']!r}, got {actual!r}"))
    # Common elliptic café replies remain valid; irrelevant and negated use does not.
    cafe=missions['lib_cafe_m1']['steps'][0]
    for utterance,expected in [('En kaffe, tack.','request_answer'),('Jag tar en kaffe.','request_answer'),('Jag tar ingen kaffe.',None),('Jag drömmer om kaffe.',None)]:
        if match(cafe,utterance)!=expected: failures.append(('lib_cafe_m1','request',utterance,'common café regression'))
    for failure in failures: print('FAIL',*failure,sep=' | ')
    if failures: raise SystemExit(f'{len(failures)} content/recognition failures')
    report={'content_version':library['content_version'],'passed':True,'situations':18,'missions':54,'terminal_paths':paths,'authored_examples':examples,'approved_exact_reply_contexts':exact_examples,'contradictory_exact_suffix_checks':exact_examples,'rejected_term_checks':rejects,'separately_authored_regression_cases':len(cases),'additional_common_phrase_cases':4,'hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['library.json','library_evaluation.json','curriculum.json','scenarios.json']},'limits':['Engineering checks only; production backend must verify the same fixtures with its own matcher.','The 162 separate cases were authored without importing the canonical examples; first execution revealed three failures which were fixed. They are now regression cases.','No independent Swedish educator review or learner-effectiveness study.','Exact pattern matching deliberately rejects unsupported paraphrases; completion is practice, not mastery.']}
    (ROOT/'library_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: 18 situations, 54 missions, {paths} terminal paths, {examples} authored replies, {exact_examples} approved exact reply contexts, {rejects} reject checks, {len(cases)} separate evaluation cases.')

if __name__=='__main__':main()
