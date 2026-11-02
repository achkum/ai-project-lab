"""Original authored guided practice. Rebuild library.json without models or network."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
VERSION = '2026-11-01.9'
NEG = ['inte', 'aldrig', 'inget', 'ingen', 'inga', 'nej']

def G(*groups):
    return [g.split('|') for g in groups]

def D(prompt, goal, sv, en, groups, reject=None):
    d={'prompt':prompt,'goal':goal,'sv':sv,'en':en,'groups':groups}
    if reject is not None: d['reject']=reject
    return d

def branch(id, sv, en, groups, reply, confirm):
    return {'id':id,'sv':sv,'en':en,'groups':groups,'reply':reply,'confirm':confirm}

def task(n, title, goal, opening, request, groups, choice, branches, reading, listening, writing, recall, reason=None, discussion=None, heldout=None):
    return dict(n=n,title=title,goal=goal,opening=opening,request=request,groups=groups,choice=choice,branches=branches,reading=reading,listening=listening,writing=writing,recall=recall,reason=reason,discussion=discussion,heldout=heldout)

def build_mission(situation, t):
    mid=f"{situation['id']}_m{t['n']}"
    steps=[]
    def add_step(id,prompt,objective,label,sv,en,groups,reply,next_step,reject=None):
        steps.append({'id':id,'prompt_sv':prompt,'prompt_en':label,'objective':objective,'objective_label':label,'intents':[{'id':id+'_answer','examples_sv':[sv],'required_groups':groups,'reject_terms':NEG if reject is None else reject,'reply_sv':reply,'next_step':next_step,'feedback_en':label+' Your reply supplied the required information.','branch':id}], 'unknown_reply_sv':'Jag är inte säker på vad du menar. Kan du säga det på ett annat sätt?', 'unknown_feedback_en':'This guided exercise did not recognise the intended reply. Try the target meaning in your own words, or reveal a phrase. Nothing has been marked complete.','hint_sv':sv,'hint_en':en})
    # Optional guided discussion turns are substantive authored steps, not fillers.
    chain=t.get('discussion') or ([] if not t.get('reason') else [t['reason']])
    first_next='detail_1' if chain else 'choice'
    next_prompt=chain[0]['prompt'] if chain else t['choice']
    add_step('request',t['opening'],'request',t['goal'],t['request'][0],t['request'][1],t['groups'],next_prompt,first_next)
    for i,d in enumerate(chain):
        nxt=f'detail_{i+2}' if i+1<len(chain) else 'choice'
        reply=chain[i+1]['prompt'] if i+1<len(chain) else t['choice']
        add_step(f'detail_{i+1}',d['prompt'],f'detail_{i+1}',d['goal'],d['sv'],d['en'],d['groups'],reply,nxt,d.get('reject'))
    intents=[]
    for b in t['branches']:
        intents.append({'id':'choose_'+b['id'],'examples_sv':[b['sv']],'required_groups':b['groups'],'reject_terms':b.get('reject',NEG),'reply_sv':b['reply']+' '+b['confirm'],'next_step':'confirm_'+b['id'],'feedback_en':'You selected a concrete option; the next reply follows that choice.','branch':b['id']})
    steps.append({'id':'choice','prompt_sv':t['choice'],'prompt_en':'Choose between the actual options.','objective':'choose','objective_label':'Respond to the available options.','intents':intents,'unknown_reply_sv':'Vilket av förslagen vill du välja? Du kan också be mig att förklara.','unknown_feedback_en':'Name one offered option. Contradictory or unclear replies do not advance.','hint_sv':t['branches'][0]['sv'],'hint_en':t['branches'][0]['en']})
    for b in t['branches']:
        steps.append({'id':'confirm_'+b['id'],'prompt_sv':b['confirm'],'prompt_en':'Confirm or decline the proposed arrangement.','objective':'confirm','objective_label':'Confirm or politely decline the actual plan.','intents':[
            {'id':'confirm','examples_sv':['Ja, det går bra.'],'required_groups':G('ja|det går bra|det passar bra'),'reject_terms':NEG,'reply_sv':'Bra, då är vi överens i övningen. Tack för samtalet!','next_step':None,'feedback_en':'You confirmed the proposed arrangement. This completes this practice task, not a language level.','branch':b['id']+'_confirmed'},
            {'id':'decline','examples_sv':['Nej, det passar inte.'],'required_groups':G('nej','passar inte|går inte|vill inte'),'reject_terms':['ja'],'reply_sv':'Okej, då bestämmer vi inget den här gången. Tack för att du sa till.','next_step':None,'feedback_en':'You clearly declined the arrangement. That is a valid communicative outcome, not a failure.','branch':b['id']+'_declined'}
        ],'unknown_reply_sv':'Passar förslaget, eller vill du tacka nej?','unknown_feedback_en':'Confirm the specific proposal or say that it does not work. A random reply will not complete the task.','hint_sv':'Ja, det går bra. / Nej, det passar inte.','hint_en':'Yes, that works. / No, that does not work.'})
    objectives=['request']+[f'detail_{i+1}' for i in range(len(chain))]+['choose','confirm']
    r=t['reading']; l=t['listening']; w=t['writing']; rc=t['recall']
    phrases=[{'id':mid+'_request','sv':t['request'][0],'en':t['request'][1],'usage':t['goal']}]
    phrases += [{'id':mid+'_'+b['id'],'sv':b['sv'],'en':b['en'],'usage':'Choose this option only if it matches what you want to say.'} for b in t['branches']]
    phrases += [{'id':mid+f'_detail_{i+1}','sv':d['sv'],'en':d['en'],'usage':d['goal']} for i,d in enumerate(chain)]
    phrases.append({'id':mid+'_repair','sv':'Kan du förklara vad du menar?','en':'Could you explain what you mean?','usage':'Ask for clarification. The guided engine may offer its authored hint rather than understand unrestricted dialogue.'})
    return {'id':mid,'situation_id':situation['id'],'level':situation['level'],'title':t['title'],'title_sv':t['title'],'description':t['goal'],'goal':t['goal'],'mode':'guided','mode_label':'Guided discussion' if situation['level']=='high' else 'Guided conversation','opening_sv':t['opening'],'opening_en':t['goal'],'character':situation['character'],'estimated_minutes':3 if situation['level']=='basic' else 6 if situation['level']=='medium' else 10,'start_step':'request','steps':steps,'completion_objectives':objectives,'objectives':[s['objective_label'] for s in steps if not s['id'].startswith('confirm_')]+['Confirm or decline the arrangement.'],'phrases':phrases,'reading':{'text_sv':r[0],'question_en':r[1],'answer_ideas_en':r[2]},'listening':{'prompt_sv':l[0],'question_en':l[1],'answer_ideas_en':l[2],'delivery':'Hide the source text until an answer is submitted. Revealing it leaves listening unassessed.'},'writing':{'prompt_sv':w[0],'prompt_en':w[1],'starter_sv':''},'recall':{'prompt_sv':rc[0],'prompt_en':rc[1],'transfer_en':rc[2],'suggested_delay_hours':24 if situation['level']!='high' else 48},'coaching':{'focus':t['goal'],'completion_note':'Task completed means the authored communication objectives were attempted successfully in this guided exchange. It is not mastery, placement or a course pass.'},'context_prompt':'Choose a real or fictional reason this situation matters to you. Keep personal details optional.','feeling_options':['curious','uncertain','hopeful','prefer not to say'],'supports':[{'id':'phrase_hint','label':'Show a phrase','effect':'Reveals an example; record supported practice.'},{'id':'replay','label':'Replay','effect':'Record audio replay.'},{'id':'translation','label':'English help','effect':'Record English assistance.'},{'id':'typed_fallback','label':'Type instead','effect':'Typed text is not speaking evidence.'}],'criterion_links':mapping(situation['level']),'progression':{'order':t['n'],'suggested_after':None if t['n']==1 else f"{situation['id']}_m{t['n']-1}",'repeat_prompt':'Try again with the other option, then try without phrase hints. New attempts remain separate.','unlock_policy':'Recommended order only; all tasks remain accessible.'},'original_material':True,'assessment_limit':'Deterministic pattern recognition validates a narrow task intention, not broad language competence. Unsupported inputs request clarification. No pronunciation, official grade or calibrated ability score.'}

def mapping(level):
    curriculum=json.loads((ROOT/'curriculum.json').read_text(encoding='utf-8'))
    courses={'basic':['A','B','1A','1B','2B'],'medium':['B','C','1B','2B','1C','2C','3C'],'high':['C','D','1C','2C','3C','1D','2D','3D']}[level]
    activity={'listening':'listening','reading':'reading','spoken_interaction':'dialogue','speaking_and_conversation':'dialogue','writing':'writing'}
    sampled={
        'listening':('Locate specific information in one short, clearly spoken everyday message.','No claim about lengthy speech, detailed instructions, unfamiliar speakers or general listening ability. Revealed source text cannot establish listening.'),
        'reading':('Locate and explain selected information in one short familiar message or notice.','Does not establish comprehension across text types, independent reading consistency, or the full course criterion.'),
        'dialogue':('Practise a request, a response to offered options, and confirmation or polite refusal.' if level=='basic' else 'Practise explaining a reason and negotiating a practical arrangement.' if level=='medium' else 'Practise describing a constraint, suggesting an idea, weighing a benefit and drawback, offering a fallback and inviting another view.', 'Authored guided turns do not establish unrestricted conversation, pronunciation, fluency or full oral production. Typed or edited-ASR answers cannot establish an independent spoken performance.'),
        'writing':('Compose one short message for a stated audience and everyday purpose.','No automatic judgement of grammatical control, coherence, variation or full course coverage. Dictation cannot establish independent writing.')
    }
    result=[]
    for c in curriculum['criteria']:
        if c['course'] not in courses or c['domain'] not in activity: continue
        # Current A writing involves personal details/copying, not these composed messages.
        if c['framework_id']=='SKOLFS-2017-91-consolidated' and c['course']=='A' and c['domain']=='writing': continue
        key=activity[c['domain']]
        result.append({'framework_id':c['framework_id'],'criterion_id':c['id'],'activity':key,'coverage':'partial','sampled_component':sampled[key][0],'limitation':sampled[key][1]+' Guided completion is practice, not an independently reviewed skill observation; all help remains attached to the attempt.'})
    return result

def situation(id,level,title,title_sv,description,character,tasks):
    from library_sources.localization import TEXT
    from library_sources.language_revision import revise
    s={'id':'lib_'+id,'level':level,'title':title,'title_sv':title_sv,'description':description,'estimated_minutes':3 if level=='basic' else 6 if level=='medium' else 10,'character':{'name':character[0],'role':character[1],'persona':'Respectful adult conversation partner. Only authored Swedish replies are used.'},'missions':[]}
    s['missions']=[build_mission(s,t) for t in tasks]
    for mission,t in zip(s['missions'],tasks):
        mission['title_sv'],mission['opening_en']=TEXT[id][t['n']-1]
        chain=t.get('discussion') or ([] if not t.get('reason') else [t['reason']])
        mission['learner_brief_en']='Fictional task facts: '+t['request'][1]+' '+' '.join(d['en'] for d in chain)
        mission['response_guidance_en']='Communicate the task facts in Swedish, then choose an offered option. This is guided practice with limited recognised phrasing; a clarification is not a judgement of your Swedish.'
        for step in mission['steps']:
            step['prompt_en_kind']='task_guidance'
    revise(s)
    from library_sources.context_clarifications import apply_context_clarifications
    from library_sources.refusal_contract import apply_refusal_contract
    for mission in s['missions']:
        apply_context_clarifications(mission)
        apply_refusal_contract(mission)
    return s

def main(output_path=None):
    from library_sources.basic import situations as basic
    from library_sources.medium import situations as medium
    from library_sources.high import situations as high
    situations=basic()+medium()+high()
    data={'schema_version':'2.0','content_version':VERSION,'language':'sv-SE','help_language':'en','legacy_policy':'Legacy scenarios.json is unchanged. Existing sessions resume their frozen snapshots; no old evidence is silently converted to guided missions.','learning_limit':'Guided task completion is not mastery. Basic/Medium/High are practice challenge labels, not SFI courses. Emotional-context benefit and retention effects remain unvalidated.','situations':situations,'provenance':{'authorship':'Original fictional dialogue, messages and exercises authored for BP5. No commercial lessons or national-test items copied.','curriculum_source':'curriculum.json retains official sources, pages and framework versions. All task links are partial authored interpretations, not an educator-validated course.','review_status':'Authored language/flow review plus deterministic engineering tests. No independent Swedish educator review, learner usability trial or learning-effectiveness validation has occurred.','evaluation':'library_evaluation.json contains separately authored paraphrases and negatives. After first execution and corrections these are regression cases, not a permanently unseen set.'}}
    output_path=Path(output_path) if output_path else ROOT/'library.json'
    output_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Built {len(situations)} situations and {sum(len(s["missions"]) for s in situations)} guided missions.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output')
    main(parser.parse_args().output)
