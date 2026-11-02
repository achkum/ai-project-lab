"""Explicit offer-scoped meanings, independent of illustrative reply inventories.

Each value is authored from the offered question, never ANSWERS[question][0].
Specific explanations and alternatives may support a refusal, but are not claims
made by the canonical predicate or by the character's negative response.
"""

# Question -> minimal Swedish refusal, English meaning, neutral character reply.
REFUSALS = {
'Passar bordet vid fönstret?':('Jag säger nej till bordet vid fönstret.','I am saying no to the table by the window.','Okej, då bestämmer vi inte det bordet.'),
'Passar det att hämta det vid disken?':('Jag säger nej till att hämta kaffet vid disken.','I am saying no to collecting the coffee at the counter.','Okej, då är hämtningen vid disken inte bestämd.'),
'Vill du betala med kort?':('Jag betalar inte med kort.','I will not pay by card.','Okej, då är betalningssättet inte bestämt.'),
'Vill du ha det i en ny kopp?':('Jag tackar nej till en ny kopp.','I am saying no to a new cup.','Okej, då tar jag ingen ny kopp.'),
'Kan du gå dit själv?':('Jag säger nej till att gå dit själv.','I am saying no to going there on my own.','Okej, då räknar jag inte med att du går dit själv.'),
'Går det bra med den här förpackningen?':('Jag säger nej till den här förpackningen.','I am saying no to this packaging.','Okej, då använder vi inte den här förpackningen.'),
'Vill du ta en förpackning?':('Jag tackar nej till den erbjudna förpackningen.','I am saying no to the offered carton.','Okej, då lägger jag inte fram den förpackningen åt dig.'),
'Passar det att komma efter lunch?':('Jag säger nej till att komma efter lunch.','I am saying no to coming after lunch.','Okej, då är ingen tid efter lunch bestämd.'),
'Vill du att jag visar hållplatsen på kartan?':('Jag tackar nej till att få hållplatsen visad på kartan.','I am saying no to having the stop shown on the map.','Okej, då visar jag inte hållplatsen på kartan.'),
'Vill du att jag visar den på kartan?':('Jag tackar nej till att få hållplatsen visad på kartan.','I am saying no to having the stop shown on the map.','Okej, då visar jag inte hållplatsen på kartan.'),
'Vill du se biljetten på skärmen?':('Jag tackar nej till att se biljetten på skärmen.','I am saying no to seeing the ticket on the screen.','Okej, då visar jag inte biljetten på skärmen.'),
'Vill du gå på här?':('Jag säger nej till att gå på bussen här.','I am saying no to boarding the bus here.','Okej, då räknar jag inte med att du går på här.'),
'Vill du gå dit?':('Jag säger nej till att gå till den hållplatsen.','I am saying no to going to that stop.','Okej, då är det inte bestämt att du går dit.'),
'Vill du låna den?':('Jag tackar nej till att låna den här boken.','I am saying no to borrowing this book.','Okej, då lånar vi inte ut den här boken till dig.'),
'Vill du ta med lappen?':('Jag tackar nej till att ta med lappen.','I am saying no to taking the note with me.','Okej, då behåller jag lappen här. Omlånet gäller ändå.'),
'Vill du skriva av det?':('Jag säger nej till att skriva av datumet.','I am saying no to copying down the date.','Okej, då räknar jag inte med att du skriver av datumet.'),
'Går det bra att skriva ut en sida?':('Jag säger nej till förslaget att skriva ut en sida.','I am saying no to the proposed one-page printout.','Okej, då gör jag ingen utskrift enligt det förslaget.'),
'Vill du prova den nu?':('Jag tackar nej till att prova tröjan nu.','I am saying no to trying the jumper on now.','Okej, då blir det ingen provning nu.'),
'Vill du vänta här?':('Jag säger nej till att vänta här.','I am saying no to waiting here.','Okej, då räknar jag inte med att du väntar här.'),
'Vill du följa med till nästa hylla?':('Jag tackar nej till att följa med till nästa hylla.','I am saying no to going over to the next shelf.','Okej, då går vi inte till nästa hylla tillsammans.'),
'Kan du vänta här?':('Jag säger nej till att vänta här.','I am saying no to waiting here.','Okej, då är väntplatsen inte bestämd.'),
'Kan du vänta utanför rum två?':('Jag säger nej till att vänta utanför rum två.','I am saying no to waiting outside room two.','Okej, då är väntplatsen inte bestämd.'),
'Stämmer det att namnet är Kim?':('Nej, jag bekräftar inte namnet som Kim.','No, I am not confirming the name as Kim.','Okej, då är namnet inte bekräftat. Jag ändrar inte namnet på egen hand.'),
'Vill du ta hissen?':('Jag tackar nej till att ta hissen.','I am saying no to taking the lift.','Okej, då räknar jag inte med att du tar hissen.'),
'Vill du sitta på stolen vid dörren?':('Jag tackar nej till stolen vid dörren.','I am saying no to the chair by the door.','Okej, då är stolen vid dörren inte bestämd som din plats.'),
'Vill du ha den lilla storleken?':('Jag tackar nej till den lilla kartongen.','I am saying no to the small box.','Okej, då ger jag dig inte den lilla kartongen.'),
'Går det bra att lägga det på vågen?':('Jag säger nej till att lägga paketet på vågen.','I am saying no to putting the parcel on the scales.','Okej, då lägger vi inte paketet på vågen.'),
'Vill du prova det?':('Jag säger nej till att leta efter koden i meddelandet.','I am saying no to looking for the code in the message.','Okej, då går vi inte vidare med att leta i meddelandet.'),
'Passar det att komma före stängning?':('Jag säger nej till att komma före stängning.','I am saying no to coming before closing time.','Okej, då är ingen tid före stängning bestämd.'),
'Kan du lämna den före klockan sju?':('Jag säger nej till att lämna tillbaka bollen före sju.','I am saying no to returning the ball before seven.','Okej, då är återlämningstiden inte bestämd.'),
'Passar nästa lördag?':('Jag säger nej till nästa lördag.','I am saying no to next Saturday.','Okej, då bokar jag ingen ny plats nästa lördag.'),
'Stämmer det?':('Nej, jag bekräftar inte avbokningen.','No, I am not confirming the cancellation.','Okej, då avbokar jag inte platsen.'),
'Kan du säga till om det fortfarande hörs för mycket?':('Jag säger nej till att lova att säga till om ljudet.','I am not agreeing to report whether the noise is still too loud.','Okej, du behöver inte återkomma om ljudet. Jag sänker volymen som jag sa.'),
'Kan du säga till om något annat stör?':('Jag säger nej till att lova att säga till om något stör.','I am not agreeing to report anything else that bothers me.','Okej, du behöver inte återkomma om det. Jag använder hörlurar som jag sa.'),
'Vill du att vi frågar tillsammans?':('Jag säger nej till att vi frågar tillsammans.','I am saying no to asking together.','Okej, då frågar vi inte tillsammans. Bytet är fortfarande inte godkänt.'),
'Vill du följa med?':('Jag tackar nej till att följa med.','I am saying no to coming with you.','Okej, då räknar jag inte med att du följer med.'),
'Vill du öppna tabellen?':('Jag säger nej till att öppna tabellen nu.','I am saying no to opening the table now.','Okej, då öppnar vi inte tabellen nu.'),
'Vill du skicka frågorna först?':('Jag säger nej till att skicka frågorna i förväg.','I am saying no to sending the questions in advance.','Okej, då räknar jag inte med frågor i förväg.'),
'Kan vi stämma av klockan två?':('Jag säger nej till en avstämning klockan två.','I am saying no to checking in at two.','Okej, då är ingen avstämning klockan två bestämd.'),
'Passar det att vi ringer i eftermiddag?':('Jag säger nej till ett samtal i eftermiddag.','I am saying no to a call this afternoon.','Okej, då bokar vi inget samtal i eftermiddag.'),
'Passar fredag förmiddag?':('Jag säger nej till fredag förmiddag.','I am saying no to Friday morning.','Okej, då bokar vi inte fredag förmiddag.'),
'Kan du möta teknikern vid porten?':('Jag säger nej till att möta teknikern vid porten.','I am saying no to meeting the technician at the entrance.','Okej, då är mottagandet vid porten inte ordnat.'),
'Vill du att vi börjar där?':('Jag säger nej till att börja med att kontrollera bytet.','I am saying no to starting by checking the exchange.','Okej, då börjar vi inte kontrollera bytet enligt förslaget.'),
'Vill du ha instruktionerna skriftligt?':('Jag tackar nej till skriftliga instruktioner.','I am saying no to written instructions.','Okej, då ger jag inte instruktionerna skriftligt.'),
'Går det bra med ett skriftligt svar?':('Jag säger nej till ett skriftligt svar.','I am saying no to a written reply.','Okej, då är sättet att ge dig besked inte bestämt.'),
'Går det bra att vänta till i morgon?':('Jag säger nej till att vänta på besked till i morgon.','I am saying no to waiting until tomorrow for an answer.','Okej, då är morgondagens besked inte en överenskommen lösning.'),
'Vill du sedan be om skriftlig bekräftelse?':('Jag säger nej till att be om skriftlig bekräftelse.','I am saying no to asking for written confirmation.','Okej, då bestämmer vi inte att du ska be om skriftlig bekräftelse.'),
'Kan du skicka en fråga före nästa lektion?':('Jag säger nej till att skicka en fråga före nästa lektion.','I am saying no to sending a question before the next lesson.','Okej, då räknar jag inte med en fråga före nästa lektion.'),
'Vill du vara kund först?':('Jag tackar nej till att vara kund först.','I am saying no to being the customer first.','Okej, då är det inte bestämt att du börjar som kund.'),
'Vill du börja med att fråga?':('Jag tackar nej till att ställa den första frågan.','I am saying no to asking the first question.','Okej, då är det inte bestämt att du ställer den första frågan.'),
'Passar klockan sex?':('Jag säger nej till klockan sex.','I am saying no to six o’clock.','Okej, då är klockan sex inte bestämt.'),
'Kan du ta med bröd?':('Jag säger nej till att ta med bröd.','I am saying no to bringing bread.','Okej, då räknar jag inte med att du tar med bröd.'),
'Kan du ta med sallad?':('Jag säger nej till att ta med sallad.','I am saying no to bringing salad.','Okej, då räknar jag inte med att du tar med sallad.'),
'Känns det rimligt?':('Jag säger nej till det föreslagna maxbeloppet.','I am saying no to the proposed spending limit.','Okej, då är det maxbeloppet inte överenskommet.'),
'Vill du att vi frågar gruppen?':('Jag säger nej till att vi frågar gruppen.','I am saying no to asking the group.','Okej, då frågar vi inte gruppen enligt det förslaget.'),
'Vill du att vi stämmer av på fredag?':('Jag säger nej till en avstämning på fredag.','I am saying no to checking in on Friday.','Okej, då är ingen avstämning på fredag bestämd.'),
'Vill du berätta i morgon hur det gick?':('Jag säger nej till att berätta i morgon hur det gick.','I am saying no to reporting back tomorrow.','Okej, då räknar jag inte med en återkoppling i morgon.'),
'Vill du prova fram till söndag?':('Jag säger nej till att prova fram till söndag.','I am saying no to trying it until Sunday.','Okej, då är ingen provperiod fram till söndag bestämd.'),
'Vill du prova fram till söndag och sedan utvärdera?':('Jag säger nej till förslaget att prova till söndag och sedan utvärdera.','I am saying no to trying it until Sunday and then reviewing it.','Okej, då är den provperioden och utvärderingen inte bestämda.'),
'Vill du att vi provar i två veckor?':('Jag säger nej till en provperiod på två veckor.','I am saying no to a two-week trial.','Okej, då är ingen provperiod på två veckor bestämd.'),
'Vill du prova den regeln nästa vecka?':('Jag säger nej till att prova den regeln nästa vecka.','I am saying no to trying that rule next week.','Okej, då är det inte bestämt att vi provar regeln nästa vecka.'),
'Vill du prova nästa vecka?':('Jag säger nej till att prova nästa vecka.','I am saying no to trying it next week.','Okej, då är ingen provperiod nästa vecka bestämd.'),
'Vill du prova i tre dagar?':('Jag säger nej till en provperiod på tre dagar.','I am saying no to a three-day trial.','Okej, då är ingen provperiod på tre dagar bestämd.'),
'Vill du att vi delar de två uppgifterna?':('Jag säger nej till att vi delar de två uppgifterna mellan oss.','I am saying no to sharing the two tasks between us.','Okej, då är den fördelningen av uppgifterna inte överenskommen.'),
'Vill du att vi delar de tre frågorna?':('Jag säger nej till att vi delar de tre frågorna mellan oss.','I am saying no to sharing the three questions between us.','Okej, då är den fördelningen av frågorna inte överenskommen.'),
'Vill du att vi skriver in bytet i planen?':('Jag säger nej till att skriva in avlösningen i planen.','I am saying no to putting the handover in the plan.','Okej, då skriver vi inte in avlösningen i planen.'),
'Vill du ha texten från mig senast onsdag?':('Jag säger nej till den föreslagna tidsgränsen för texten, senast onsdag.','I am saying no to the proposed Wednesday deadline for the text.','Okej, då är senast onsdag inte en överenskommen tidsgräns.'),
'Vill du att svaren blir frivilliga?':('Jag säger nej till förslaget att svaren ska vara frivilliga.','I am saying no to the proposal that answering should be voluntary.','Okej, då har vi ingen gemensam överenskommelse om den delen av enkäten.'),
'Vill du att vi sammanfattar svaren utan namn?':('Jag säger nej till att sammanfatta svaren utan namn.','I am saying no to summarising the answers without names.','Okej, då är det sättet att sammanfatta svaren inte överenskommet.'),
'Vill du skriva ner de tre frågorna?':('Jag säger nej till att skriva ner de tre frågorna.','I am saying no to writing down the three questions.','Okej, då bestämmer vi inte att du skriver ner frågorna.'),
'Vill du bestämma en dag för uppföljning?':('Jag säger nej till att bestämma en dag för uppföljning.','I am saying no to choosing a day to review progress.','Okej, då är ingen dag för uppföljning bestämd.'),
'Vill du börja med en kort version?':('Jag tackar nej till att börja med en kort version.','I am saying no to starting with a short version.','Okej, då är det inte bestämt att du börjar med en kort version.'),
'Vill du sedan berätta utan hela meningar framför dig?':('Jag tackar nej till att berätta utan hela meningar framför mig.','I am saying no to speaking without full sentences in front of me.','Okej, då är det inte bestämt att du berättar utan hela meningar framför dig.'),
'Vill du göra det före nästa vecka?':('Jag säger nej till att göra provresan före nästa vecka.','I am saying no to making the trial journey before next week.','Okej, då är ingen provresa före nästa vecka bestämd.'),
'Vill du skriva frågan i dag?':('Jag säger nej till att skriva frågan i dag.','I am saying no to writing the question today.','Okej, då är det inte bestämt att du skriver frågan i dag.')
}

