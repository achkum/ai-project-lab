"""Record before/after results without deleting failed-case evidence."""
import json,hashlib
from pathlib import Path
from collections import Counter
from validate_library import match
ROOT=Path(__file__).parent

def evaluate(path,cases):
    raw=path.read_bytes();lib=json.loads(raw);missions={m['id']:m for s in lib['situations'] for m in s['missions']}
    counts={}; failures=[]
    for c in cases:
        m=missions[c['mission_id']];step=next(s for s in m['steps'] if s['id']==c['step_id'])
        actual=match(step,c['text_sv']);ok=actual==c['expected_intent'];bucket=counts.setdefault(c['kind'],{'total':0,'passed':0,'failed':0})
        bucket['total']+=1;bucket['passed']+=ok;bucket['failed']+=not ok
        if not ok:failures.append({**c,'actual_intent':actual})
    positive=[c for c in cases if c['expected_intent'] is not None];negative=[c for c in cases if c['expected_intent'] is None]
    return {'version':lib['content_version'],'sha256':hashlib.sha256(raw).hexdigest(),'case_count':len(cases),'distinct_utterances':len({c['text_sv'] for c in cases}),'valid_replies':{'total':len(positive),'accepted_correctly':len(positive)-sum(c['expected_intent'] is not None for c in failures)},'unsafe_or_offtopic':{'total':len(negative),'rejected_correctly':len(negative)-sum(c['expected_intent'] is None for c in failures)},'by_kind':counts,'failures':failures}

def main():
    cases=json.loads((ROOT/'natural_reply_evaluation.json').read_text(encoding='utf-8'))['cases']
    before=evaluate(ROOT/'snapshots/library-2026-11-01.2.json',cases)
    after=evaluate(ROOT/'library.json',cases)
    report={'status':'Finite authored engineering regression corpus; confirmation phrases repeat across contexts. Distinct utterance count is reported separately. Not an external learner study.','before':before,'after':after,'case_sha256':hashlib.sha256((ROOT/'natural_reply_evaluation.json').read_bytes()).hexdigest(),'repairs':[{'mission_id':c['mission_id'],'step_id':c['step_id'],'text_sv':c['text_sv'],'before':c['actual_intent'],'expected':c['expected_intent']} for c in before['failures'] if not any((f['mission_id'],f['step_id'],f['text_sv'])==(c['mission_id'],c['step_id'],c['text_sv']) for f in after['failures'])]}
    (ROOT/'natural_reply_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for label,result in [('BEFORE',before),('AFTER',after)]:
        print(label,result['version'],result['valid_replies'],result['unsafe_or_offtopic'],'distinct',result['distinct_utterances'])
        for kind,stats in result['by_kind'].items():print(' ',kind,stats)
    return after
if __name__=='__main__':main()
