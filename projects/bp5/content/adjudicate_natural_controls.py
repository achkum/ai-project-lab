"""Versioned quarantine of historical synthetic controls, without relabelling.

Original artifacts are read-only inputs. The output deliberately distinguishes
uncertain labels from a semantic UNKNOWN class, and repetitive nonsense checks
from diverse natural-language coverage. No acceptance corpus is accessed.
"""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).parent

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def reason(case):
    if case['kind']=='negated_choice':
        return ('synthetic_no_plus_affirmative_choice','Prepending Nej to an affirmative choice is not reliable logical negation. It can correct a previous suggestion or discourse frame. Individual context adjudication is required; no replacement class is assigned.')
    if case['kind']=='unsafe_confirmation' and case['text_sv'] in ['Ja, men nej.','Nej, men ja.']:
        return ('mixed_discourse_markers','Mixed yes/no discourse markers do not have a context-independent UNKNOWN label. Individual scope and final stance require adjudication.')
    if case['kind']=='unsafe_confirmation' and case['text_sv']=='Ja, det passar inte.':
        return ('unreliable_unknown_label_for_negative_proposition','The negative proposition can clearly refuse many offers despite the initial Ja. The historical blanket UNKNOWN label is not gold. Retain for individual context adjudication, not a blanket flip.')
    if case['mission_id']=='lib_reception_m2' and case['step_id'].startswith('confirm_'):
        if case['text_sv'] in ['Absolut, det passar.','Det fungerar fint.','Gärna.','Det passar tyvärr inte.']:
            return ('generic_offer_phrase_at_fact_verification','A willingness/suitability phrase does not reliably verify or deny the stated name. It is quarantined, not declared incorrect Swedish or assigned UNKNOWN as new gold.')
    return None

def adjudicate(source):
    cases=source['cases'];active=[];quarantined=[];controls=[];manifest=[]
    for index,original in enumerate(cases,1):
        case_id=f'natural-v1-{index:06d}';case_hash=digest(original)
        decision=reason(original)
        if decision:
            code,explanation=decision
            item={'case_id':case_id,'source_case_sha256':case_hash,'original_index_1based':index,'original_case':original,'decision':'quarantine_pending_context_adjudication','reason_code':code,'reason':explanation,'eligible_for_gold':False,'eligible_for_training':False}
            quarantined.append(item);manifest.append(item)
        elif original['kind']=='unsafe_confirmation' and original['text_sv']=='Bananerna går till skolan.':
            item={**original,'case_id':case_id,'source_case_sha256':case_hash,'eligibility':'scoped_regression_only','eligible_for_gold':False,'eligible_for_training':False,'coverage_note':'One repeated nonsense string across multiple contexts is not many diverse language examples.'}
            controls.append(item)
            manifest.append({'case_id':case_id,'source_case_sha256':case_hash,'original_index_1based':index,'original_case':original,'decision':'move_to_scoped_regression_controls','reason_code':'repeated_nonsense_control','reason':item['coverage_note'],'eligible_for_gold':False,'eligible_for_training':False})
        else:
            active.append({**original,'case_id':case_id,'source_case_sha256':case_hash,'eligibility':'retained_development_regression','coverage_note':'Retained historical label, not newly or independently validated here.'})
    assert len(active)+len(quarantined)+len(controls)==len(cases)
    summary={'original_case_contexts':len(cases),'retained_case_contexts':len(active),'retained_distinct_texts':len({x['text_sv'] for x in active}),'quarantined_case_contexts':len(quarantined),'quarantined_distinct_texts':len({x['original_case']['text_sv'] for x in quarantined}),'scoped_regression_contexts':len(controls),'scoped_regression_distinct_texts':len({x['text_sv'] for x in controls}),'replacement_labels_assigned':0,'quarantine_reasons':dict(Counter(x['reason_code'] for x in quarantined))}
    return active,quarantined,controls,manifest,summary

def publish(source):
    original_path=ROOT/'natural_reply_evaluation.json'
    frozen=json.loads(original_path.read_text(encoding='utf-8'))
    assert source['cases']==frozen['cases'],'Historical generator cases changed; create and document a new adjudication version instead of silently replacing this source.'
    original_hash=hashlib.sha256(original_path.read_bytes()).hexdigest()
    active,quarantine,controls,manifest,summary=adjudicate(source)
    common={'schema_version':'3.0','adjudication_version':'2026-11-02.v2','source_artifact':original_path.name,'source_sha256':original_hash,'policy':'No automatic positive/negative flips. Quarantine is not the UNKNOWN class. Repetition is reported separately from distinct language. These are disclosed development artifacts, not independent acceptance data.','summary':summary}
    outputs={
      'natural_reply_evaluation.v2.json':{**common,'cases':active},
      'natural_reply_quarantine.v2.json':{**common,'cases':quarantine},
      'natural_reply_regression_controls.v2.json':{**common,'cases':controls},
      'natural_reply_adjudication.v2.json':{**common,'removed_or_quarantined_cases':manifest}
    }
    for filename,data in outputs.items():
        (ROOT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert hashlib.sha256(original_path.read_bytes()).hexdigest()==original_hash
    print(json.dumps(summary))

if __name__=='__main__':publish(json.loads((ROOT/'natural_reply_evaluation.json').read_text(encoding='utf-8')))