# The short questions below are resolved from the actual predecessor offer, not
# from an earlier learner plan or from an illustrative acceptance/refusal.
CONTEXTUAL = {
('clothes_m2','confirm_wait'):('Jag säger nej till att vänta vid spegeln.','I am saying no to waiting by the mirror.','Okej, då är det inte bestämt att du väntar vid spegeln.'),
('clothes_m2','confirm_return'):('Jag tackar nej till att du lägger undan byxorna.','I am saying no to having the trousers put aside.','Okej, jag lägger inte undan byxorna. Du är välkommen tillbaka.'),
('parcel_m1','confirm_phone'):('Jag säger nej till att visa koden på telefonens skärm.','I am saying no to showing the code on my phone screen.','Okej, då visas inte koden på telefonens skärm.'),
('parcel_m1','confirm_paper'):('Jag säger nej till att visa lappen med koden.','I am saying no to showing the note with the code.','Okej, då visar du inte lappen med koden.'),
('community_centre_m2','confirm_hour'):('Jag säger nej till att lämna tillbaka bollen om en timme.','I am saying no to returning the ball in an hour.','Okej, då är återlämning om en timme inte bestämd.'),
('neighbours_m1','confirm_friday'):('Jag säger nej till att ses på fredag efter sex.','I am saying no to meeting on Friday after six.','Okej, då är inget möte på fredag efter sex bestämt.'),
('neighbours_m1','confirm_saturday'):('Jag säger nej till att ses på lördag morgon före nio.','I am saying no to meeting on Saturday morning before nine.','Okej, då är inget möte på lördag morgon före nio bestämt.'),
('neighbours_m2','confirm_tonight'):('Jag säger nej till att komma efter sju i kväll.','I am saying no to coming after seven this evening.','Okej, då är inget besök efter sju i kväll bestämt.'),
('neighbours_m2','confirm_tomorrow'):('Jag säger nej till att komma före lunch i morgon.','I am saying no to coming before lunch tomorrow.','Okej, då är inget besök före lunch i morgon bestämt.'),
('social_plans_m1','confirm_nextweek'):('Jag säger nej till att höras på måndag för att bestämma en tid.','I am saying no to getting in touch on Monday to arrange a time.','Okej, då är det inte bestämt att vi hörs på måndag.'),
('community_centre_m1','confirm_monday'):('Jag säger nej till att komma på måndag.','I am saying no to coming on Monday.','Okej, då räknar vi inte med dig på måndag.'),
('community_centre_m1','confirm_thursday'):('Jag säger nej till att komma på torsdag.','I am saying no to coming on Thursday.','Okej, då räknar vi inte med dig på torsdag.'),
('housing_m1','confirm_tuesday'):('Jag säger nej till att vara hemma på tisdag förmiddag.','I am saying no to being at home on Tuesday morning.','Okej, då är det inte bestämt att du är hemma på tisdag förmiddag.'),
('housing_m1','confirm_wednesday'):('Jag säger nej till att vara hemma på onsdag eftermiddag.','I am saying no to being at home on Wednesday afternoon.','Okej, då är det inte bestämt att du är hemma på onsdag eftermiddag.'),
('course_planning_m3','confirm_morning'):('Jag säger nej till att vi undersöker om det finns plats i morgongruppen.','I am saying no to checking availability in the morning group.','Okej, då frågar vi inte om plats i morgongruppen enligt förslaget.'),
('course_planning_m3','confirm_afternoon'):('Jag säger nej till att vi undersöker om det finns plats i eftermiddagsgruppen.','I am saying no to checking availability in the afternoon group.','Okej, då frågar vi inte om plats i eftermiddagsgruppen enligt förslaget.')
}

