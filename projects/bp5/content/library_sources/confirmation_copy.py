"""Learner-facing English meanings. This module changes no matching rules."""

# Swedish question -> English question, intended yes meaning, intended no meaning.
QUESTIONS={
'Passar bordet vid fönstret?':('Would the table by the window suit you?','I would like to sit by the window.','I would prefer to sit somewhere else.'),
'Passar det att hämta det vid disken?':('Can you collect it at the counter?','I will collect the coffee at the counter.','I need help collecting the coffee.'),
'Vill du betala med kort?':('Would you like to pay by card?','I will pay by card.','I would prefer to pay cash.'),
'Vill du ha det i en ny kopp?':('Would you like it in a new cup?','I would like a new cup.','The same cup is fine.'),
'Kan du gå dit själv?':('Can you find your way there?','I can find it myself.','I need help finding it.'),
'Går det bra med den här förpackningen?':('Is this packaging all right?','This packaging is fine.','I would like different packaging.'),
'Vill du ta en förpackning?':('Would you like one carton?','I would like one carton.','I will wait before buying anything.'),
'Passar det att komma efter lunch?':('Can you come after lunch?','I will come after lunch.','I cannot come after lunch.'),
'Vill du att jag visar hållplatsen på kartan?':('Would you like me to show the stop on the map?','Please show me the stop on the map.','I can find the stop myself.'),
'Vill du att jag visar den på kartan?':('Would you like me to show it on the map?','Please show me the stop on the map.','I can find the stop myself.'),
'Vill du se biljetten på skärmen?':('Would you like to see the ticket on the screen?','Please show me the ticket.','You do not need to show me the screen.'),
'Vill du gå på här?':('Would you like to board here?','I will board the bus here.','I would like to wait before boarding.'),
'Vill du gå dit?':('Would you like to go there?','I will go to that stop.','I need help finding that stop.'),
'Vill du låna den?':('Would you like to borrow it?','I would like to borrow the book.','I only want to look through the book for now.'),
'Vill du ta med lappen?':('Would you like to take the note with you?','I will take the note with me.','I do not need the note.'),
'Vill du skriva av det?':('Would you like to copy it down?','I will write down the date.','I do not need to write down the date.'),
'Går det bra att skriva ut en sida?':('Is printing one page enough?','One page is enough.','I need more pages.'),
'Vill du prova den nu?':('Would you like to try it on now?','I would like to try it on now.','I would like to wait before trying it on.'),
'Går det bra?':('Does that work for you?',None,None),
'Vill du vänta här?':('Would you like to wait here?','I will wait here.','I cannot wait here.'),
'Vill du följa med till nästa hylla?':('Would you like to come over to the next shelf?','I will come with you.','I will carry on looking by myself.'),
'Kan du vänta här?':('Can you wait here?','I will wait here.','I cannot wait here.'),
'Kan du vänta utanför rum två?':('Can you wait outside room two?','I will wait outside room two.','I cannot wait outside room two.'),
'Stämmer det att namnet är Kim?':('Is Kim the correct name?','Yes, my name is Kim.','The name is wrong.'),
'Vill du ta hissen?':('Would you like to take the lift?','I would like to take the lift.','I will take the stairs.'),
'Vill du sitta på stolen vid dörren?':('Would you like to sit on the chair by the door?','I would like to sit there.','I would like to sit somewhere else.'),
'Vill du ha den lilla storleken?':('Would you like the small size?','The small box is fine.','I need a larger box.'),
'Går det bra att lägga det på vågen?':('Can you put it on the scales?','I will put the parcel on the scales.','I need to wait before weighing it.'),
'Vill du prova det?':('Would you like to try that?','I will try looking for the code in the message.','I do not want to look in the message now.'),
'Passar det att komma före stängning?':('Can you come before closing time?','I will come before closing time.','I cannot get here before closing time.'),
'Vill du komma då?':('Would you like to come then?','I will come then.','I cannot come then.'),
'Kan du lämna den före klockan sju?':('Can you return it before seven?','I will return it before seven.','I cannot return it before seven.'),
'Passar nästa lördag?':('Does next Saturday suit you?','Next Saturday works for me.','I cannot come next Saturday.'),
'Stämmer det?':('Is that correct?','Yes, that is correct.','No, that is wrong.'),
'Passar det att ses då?':('Can we meet then?',None,'That time does not work for me.'),
'Passar det?':('Does that time suit you?',None,'That time does not work for me.'),
'Kan du säga till om det fortfarande hörs för mycket?':('Can you let me know if it is still too loud?','I will let you know if the noise still bothers me.','I would prefer not to have to mention it again.'),
'Kan du säga till om något annat stör?':('Can you let me know if anything else bothers you?','I will let you know if something bothers me.','I would prefer not to have to mention it again.'),
'Vill du att vi frågar tillsammans?':('Would you like us to ask together?','We can ask together.','I would like to ask by myself.'),
'Vill du följa med?':('Would you like to come with me?','I will come with you.','I cannot come with you.'),
'Vill du öppna tabellen?':('Would you like to open the table?','I will open the table now.','I cannot open it right now.'),
'Vill du skicka frågorna först?':('Would you like to send the questions first?','I will send the questions first.','I would like to discuss the questions when we meet.'),
'Kan vi stämma av klockan två?':('Can we check in at two?','Two o’clock works for me.','I am not available at two.'),
'Kan du vara hemma då?':('Can you be at home then?','I can be at home then.','I cannot be at home then.'),
'Passar det att vi ringer i eftermiddag?':('Can we call you this afternoon?','You can call me this afternoon.','I cannot talk this afternoon.'),
'Passar fredag förmiddag?':('Does Friday morning suit you?','Friday morning works for me.','Friday morning does not work for me.'),
'Kan du möta teknikern vid porten?':('Can you meet the technician at the entrance?','I will meet the technician at the entrance.','I cannot meet the technician at the entrance.'),
'Vill du att vi börjar där?':('Would you like us to start there?','Please start by checking whether the right size is available.','I would like to wait before checking the exchange.'),
'Vill du ha instruktionerna skriftligt?':('Would you like written instructions?','I would like written instructions.','It is enough to explain it to me aloud.'),
'Går det bra med ett skriftligt svar?':('Is a written reply all right?','A written reply is fine.','I would prefer a phone call.'),
'Går det bra att vänta till i morgon?':('Can you wait until tomorrow?','I can wait until tomorrow.','I need an answer today.'),
'Vill du sedan be om skriftlig bekräftelse?':('Would you then like to ask for written confirmation?','I will ask for written confirmation.','I will wait before asking for confirmation.'),
'Kan du skicka en fråga före nästa lektion?':('Can you send a question before the next lesson?','I will send a question before the next lesson.','I will not have time before the next lesson.'),
'Vill du vara kund först?':('Would you like to be the customer first?','I would like to be the customer first.','I would like to listen first.'),
'Vill du börja med att fråga?':('Would you like to ask the first question?','I will ask the first question.','Please ask a question first.'),
'Vill du att vi undersöker det?':('Would you like us to look into that?','Please check whether there is a place available.','I would like to think about it first.'),
'Passar klockan sex?':('Does six o’clock suit you?','Six o’clock works for me.','I am not available at six.'),
'Kan du ta med bröd?':('Can you bring bread?','I will bring bread.','I cannot bring bread.'),
'Kan du ta med sallad?':('Can you bring salad?','I will bring salad.','I cannot bring salad.'),
'Känns det rimligt?':('Does that seem reasonable?','That amount seems reasonable.','That would be too expensive for me.'),
'Vill du att vi frågar gruppen?':('Would you like us to ask the group?','We can ask the group.','We should wait before asking the group.'),
'Vill du att vi stämmer av på fredag?':('Would you like us to check in on Friday?','We can talk on Friday.','I am not available on Friday.'),
'Vill du berätta i morgon hur det gick?':('Would you like to tell me tomorrow how it went?','I will tell you tomorrow how it went.','I would like to try it for a few days first.'),
'Vill du prova fram till söndag?':('Would you like to try it until Sunday?','I will try it until Sunday.','I do not want to choose an end date yet.'),
'Vill du prova fram till söndag och sedan utvärdera?':('Would you like to try it until Sunday and then see how it went?','We can try it until Sunday.','I would like to wait before deciding how long to try it.'),
'Vill du att vi provar i två veckor?':('Would you like us to try it for two weeks?','We can try it for two weeks.','Two weeks does not work for me.'),
'Vill du prova den regeln nästa vecka?':('Would you like to try that rule next week?','We can try it next week.','I would like to discuss the rule more first.'),
'Vill du prova nästa vecka?':('Would you like to try it next week?','Next week works for me.','I cannot do it next week.'),
'Vill du prova i tre dagar?':('Would you like to try it for three days?','Three days would be a good length of time.','I would like to wait before choosing how long to try it.'),
'Vill du att vi delar de två uppgifterna?':('Would you like us to share the two tasks?','We can share the tasks.','I would like to divide the tasks differently.'),
'Vill du att vi delar de tre frågorna?':('Would you like us to share the three questions?','We can share the questions.','I would like to divide the questions differently.'),
'Vill du att vi skriver in bytet i planen?':('Would you like us to include the handover in the plan?','Please include the handover in the plan.','I would like to wait before putting it in the plan.'),
'Vill du ha texten från mig senast onsdag?':('Would you like the text from me by Wednesday?','Wednesday works for receiving the text.','I need the text earlier.'),
'Vill du att svaren blir frivilliga?':('Would you like people to be free to choose whether to answer?','Answering should be voluntary.','I would like to discuss how we ask people first.'),
'Vill du att vi sammanfattar svaren utan namn?':('Would you like us to summarise the answers without names?','We should leave names out of the summary.','We need to discuss how we may use the answers first.'),
'Vill du skriva ner de tre frågorna?':('Would you like to write down the three questions?','I will write down the questions.','I do not want to write them down now.'),
'Vill du bestämma en dag för uppföljning?':('Would you like to choose a day to see how it is going?','We can choose a day to see how it is going.','I would like to start without choosing a date yet.'),
'Vill du börja med en kort version?':('Would you like to start with a short version?','I will start with the short version.','I would like to think about which version to use first.'),
'Vill du sedan berätta utan hela meningar framför dig?':('Would you then like to speak without full sentences written in front of you?','I will try using just a few key words.','I still need full sentences to help me.'),
'Vill du göra det före nästa vecka?':('Would you like to do it before next week?','I will do it before next week.','I will not have time before next week.'),
'Vill du skriva frågan i dag?':('Would you like to write the question today?','I will write the question today.','I will not have time to write it today.')
}

