"""Export stripped semantic contracts and explicit historical compatibility maps.

This tool never reads acceptance corpora, predictions or learner records.
"""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).parent

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def indexed(lib):return {m['id']:m for sit in lib['situations'] for m in sit['missions']}
def incoming(mission,step):
    values=[{'step_id':s['id'],'intent_id':i['id'],'reply_sv':i['reply_sv']} for s in mission['steps'] for i in s['intents'] if i['next_step']==step['id']]
    return values or [{'step_id':None,'intent_id':None,'reply_sv':mission['opening_sv']}]
def offer(mission,step):return '\n'.join(i['reply_sv'] for i in incoming(mission,step))

def export(library_path,output_dir):
    lib=read(library_path);missions=indexed(lib);output_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    for m in missions.values():
        for s in m['steps']:
            allowed=[]
            for i in s['intents']:
                item={k:i.get(k) for k in ['id','meaning_sv','meaning_en','expected_act','reply_sv','next_step','outcome_scope','reference_question_sv']}
                if 'semantic_contract' in i:item['semantic_contract']={k:v for k,v in i['semantic_contract'].items() if k!='example_inventory_role'}
                if 'speech_act_policy' in i:item['speech_act_policy']=i['speech_act_policy']
                allowed.append(item)
            records.append({'task_id':m['id']+'/'+s['id'],'mission_id':m['id'],'step_id':s['id'],'title':m['title'],'level':m['level'],'task_goal':m['goal'],'learner_facts':m['learner_brief_en'],'objective_id':s['objective'],'objective_label':s['objective_label'],'question_sv':s['prompt_sv'],'question_en':s['prompt_en'],'current_offer_sv':offer(m,s),'preceding_authored_context':incoming(m,s),'expected_act':s.get('expected_act'),'speech_act_policy':s.get('speech_act_policy'),'allowed_intents':allowed})
    stripped={'schema_version':'1.0','content_version':lib['content_version'],'source_sha256':sha(library_path),'scope':'Stripped semantic contract: task facts, actual authored offers, permitted meanings and graph. No matcher rules, response examples, tests, candidate outputs or learner records.','records':records}
    write(output_dir/'semantic-contract.stripped.json',stripped)
    act_changes=[];summaries=[]
    legacy_scope_nodes={('lib_clothes_m2','confirm_return'),('lib_social_plans_m1','confirm_nextweek')}
    for version in ['2026-11-01.7','2026-11-01.8']:
        baseline_path=ROOT/'snapshots'/('library-'+version+'.json');old=read(baseline_path);prior=indexed(old);rows=[]
        assert set(prior)==set(missions)
        for mid,m in missions.items():
            before_m=prior[mid];before_steps={s['id']:s for s in before_m['steps']}
            assert set(before_steps)=={s['id'] for s in m['steps']}
            assert before_m['completion_objectives']==m['completion_objectives'] and before_m['start_step']==m['start_step']
            for s in m['steps']:
                old_s=before_steps[s['id']];old_intents={i['id']:i for i in old_s['intents']}
                assert set(old_intents)=={i['id'] for i in s['intents']} and s['objective']==old_s['objective']
                if old_s.get('expected_act')!=s.get('expected_act'):
                    act_changes.append({'from_version':version,'mission_id':mid,'step_id':s['id'],'intent_id':None,'old_expected_act':old_s.get('expected_act'),'new_expected_act':s.get('expected_act')})
                for i in s['intents']:
                    old_i=old_intents[i['id']];assert i['next_step']==old_i['next_step']
                    old_offer=offer(before_m,old_s);new_offer=offer(m,s)
                    changed_offer=old_offer!=new_offer;changed_question=s['prompt_sv']!=old_s['prompt_sv']
                    historical_scope_guard=version=='2026-11-01.7' and (mid,s['id']) in legacy_scope_nodes
                    compat='legacy_manual_label_addressed_a_different_proposition' if historical_scope_guard else 'changed_offer_wording_requires_explicit_session_policy' if changed_offer or changed_question else 'same_offer_and_edges_semantic_or_display_correction'
                    row={'key':mid+'/'+s['id']+'/'+i['id'],'mission_id':mid,'step_id':s['id'],'intent_id':i['id'],
                         'old_current_offer_sv':old_offer,'new_current_offer_sv':new_offer,'old_question_sv':old_s['prompt_sv'],'new_question_sv':s['prompt_sv'],
                         'old_predicate_sv':old_i.get('meaning_sv'),'new_predicate_sv':i.get('meaning_sv'),'old_predicate_en':old_i.get('meaning_en'),'new_predicate_en':i.get('meaning_en'),
                         'old_reply_sv':old_i['reply_sv'],'new_reply_sv':i['reply_sv'],
                         'predicate_changed':(old_i.get('meaning_sv'),old_i.get('meaning_en'))!=(i.get('meaning_sv'),i.get('meaning_en')),
                         'response_changed':old_i['reply_sv']!=i['reply_sv'],'question_changed':changed_question,'offered_context_changed':changed_offer,
                         'matcher_inventory_changed':old_i.get('exact_replies_sv')!=i.get('exact_replies_sv'),
                         'canonical_example_changed':old_i.get('examples_sv')!=i.get('examples_sv'),
                         'goal_changed':before_m['goal']!=m['goal'],'intent_id_changed':False,'edge_changed':False,'objective_id_changed':False,
                         'semantic_contract_added':'semantic_contract' not in old_i and 'semantic_contract' in i,
                         'legacy_manual_label_offer_mismatch':historical_scope_guard,'compatibility_class':compat,
                         'history_rule':'Do not rewrite previous learner replies, chosen meaning labels, assistant turns or evidence. Any corrected checking must record its semantic version separately.',
                         'active_session_rule':'Requires explicit restart/resume reconciliation of the affected offer or manual meaning before further checking.' if historical_scope_guard or changed_offer or changed_question else 'Candidate for an audited future-checking semantic overlay; backend/root must choose policy. Historical text and results remain unchanged.'}
                    rows.append(row)
                    if old_i.get('expected_act')!=i.get('expected_act'):
                        act_changes.append({'from_version':version,'mission_id':mid,'step_id':s['id'],'intent_id':i['id'],'old_expected_act':old_i.get('expected_act'),'new_expected_act':i.get('expected_act')})
        summary={k:sum(bool(r[k]) for r in rows) for k in ['predicate_changed','response_changed','question_changed','offered_context_changed','goal_changed','legacy_manual_label_offer_mismatch','matcher_inventory_changed','canonical_example_changed']}
        output={'schema_version':'1.0','from_version':version,'from_sha256':sha(baseline_path),'to_version':lib['content_version'],'to_sha256':sha(library_path),'decision_owner':'Root/backend; this is a compatibility inventory, not a migration instruction.','stable_graph':True,'counts':summary,'rows':rows}
        write(output_dir/('compatibility-'+version+'-to-2026-11-01.9.json'),output);summaries.append({'from':version,**summary})
    write(output_dir/'expected-act-changes.json',{'content_version':lib['content_version'],'note':'Speech-act metadata changes are reported separately from canonical predicates and responses. These are meaning descriptions, not keyword requirements.','changes':act_changes})
    write(output_dir/'review-summary.json',{'content_version':lib['content_version'],'source_sha256':sha(library_path),'record_count':len(records),'decline_nodes':sum(i['id']=='decline' for m in missions.values() for s in m['steps'] for i in s['intents']),'compatibility':summaries,'stripped_sha256':sha(output_dir/'semantic-contract.stripped.json')})
    print(json.dumps({'records':len(records),'compatibility':summaries,'stripped_sha256':sha(output_dir/'semantic-contract.stripped.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();export(args.library,args.output_dir)