# Four old affirmative labels inserted a handover promise into a question about
# whether a meeting time works. Preserve the earlier context, but scope this
# predicate to the offered time only.
AFFIRMATIVE_CORRECTIONS={
('neighbours_m1','confirm_friday'):('Det passar att ses på fredag efter sex.','Meeting on Friday after six works for me.'),
('neighbours_m1','confirm_saturday'):('Det passar att ses på lördag morgon före nio.','Meeting on Saturday morning before nine works for me.'),
('neighbours_m2','confirm_tonight'):('Det passar att komma efter sju i kväll.','Coming after seven this evening works for me.'),
('neighbours_m2','confirm_tomorrow'):('Det passar att komma före lunch i morgon.','Coming before lunch tomorrow works for me.')
}

def apply_refusal_contract(mission):
    key=mission['id'][4:]
    for step in mission['steps']:
        if not step['id'].startswith('confirm_'):continue
        node=(key,step['id'])
        source='contextual_offer' if node in CONTEXTUAL else 'explicit_question_scope'
        sv,en,reply=CONTEXTUAL[node] if node in CONTEXTUAL else REFUSALS[step['prompt_sv']]
        predecessors=[i['reply_sv'] for s in mission['steps'] for i in s['intents'] if i['next_step']==step['id']]
        assert len(predecessors)==1,node
        step['current_offer_sv']=predecessors[0]
        verification=step['prompt_sv']=='Stämmer det att namnet är Kim?'
        step['expected_act']='verify_the_stated_name' if verification else 'respond_to_the_current_offer'
        step['speech_act_policy']={
            'scope':'Interpret the actual current offer and the learner response together.',
            'surface_form_rule':'A question, an uncertainty word, or an initial yes/no token is not a class by itself.',
            'unresolved_case':'If the response does not establish a permitted meaning, request clarification without calling the Swedish incorrect.',
            'additional_content':'An explicit current-offer answer can remain valid with harmless extra content. Additional text must be checked for contradiction or a change of scope, not rejected automatically.',
            'refusal_scope':'A denial about an unrelated object is not automatically a refusal of this offer. Interpret whether an initial yes/no independently answers the offer or belongs only to a correction or different topic.'
        }
        for intent in step['intents']:
            if intent['id']=='decline':
                intent['meaning_sv']=sv;intent['meaning_en']=en;intent['reply_sv']=reply
                intent['feedback_en']='Your meaning: '+en
                intent['expected_act']='deny_the_stated_name_or_explicitly_decline_verification' if verification else 'explicitly_refuse_the_current_offer'
                intent['semantic_contract']={
                    'version':'2026-11-02.9','derivation':'Authored from the current offer, not selected from response examples.',
                    'predicate_kind':'explicit_denial_or_explicit_refusal_to_verify' if verification else 'explicit_scoped_refusal',
                    'scope_source':source,'offer_sv':predecessors[0],'question_sv':step['prompt_sv'],
                    'required_meaning_sv':sv,'required_meaning_en':en,
                    'permitted_meanings':(['Explicitly deny that the stated name is correct.','Explicitly refuse to verify the stated name.'] if verification else ['Explicitly decline the offered action, arrangement, item or condition.','Express an inability or an incompatible preference that clearly refuses this offer.','Clearly decide to defer the offered action or commitment for now, including asking for prerequisite discussion first. This does not assert a later plan.']),
                    'not_entailed':['A particular reason for the refusal.','A specific alternative action, item, place or time.','An intention to do it later.','Cancellation of earlier agreements outside this offer.'],
                    'uncertainty_boundary':'Not knowing whether the name is correct is not itself a denial or a refusal to verify it.' if verification else 'Uncertainty alone does not establish refusal; the complete response must express a permitted meaning.',
                    'example_inventory_role':'Illustrative subtypes only. No shared alternative or reason is inferred from the examples.'
                }
                if node in [('cafe_m1','confirm_takeaway'),('transport_m3','confirm_direct')]:
                    intent['semantic_contract']['assistance_boundary']='A request for assistance alone need not refuse the offered collection or journey. Neither offer explicitly requires acting alone. A separate clear refusal or inability scoped to the actual offer may establish the negative meaning.'
            else:
                intent['expected_act']='affirm_the_stated_name' if verification else 'accept_the_current_offer'
                if node in AFFIRMATIVE_CORRECTIONS:
                    intent['meaning_sv'],intent['meaning_en']=AFFIRMATIVE_CORRECTIONS[node]
                    intent['feedback_en']='Your meaning: '+intent['meaning_en']
    # These tasks permit hypotheses/questions as successful contributions.
    if key=='community_project_m3':
        step=next(s for s in mission['steps'] if s['id']=='detail_2')
        step['expected_act']='offer_a_plausible_hypothesis_about_low_attendance'
        step['speech_act_policy']={'uncertainty_allowed':True,'questions_allowed_when_they_propose_a_relevant_hypothesis':True,'meaning':'Propose the event time as a possible explanation, without claiming that it is established.','surface_form_rule':'Do not reject a hypothesis merely because it says perhaps, might, or asks whether a possible cause fits.'}
        for intent in step['intents']:intent['expected_act']=step['expected_act']
    if key=='course_planning_m3':
        step=next(s for s in mission['steps'] if s['id']=='choice')
        step['expected_act']='request_information_about_one_offered_course_group'
        step['speech_act_policy']={'questions_allowed':True,'uncertainty_allowed_when_asking_for_information':True,'meaning':'Ask about the morning group or the afternoon group. A definite enrolment decision is not required.','surface_form_rule':'Do not reject a request for group information merely because it is a question or expresses missing knowledge.'}
        for intent in step['intents']:
            intent['expected_act']='request_information_about_the_morning_group' if intent['id']=='choose_morning' else 'request_information_about_the_afternoon_group'
    if mission['level']=='high':
        step=next(s for s in mission['steps'] if s['id']=='detail_5')
        step['expected_act']='request_the_partners_view_or_feedback'
        step['speech_act_policy']={'questions_allowed':True,'meaning':'Invite the partner’s view or feedback about the issue specified in this step.','surface_form_rule':'A question is an expected contribution here, not automatically UNKNOWN.'}
        for intent in step['intents']:intent['expected_act']=step['expected_act']
    if key in ('next_steps_m1','next_steps_m3'):
        step=next(s for s in mission['steps'] if s['id']=='choice')
        inquiry_id='choose_class' if key=='next_steps_m1' else 'choose_digital'
        for intent in step['intents']:
            if intent['id']==inquiry_id:
                intent['expected_act']='inquire_about_a_trial_lesson' if key=='next_steps_m1' else 'inquire_about_a_digital_participation_option'
                intent['speech_act_policy']={'questions_allowed':True,'uncertainty_allowed_when_seeking_information':True,'meaning':'A relevant information question can itself perform the offered investigation. No commitment to enrol or participate is required.','scope_conflict':'If the utterance also explicitly denies that it is performing or selecting this investigation, adjudicate the complete scope; do not force a class from a question mark or a named option.'}
            else:
                intent['expected_act']='choose_to_try_an_independent_study_plan' if key=='next_steps_m1' else 'choose_to_try_the_journey'
    if key=='shared_home_m2':
        step=next(s for s in mission['steps'] if s['id']=='choice')
        old=step['prompt_sv']
        new=old.replace('skicka ett meddelande dagen före','meddela varandra dagen före')
        assert new!=old
        step['prompt_sv']=new
        for previous in mission['steps']:
            for intent in previous['intents']:
                if intent['next_step']=='choice':intent['reply_sv']=intent['reply_sv'].replace(old,new)
        for sid,iid in [('detail_2','detail_2_answer'),('choice','choose_message')]:
            node=next(s for s in mission['steps'] if s['id']==sid)
            intent=next(i for i in node['intents'] if i['id']==iid)
            intent['meaning_sv']='Vi meddelar varandra dagen före planerade besök.'
            intent['meaning_en']='We give each other notice the day before planned visits.'
            intent['expected_act']='propose_day_before_notice' if sid=='detail_2' else 'choose_day_before_notice'
            intent['semantic_contract']={'version':'2026-11-02.9','predicate_kind':'day_before_notification','required_meaning_en':'Give notice the day before the visit.','channel_rule':'No written channel is required. A message is an illustrative method; spoken notice or a call can express the same permitted meaning.','required_facts':['Notice is given the day before the planned visit.'],'contrast':'The other offered routine is a weekly Sunday check-in.'}
    from library_sources.example_adjudication import apply_example_adjudication
    apply_example_adjudication(mission)