# Repeated short questions need their actual branch context. These metadata-only
# meanings do not add aliases or change what the automatic matcher accepts.
BRANCHES={
('clothes_m2','confirm_wait'):('I will wait by the mirror.','Waiting there does not work for me.','Jag väntar vid spegeln.','Det passar inte att vänta där.'),
('clothes_m2','confirm_return'):('Please put the trousers aside; I will return in five minutes.','Returning in five minutes does not work for me.','Lägg gärna undan byxorna, så kommer jag om fem minuter.','Jag kan inte komma tillbaka om fem minuter.'),
('parcel_m1','confirm_phone'):('I can show the code on my phone.','I cannot show the code on my phone right now.','Jag kan visa koden i telefonen.','Jag kan inte visa koden i telefonen just nu.'),
('parcel_m1','confirm_paper'):('I can show you the note with the code.','I cannot show you the note with the code.','Jag kan visa lappen med koden.','Jag kan inte visa lappen med koden.'),
('community_centre_m2','confirm_hour'):('I will return the ball in an hour.','I cannot return the ball in an hour.','Jag lämnar tillbaka bollen om en timme.','Jag kan inte lämna tillbaka bollen om en timme.'),
('neighbours_m1','confirm_friday'):('I can bring the key on Friday after six.','Friday after six does not work for me.','Jag kan lämna nyckeln på fredag efter sex.','Fredag efter sex passar inte mig.'),
('neighbours_m1','confirm_saturday'):('I can bring the key on Saturday morning before nine.','Saturday morning before nine does not work for me.','Jag kan lämna nyckeln på lördag morgon före nio.','Lördag morgon före nio passar inte mig.'),
('neighbours_m2','confirm_tonight'):('I can return the tool after seven this evening.','After seven this evening does not work for me.','Jag kan lämna tillbaka den efter sju i kväll.','Efter sju i kväll passar inte mig.'),
('neighbours_m2','confirm_tomorrow'):('I can return the tool before lunch tomorrow.','Before lunch tomorrow does not work for me.','Jag kan lämna tillbaka den före lunch i morgon.','Före lunch i morgon passar inte mig.'),
('social_plans_m1','confirm_nextweek'):('Meeting for a fika next week works for me.','Meeting for a fika next week does not work for me.','Vi kan ta en fika nästa vecka.','Nästa vecka passar inte för en fika.'),
('community_centre_m1','confirm_monday'):('I will come on Monday.','I cannot come on Monday.'),
('community_centre_m1','confirm_thursday'):('I will come on Thursday.','I cannot come on Thursday.'),
('community_centre_m3','confirm_cancel'):('Yes, please cancel my place.','No, that is not the change I wanted.'),
('housing_m1','confirm_tuesday'):('I can be at home on Tuesday morning.','I cannot be at home on Tuesday morning.'),
('housing_m1','confirm_wednesday'):('I can be at home on Wednesday afternoon.','I cannot be at home on Wednesday afternoon.'),
('course_planning_m3','confirm_morning'):('Please check whether the morning group has a place.','I would like to think about the morning group first.'),
('course_planning_m3','confirm_afternoon'):('Please check whether the afternoon group has a place.','I would like to think about the afternoon group first.')
}

def apply_confirmation_copy(mission):
    questions=[]
    for step in mission['steps']:
        if not step['id'].startswith('confirm_'):continue
        question,yes,no=QUESTIONS[step['prompt_sv']]
        branch=BRANCHES.get((mission['id'][4:],step['id']))
        if branch:yes,no=branch[:2]
        assert yes and no,(mission['id'],step['id'])
        questions.append(question)
        step['prompt_en']=question
        step['prompt_en_kind']='translation'
        step['objective_label']=question
        for index,intent in enumerate(step['intents']):
            meaning=yes if intent['id']=='confirm' else no
            intent['meaning_en']=meaning
            intent['feedback_en']='Your meaning: '+meaning
            if branch and len(branch)==4:intent['meaning_sv']=branch[2+index]
    mission['objectives'][-1]=' / '.join(dict.fromkeys(questions))
