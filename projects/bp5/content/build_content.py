"""Rebuild original BP5 starter content. No network or learner data required."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
OLD = 'SKOLFS-2017-91-consolidated'
NEW = 'SKOLFS-2026-67'
OLD_URL = 'https://syllabuswebb.skolverket.se/syllabuscw/jsp/sfi.htm'
OLD_PDF = 'https://syllabuswebb.skolverket.se/subject/SFI/11/pdf'
NEW_URL = 'https://skolfs.skolverket.se/api/document/GRUNDFORFATTNING/2026:67/pdf'
DOMAINS = ['listening', 'reading', 'spoken_interaction', 'spoken_production', 'writing']
NEW_DOMAINS = ['listening', 'reading', 'speaking_and_conversation', 'writing']
LABELS = dict(zip(DOMAINS, ['Listen and understand', 'Read and understand', 'Take part in a conversation', 'Explain aloud', 'Write a useful message']))
LABELS['speaking_and_conversation'] = 'Speak and take part in a conversation'
old_summaries = {
 'A': ['Follow supported, clear everyday speech.', 'Understand very simple familiar information.', 'Exchange basic questions and polite phrases with support.', 'Tell personal details using supported simple phrases.', 'Write personal details and copy needed information.'],
 'B': ['Understand clear everyday speech and short instructions.', 'Read simple familiar texts and messages.', 'Exchange wishes and questions with support.', 'Describe familiar experiences simply with support.', 'Write understandable short everyday messages.'],
 'C': ['Understand clear simple speech in familiar settings.', 'Read familiar texts and reason simply about information.', 'Exchange ideas with some adaptation to the partner.', 'Describe experiences and give simple advice coherently.', 'Write connected familiar texts with some adaptation.'],
 'D': ['Understand clear speech including detailed instructions.', 'Read varied familiar texts and reason about information.', 'Discuss and respond to opinions with simple arguments.', 'Explain familiar matters with some fluency and variation.', 'Write structured varied texts for different purposes.'],
}
new_summaries = {
 'A': ['Understand slow, clear simple speech on very familiar topics.', 'Understand short simple texts on very familiar topics.', 'Communicate understandably with individual words and phrases.', 'Write familiar words and phrases in a largely functional way.'],
 'B': ['Understand clear simple speech on very familiar topics.', 'Understand simple texts on very familiar topics.', 'Communicate understandably with phrases and sentences.', 'Write simple understandable texts on very familiar topics.'],
 'C': ['Understand clear simple speech on familiar topics.', 'Understand simple texts on familiar topics.', 'Speak with some coherence, adaptation and variation; partly sustain conversation.', 'Write simple structured texts with some coherence, adaptation and grammatical control.'],
 'D': ['Understand clear speech on familiar topics.', 'Understand texts on familiar topics.', 'Speak with some coherence, adaptation and variation; largely sustain conversation.', 'Write structured informal and more formal texts with some adaptation and grammatical control.'],
}
criteria = []
old_courses = []
for course in 'ABCD':
    paths = [1] if course == 'A' else [1, 2] if course == 'B' else [1, 2, 3]
    codes = [f'SFIKU{course}9{path}' for path in paths]
    old_courses.append({'id': course, 'label': f'Course {course}', 'study_paths': paths, 'course_codes': codes})
    for domain, summary in zip(DOMAINS, old_summaries[course]):
        page = {'A': 4, 'B': 5, 'C': 6, 'D': 7}[course]
        if course == 'A' and domain in ['spoken_production', 'writing']: page = 5
        criteria.append({'id': f'old_{course}_{domain}', 'framework_id': OLD, 'course': course, 'course_codes': codes, 'study_paths': paths, 'domain': domain, 'label': LABELS[domain], 'summary_en': summary, 'source': {'url': OLD_URL, 'pdf_url': OLD_PDF, 'pages': [page], 'section': f'Kurs {course} / Betygskriterier / ' + {'listening':'Hörförståelse','reading':'Läsförståelse','spoken_interaction':'Muntlig interaktion','spoken_production':'Muntlig produktion','writing':'Skriftlig färdighet'}[domain]}, 'coverage_limit': 'Short summary of one area; consult the complete criterion. One familiar scene cannot demonstrate its breadth, consistency or an official course result.'})
new_courses = []
for course, pages in {'1A':[5], '1B':[7], '1C':[9], '1D':[12], '2B':[15], '2C':[17], '2D':[19,20], '3C':[23], '3D':[25]}.items():
    code = f'VSFI{course}0'
    new_courses.append({'id': course, 'label': f'Course {course}', 'study_paths': [int(course[0])], 'course_codes': [code]})
    for domain, summary in zip(NEW_DOMAINS, new_summaries[course[-1]]):
        actual_pages = pages
        if course == '2D': actual_pages = [19,20] if domain == 'speaking_and_conversation' else [20] if domain == 'writing' else [19]
        criteria.append({'id': f'new_{course}_{domain}', 'framework_id': NEW, 'course': course, 'course_codes': [code], 'study_paths': [int(course[0])], 'domain': domain, 'label': LABELS[domain], 'summary_en': summary, 'source': {'url': NEW_URL, 'pdf_url': NEW_URL, 'pages': actual_pages, 'section': f'Bilaga {course[0]} / Kurs {course} / Betygskriterier'}, 'coverage_limit': 'Summary, not the complete criterion or an assessment rubric. The task samples one familiar context; course-specific teaching needs and wider evidence remain outside this starter.'})

curriculum = {
 'schema_version': '1.0', 'content_version':'2026-11-01.1', 'verified_at':'2026-11-01',
 'title':'SFI practice evidence',
 'notice':'These are practice observations, not an official grade, placement or pass prediction. Basic, Medium and High describe role-play challenge, not SFI courses.',
 'mapping_status':'Official references checked; task mappings are authored starter interpretations awaiting qualified SFI educator review.',
 'frameworks': [
  {'id':OLD, 'label':'Current SFI syllabus (2017:91 consolidated)', 'source_url':OLD_URL, 'pdf_url':OLD_PDF, 'domains':[{'id':d,'label':LABELS[d]} for d in DOMAINS], 'courses':old_courses, 'assessment_note':'Five knowledge areas support a teacher’s overall judgement; they are not five separate official grades.', 'assessment_source':{'url':OLD_PDF,'pages':[4],'section':'Bedömning'}, 'applicability':'Retained for courses begun before 2027-01-01; confirm the applicable framework with the school.'},
  {'id':NEW, 'label':'SFI course syllabuses (2026:67)', 'source_url':NEW_URL, 'pdf_url':NEW_URL, 'published_at':'2026-06-23', 'effective_at':'2026-08-15', 'applies_to_education_starting_from':'2027-01-01', 'domains':[{'id':d,'label':LABELS[d]} for d in NEW_DOMAINS], 'courses':new_courses, 'assessment_note':'Speaking and conversation share an oral criterion. Do not silently merge old evidence into this criterion.', 'applicability':'Applies to education begun after 2026-12-31. Previous rules remain for courses begun before 2027-01-01.', 'transition_source':{'url':NEW_URL,'pages':[1,2],'section':'Commencement and transitional provisions 1–3'}}
 ],
 'criteria':criteria,
 'selection_rules': {
  'default_framework_id':None, 'default_course':None, 'default_study_path':None,
  'required_for_mapping':['framework_id','course','study_path'],
  'unknown_profile_behavior':'Allow all practice, but keep course-specific evidence unassigned until the learner selects their actual course and framework.',
  'date_rule':'Course start is a transition clue, not automatic placement. Ask for school-confirmed framework when unclear; do not select from today’s date.',
  'history_rule':'Freeze framework, course, study path, criterion ID, source and content version on every evidence record. A later profile change never rewrites earlier records.',
  'difficulty_rule':'Never infer course or study path from basic, medium or high.',
  'unsupported_courses':['VSFILS0','VSFILA0'],
  'unsupported_course_note':'Foundational literacy and Latinisation courses need a separate teaching design; this text-using starter does not cover them.'
 },
 'evidence_states': [
  {'id':'unassessed','label':'Not assessed','meaning':'No usable observation for this activity and criterion.'},
  {'id':'practised','label':'Practised','meaning':'An attempt exists. It has not established successful performance.'},
  {'id':'observed_with_help','label':'Observed with help','meaning':'A specific successful action was reviewed; aids or prompts were used and are recorded.'},
  {'id':'observed_independently','label':'Observed independently','meaning':'A specific successful action was reviewed without task-specific aids on this attempt. This is not mastery or course completion.'}
 ],
 'evidence_rules': {
  'automatic_completion_state':'practised',
  'review_required_for_observed_states':True,
  'review_note':'Save the actual action, evidence excerpt, reviewer type (learner, educator or provisional automated feedback), limitations and help used. Keyword matching alone cannot promote an observation.',
  'required_record_fields':['id','created_at','scenario_id','activity','input_mode','framework_id','course','study_path','criterion_id','source','content_version','state','evidence','hints_used','reviewer_type','uncertainty'],
  'listening':'Record audio played, text visibility, replay and translation. If the answer or transcript was visible before responding, keep listening unassessed; record supported multimodal practice separately.',
  'reading':'Require an answer based on the displayed text. Audio reading or translation assistance must be recorded; listening to it alone is not independent reading.',
  'speaking':'Typed turns are not speaking evidence. Speech transcripts may support limited content observations after correction; they cannot establish pronunciation, prosody, fluency or comprehensibility from audio.',
  'writing':'Dictation or copied phrase text is not independent writing. Keep input provenance and mark unknown provenance as unknown rather than assuming independence.',
  'help':'Phrase hints, translation, model answers, notes, transcript visibility, replay and slow audio remain visible with the attempt. With-help is useful evidence, not a failure.',
  'missing':'Never average missing skills into a score or infer one skill from another. Keep each unmapped or unobserved area unassessed.',
  'forbidden_outputs':['official_grade','placement','pass_probability','calibrated_confidence','overall_pass','pronunciation_score_from_transcript'],
  'progress_example':'In this supported request you explained what you needed. Next, try responding to a follow-up before opening a phrase hint.'
 },
 'coverage':{'scope':'Three original everyday scenes and linked tasks; all criterion links are partial.', 'not_covered':['national test readiness','full breadth of any course','formal workplace discussion','news and extended narratives','tables and diagrams','foundational literacy','systematic pronunciation assessment','independent teacher validation'], 'unlinked_rule':'A selected course or domain with no matching task link is shown as not covered, not failed.'},
 'learning_hypothesis':{'claim':'Learner-chosen meaning and feelings may make practice relevant; improved retention is an untested hypothesis.', 'method':'Offer optional self-described feelings and fictional alternatives. Compare later phrase recall and transfer, not enjoyment alone.', 'privacy':'No emotion inference from voice. A personal reason or feeling is optional; fictional context works equally well.'},
 'provenance':{'scenario_authorship':'Original BP5 fictional material, 2026-11-01; no national test or commercial lesson items.', 'source_review':'Current HTML plus linked seven-page consolidated PDF; downloaded 28-page 2026:67 regulation, extracted relevant pages and visually checked transition and criterion pages.', 'uncertainties':['Task difficulty and support have not been calibrated with learners.','Mappings and feedback need review by a qualified SFI educator.','No reliability, readiness accuracy or retention improvement has been validated.']}
}

common_supports = [
 {'id':'phrase_hint','label':'Phrase hint','effect':'Shows a Swedish starter with English meaning; record help used.'},
 {'id':'slow_audio','label':'Slower audio','effect':'Replay the same Swedish at a slower rate; record help used.'},
 {'id':'replay','label':'Replay audio','effect':'Listen again; record replay count.'},
 {'id':'translation','label':'English help','effect':'Shows the meaning; this limits independent comprehension evidence.'},
 {'id':'transcript','label':'Show transcript','effect':'Visible text means this turn cannot establish listening alone.'},
 {'id':'typed_fallback','label':'Type instead','effect':'Continue in chat when voice is unavailable; does not count as spoken evidence.'},
 {'id':'retry','label':'Try again','effect':'Keep the first attempt and help record; save the retry separately.'}
]

scenarios = [
 {
  'id':'cafe_request','level':'basic','title':'Your first café request','title_sv':'En kaffe, tack',
  'description':'Ask for something you would actually like. One sentence is enough to start.',
  'goal':'Make one clear request and understand a useful part of the reply.',
  'character':{'name':'Alex','role':'Café worker','persona':'Friendly, patient and brief. Treat the learner as an adult.'},
  'opening_sv':'Hej! Vad vill du ha?','opening_en':'Hi! What would you like?',
  'context_prompt':'What would you like to order, and why does this small moment matter? You can keep the reason private or use a fictional one.',
  'feeling_options':['curious','a little nervous','ready for a break','prefer not to say'],
  'estimated_minutes':3,'min_turns':1,'max_turns':5,
  'objectives':['Ask for one drink or item.','Respond to a simple choice or ask for repetition.','Read a short collection note and write a message.'],
  'phrases':[
   {'id':'cafe_would_like','sv':'Jag skulle vilja ha en kaffe, tack.','en':'I would like a coffee, please.','usage':'A polite request; replace kaffe with te.'},
   {'id':'cafe_takeaway','sv':'Att ta med, tack.','en':'To take away, please.','usage':'Answer when asked whether you will stay.'},
   {'id':'repeat','sv':'Kan du säga det igen, tack?','en':'Could you say that again, please?','usage':'Ask for repetition instead of guessing.'},
   {'id':'cafe_price','sv':'Vad kostar det?','en':'How much does it cost?','usage':'Ask about the price.'}
  ],
  'dialogue':{'system_instructions':'Speak simple Swedish as Alex. Ask one short question at a time. Accept an understandable single-sentence request without demanding grammatical perfection. Offer coffee, tea or water; prices are fictional. Ask stay/takeaway only after acknowledging the request. Do not reveal listening-task answers or give grades. Feedback belongs after the scene.', 'beats':['Invite one order.','Acknowledge the actual item and ask: Vill du sitta här eller ta med?','Confirm the learner’s choice and close warmly.'], 'completion':'Finish once a request is understandable and its useful reply has been offered; allow the learner to stop after one sentence.'},
  'listening':{'prompt_sv':'Ditt te är klart. Du kan hämta det vid dörren.','question_en':'Where should you collect the tea? Listen before revealing the text.','answer_ideas_en':['By the door.'], 'delivery':'Play audio with source text hidden until the answer is submitted. The item is deliberately different from the reading task.'},
  'reading':{'text_sv':'Ditt kaffe är klart. Hämta det vid kassan. Tack!','question_en':'Where should you collect the coffee?','answer_ideas_en':['At the till / checkout.']},
  'writing':{'prompt_en':'Write a short message to a friend: say what you ordered and where you are waiting. One or two sentences is enough.','prompt_sv':'Skriv till en vän: Vad beställde du? Var väntar du?','starter_sv':'Jag beställde … Jag väntar …','extension_en':'For current course A practice, copy the collection place from the note. Keep this separate from composing a message.'},
  'recall':{'prompt_en':'Later, without looking at your card, ask for your favourite drink. Then reveal the phrase and compare.','prompt_sv':'Be om din favoritdryck utan att titta på frasen.','transfer_en':'At a shop, ask for a bag using a request phrase from the café.','transfer_sv':'Jag skulle vilja ha en påse, tack.','suggested_delay_hours':24},
  'coaching':{'focus':'Whether the request communicates the intended item.','example_en':'Your request named the drink. If you want a polite ending, add tack. Try once more in your own words.','retry_en':'Change the drink or choose takeaway.'}
 },
 {
  'id':'neighbour_favour','level':'medium','title':'Ask a neighbour for a favour','title_sv':'Kan du hjälpa mig?',
  'description':'You will be away and need someone to water one plant. Explain the need and agree a workable plan.',
  'goal':'Explain a need, take turns, respond to another option and confirm the details.',
  'character':{'name':'Samira','role':'Neighbour','persona':'Kind but has her own schedule. Can help on Sunday, not Saturday.'},
  'opening_sv':'Hej! Du ville fråga mig om något?','opening_en':'Hi! You wanted to ask me something?',
  'context_prompt':'Choose a real or fictional reason for being away. What would make asking for help feel worthwhile?',
  'feeling_options':['awkward asking','grateful','hopeful','prefer not to say'],
  'estimated_minutes':6,'min_turns':4,'max_turns':10,
  'objectives':['Explain the favour and a reason.','Respond when Saturday is not possible.','Ask one practical follow-up.','Confirm the plan by message.'],
  'phrases':[
   {'id':'favour_request','sv':'Skulle du kunna vattna min växt?','en':'Could you water my plant?','usage':'Ask a neighbour for a small favour.'},
   {'id':'favour_reason','sv':'Jag ska resa bort i helgen.','en':'I am going away this weekend.','usage':'Give a reason without private details.'},
   {'id':'favour_alternative','sv':'Skulle söndag passa bättre?','en':'Would Sunday work better?','usage':'Offer another time.'},
   {'id':'favour_key','sv':'När kan jag lämna nyckeln?','en':'When can I leave the key?','usage':'Ask a practical follow-up in the fictional scene.'},
   {'id':'favour_thanks','sv':'Tack, det betyder mycket för mig.','en':'Thank you, that means a lot to me.','usage':'Express appreciation if it fits your meaning.'}
  ],
  'dialogue':{'system_instructions':'Speak Swedish as Samira. Respond to the learner’s actual request. Explain that Saturday is unavailable; Sunday is possible. Ask one practical question about the plant or key. Let the learner negotiate, decline, or suggest another safe fictional arrangement. Do not pretend that a real favour or key exchange has been arranged. Keep replies to one or two short sentences.', 'beats':['Invite the request and hear the reason.','Say Saturday is unavailable and ask whether another day works.','Discuss Sunday and one practical detail.','Ask the learner to confirm the agreed plan.','Close with a friendly acknowledgement.'], 'completion':'The learner has had an opportunity to explain, respond to the constraint, ask a question and confirm or politely decline.'},
  'listening':{'prompt_sv':'Jag kan hjälpa dig på söndag efter lunch, men inte på lördag. Ställ gärna växten i hallen.','question_en':'When can Samira help, and where should you put the plant? Listen before revealing text.','answer_ideas_en':['Sunday after lunch.','In the hall.'], 'delivery':'Hide source text until response. Do not infer listening from the chat transcript.'},
  'reading':{'text_sv':'Hej! Jag kan vattna växten på söndag klockan 15. Kan du lämna nyckeln på fredag efter klockan 18? Skriv gärna hur mycket vatten växten behöver. /Samira','question_en':'When does Samira ask for the key, and what other information does she need?','answer_ideas_en':['Friday after 18:00.','How much water the plant needs.']},
  'writing':{'prompt_en':'Reply to Samira. Confirm or change the key handover time, say how much water to give, and thank her. Invent the details; do not include an address or access code.','prompt_sv':'Svara Samira. Skriv när du lämnar nyckeln, hur mycket vatten växten behöver och tacka för hjälpen.','starter_sv':'Hej Samira! Jag kan … Växten behöver … Tack …'},
  'recall':{'prompt_en':'Tomorrow, ask for the same favour with a different day. Try before opening your phrases.','prompt_sv':'Be om samma tjänst en annan dag utan att titta på fraserna.','transfer_en':'Ask a colleague to swap a break time. They cannot do your first suggestion: explain why and offer another time.','transfer_sv':'Skulle du kunna byta rast med mig?','suggested_delay_hours':24},
  'coaching':{'focus':'How the learner responds to a constraint and makes details clear.','example_en':'You explained the favour. Next, check the time with a question so you both know the plan.','retry_en':'Try again: this time Sunday is unavailable, but Monday works.'}
 },
 {
  'id':'friend_problem','level':'high','title':'Talk it through with a friend','title_sv':'Hur kan jag få det att fungera?',
  'description':'You want time for Swedish practice, but your week feels crowded. Talk with a fictional friend, compare ideas and choose a small next step.',
  'goal':'Sustain a discussion for several minutes, explain reasons, compare options and adapt to a different view.',
  'character':{'name':'Robin','role':'Fictional friend','persona':'Warm, curious and practical. Offers ideas without deciding for the learner or diagnosing feelings.'},
  'opening_sv':'Hej! Du sa att det är svårt att hitta tid för svenskan. Hur ser en vanlig vecka ut för dig?','opening_en':'Hi! You said it is hard to find time for Swedish. What does a normal week look like for you?',
  'context_prompt':'Choose a real or fictional busy week. Which part would you like to change? Share only what you want to practise saying.',
  'feeling_options':['frustrated','uncertain','hopeful','prefer not to say'],
  'estimated_minutes':10,'min_turns':8,'max_turns':18,
  'objectives':['Describe the problem and what matters to you.','Give an example and explain a cause.','Suggest two possible approaches.','Ask for and respond to a different opinion.','Compare benefits and drawbacks.','Summarise a small plan with a fallback.'],
  'phrases':[
   {'id':'problem_feeling','sv':'Jag känner mig stressad när jag inte hinner öva.','en':'I feel stressed when I do not have time to practise.','usage':'Use only if it matches your chosen character or feeling.'},
   {'id':'problem_reason','sv':'Det är svårt eftersom mina tider ändras varje vecka.','en':'It is difficult because my schedule changes every week.','usage':'Connect a problem and a reason.'},
   {'id':'problem_option','sv':'Ett alternativ är att öva en kort stund på bussen.','en':'One option is to practise briefly on the bus.','usage':'Introduce an option; it is fine to reject it.'},
   {'id':'problem_balance','sv':'Fördelen är att … men nackdelen är att …','en':'The advantage is that … but the disadvantage is that …','usage':'Compare consequences.'},
   {'id':'problem_disagree','sv':'Jag förstår hur du menar, men det passar inte riktigt för mig.','en':'I see what you mean, but that does not quite work for me.','usage':'Disagree and then explain your reason.'},
   {'id':'problem_opinion','sv':'Vad tycker du skulle fungera bäst?','en':'What do you think would work best?','usage':'Invite the other person’s view.'},
   {'id':'problem_plan','sv':'Jag tänker prova … Om det inte fungerar kan jag …','en':'I plan to try … If it does not work, I can …','usage':'Close with a plan and an alternative.'}
  ],
  'dialogue':{'system_instructions':'Act as fictional friend Robin, speaking natural but accessible Swedish. Sustain a several-minute discussion; do not end after two exchanges or provide all solutions at once. Ask one follow-up at a time and use the learner’s actual details. Invite an example, two ideas, comparison and a plan. Gently challenge one idea, then respect the learner’s response. Do not diagnose stress or claim to know feelings. If they choose a different ordinary problem, keep the same discussion goals. Let them end at any time.', 'beats':['Ask about the week and why the goal matters.','Ask for one concrete example.','Explore the main obstacle.','Invite the learner’s first idea.','Offer one different option and ask their opinion.','Ask for an advantage and a drawback.','Gently challenge one assumption and invite a response.','Ask what small step they will try and when.','Ask for a fallback if the plan fails.','Invite a short summary and close.'], 'completion':'A discussion opportunity of roughly 4–7 speaking minutes, with reasons, comparison and a chosen next step. Duration and turn count are practice targets, never language scores.'},
  'listening':{'prompt_sv':'Vi kan öva tillsammans på tisdag i tio minuter. På torsdag arbetar jag sent. Om tisdag inte passar kan vi skicka korta röstmeddelanden till varandra.','question_en':'What first plan and fallback does Robin suggest? Which day is difficult?','answer_ideas_en':['Practise together for ten minutes on Tuesday.','Exchange short voice messages if Tuesday does not work.','Thursday is difficult because Robin works late.'], 'delivery':'Play with text hidden; asking for a replay is allowed and recorded.'},
  'reading':{'text_sv':'Hej! Jag tänkte på vårt samtal. En kort stund på bussen kan fungera, men det är svårt att prata när andra sitter nära. Vi kan i stället läsa en kort text var för sig och prata om den på söndag. Om veckan blir för full räcker ett kort meddelande. Vad vill du prova först? /Robin','question_en':'Why might the bus idea be difficult, and what alternative and fallback does Robin offer?','answer_ideas_en':['Talking may be difficult near other passengers.','Read separately and discuss on Sunday.','Send a short message if the week is too full.']},
  'writing':{'prompt_en':'Write Robin a connected reply. Explain your choice, compare it with one alternative, and say when you will try it and what you will do if it fails. Aim for 5–8 sentences if comfortable; length is not a score.','prompt_sv':'Skriv till Robin. Förklara ditt val, jämför med ett annat förslag och beskriv din plan och ett alternativ om planen inte fungerar.','starter_sv':'Hej Robin! Jag vill prova … eftersom … Ett annat alternativ är … Om …'},
  'recall':{'prompt_en':'In two days, explain your plan aloud without your notes. Then say what you would change if you had half as much time.','prompt_sv':'Förklara din plan utan anteckningar. Vad ändrar du om du har mindre tid?','transfer_en':'A friend wants to plan an inexpensive weekend together. Compare two activities, respond to a different opinion and agree on a plan and backup.','transfer_sv':'Fördelen med … är att … men vi skulle också kunna …','suggested_delay_hours':48},
  'coaching':{'focus':'Reasons, connected ideas, responses to the partner and a workable summary; not a global fluency grade.','example_en':'You gave a reason for your first idea. Try comparing it with the other option, then ask Robin for a view.','retry_en':'Keep your preferred plan, but respond to a friend who thinks it takes too much time.'}
 }
]

def add_link(scene, framework, course, domain, activity, limitation):
    prefix = 'old' if framework == OLD else 'new'
    scene['criterion_links'].append({'framework_id':framework,'criterion_id':f'{prefix}_{course}_{domain}','activity':activity,'coverage':'partial','limitation':limitation})

for scene in scenarios:
    scene['supports'] = common_supports
    scene['criterion_links'] = []
    scene['evidence_note'] = 'Completing this activity records practice only. A course link is a partial opportunity, not proof that a criterion is met.'
    scene['original_material'] = True
    if scene['level'] == 'basic':
        for course in ['A','B']:
            for domain,activity in [('spoken_interaction','dialogue'),('listening','listening'),('reading','reading')]:
                add_link(scene,OLD,course,domain,activity,'One concrete request or short message only; wider everyday comprehension and interaction remain unassessed.')
        add_link(scene,OLD,'B','writing','writing','Only a short personal message; not the wider range or consistency of writing.')
        add_link(scene,OLD,'A','writing','writing_copy_extension','Only the explicitly labelled copying extension; composing a new café message is not a substitute for the current A copying criterion.')
        new_targets=['1A','1B','2B']
    elif scene['level'] == 'medium':
        for course in ['B','C']:
            for domain,activity in [('spoken_interaction','dialogue'),('listening','listening'),('reading','reading'),('writing','writing')]:
                add_link(scene,OLD,course,domain,activity,'One informal favour; no broad coverage of settings, text types or repeated independent performance.')
        new_targets=['1B','2B','1C','2C','3C']
    else:
        for course in ['C','D']:
            for domain,activity in [('spoken_interaction','dialogue'),('spoken_production','dialogue_summary'),('listening','listening'),('reading','reading'),('writing','writing')]:
                add_link(scene,OLD,course,domain,activity,'One informal familiar problem; excludes formal settings, broad text types and audio-based fluency or pronunciation judgements.')
        new_targets=['1C','2C','3C','1D','2D','3D']
    for course in new_targets:
        for domain,activity in [('speaking_and_conversation','dialogue'),('listening','listening'),('reading','reading'),('writing','writing')]:
            add_link(scene,NEW,course,domain,activity,'Samples a single familiar situation. Oral criterion combines speaking and conversation; neither a typed turn nor one brief exchange demonstrates the full criterion.')

for name,data in [('curriculum.json',curriculum),('scenarios.json',{'schema_version':'1.0','content_version':'2026-11-01.1','language':'sv-SE','help_language':'en','scenarios':scenarios})]:
    (ROOT / name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Wrote {len(criteria)} criterion summaries and {len(scenarios)} original scenarios.')
