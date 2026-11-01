"""Reviewed finite Swedish variants, context guards and natural role-play endings.

No stemming or open keyword acceptance. Short replies use exact, complete token
sequences; longer grouped replies retain their semantic anchors and rejections.
"""
import json,re
from pathlib import Path

# Explicit lexical pairs; replacements are whole words/phrases, never suffixes.
FORMS={
'ta med':['tar med','tar gärna med','ta med mig','tar med mig'],
'sitta här':['sitter här','sitter gärna här','sitta kvar här','sitter kvar här'],
'dricka här':['dricker här','dricker kaffet här'],
'vill ha':['skulle vilja ha','tar gärna'],
'jag vill':['jag skulle vilja','jag vill gärna'],
'kan jag':['skulle jag kunna','får jag'],
'kan du':['skulle du kunna','skulle du vilja'],
'vi kan':['vi skulle kunna'],
'tar':['ta'],'väljer':['välja'],'provar':['prova','testar','testa'],
'söker':['letar efter'],'lämnar tillbaka':['lämna tillbaka','får tillbaka'],
'skriver':['skriva'],'läser':['läsa'],'bokar':['boka'],'avbokar':['avboka'],
'stänger av':['stänga av'],'lägger':['lägga'],'stämmer av':['stämma av'],
'går igenom':['gå igenom'],'tar emot':['ta emot'],'förbereder':['förbereda'],
'frågar':['fråga'],'pratar':['prata','talar'],'gör':['göra'],'har':['ha'],
'i dag':['idag'],'i morgon':['imorgon'],'i kväll':['ikväll'],
'imorgon':['i morgon'],'ikväll':['i kväll'],'idag':['i dag'],
'i veckan':['per vecka','varje vecka'],'morgonen':['varje morgon','morgnarna'],
'efter tre':['efter klockan tre','efter 15','efter kl 15'],
'tio minuter':['10 minuter'],'en timme':['1 timme'],'halvtimme':['30 minuter'],
'telefonen':['mobilen'],'mobilen':['telefonen'],'jobbar':['arbetar'],'jobba':['arbeta'],
'skivor':['skivad'],'smörgås':['smörgåsen'],'bulle':['bullen'],
'fullkornsris':['fullkornsriset'],'sojadryck':['sojadrycken'],
'svart te':['svarta teet'],'grönt te':['gröna teet'],'hörlurar':['hörlurarna'],
'måndag':['måndagen'],'tisdag':['tisdagen'],'onsdag':['onsdagen'],
'torsdag':['torsdagen'],'fredag':['fredagen'],'lördag':['lördagen'],'söndag':['söndagen'],
'på fredag':['fredag'],'på torsdag':['torsdag'],'på måndag':['måndag'],
'längre stunder':['längre pass'],'dagen före':['dagen innan'],'tillsammans':['ihop'],
'första raden':['den första raden'],'på egen hand':['själv'],
'skruvmejsel':['skruvmejseln'],'växt':['blomma','blomman'],'blommor':['blommorna'],
'föreningsrummet':['rummet i föreningen'],'ett meddelande':['ett sms'],
'stödord':['några stödord'],'provlektion':['lektion på prov'],
'notiser':['aviseringar'],'gruppnotiserna':['notiserna från gruppen'],
}

# Both directions of a reviewed inflection family are enumerated explicitly.
# This is a finite dictionary, not a suffix stemmer or fuzzy-token rule.
for family in [('ta','tar'),('ha','har'),('skriva','skriver'),('läsa','läser'),('boka','bokar'),('fråga','frågar'),('prova','provar','testa','testar'),('välja','väljer'),('lämna','lämnar'),('stänga av','stänger av'),('lägga','lägger'),('skiva','skivad','skivor'),('titta','tittar'),('kolla','kollar')]:
    for form in family:FORMS.setdefault(form,[]).extend(v for v in family if v!=form)
FORMS.update({
 'grönt':['gröna'],'svart':['svarta'],'te':['teet'],
 'kommer tillbaka':['då kommer jag tillbaka','återkommer'],
 'tillbaka':['hem igen'],'direktbussen':['bussen som går direkt','den direkta bussen'],
 'utskrivet':['skriv ut','skriv gärna ut','skriva ut'],
 'likadan skjorta':['en likadan'],'letar':['kollar'],'tittar':['kollar'],
 'torsdag kväll':['torsdagskvällen','torsdagskväll'],
 'klasskamrat':['klasskompis','klasskompisen'],'affär':['affären'],'butik':['butiken'],
 'morgongruppen':['gruppen på morgonen'],'eftermiddagsgruppen':['gruppen på eftermiddagen'],
 'grönsakssoppa':['grönsakssoppan'],'soppa':['soppan'],'bidra':['hjälpa till'],
 'sitt sätt':['sitt eget sätt'],'veckan':['varje vecka','per vecka'],
 'notiser':['aviseringar','notiserna'],'aviseringar':['aviseringarna'],
 'fast uppgift':['bestämd uppgift','uppgift och behåller den'],
 'varje söndag':['på söndagar','på söndagarna'],
 'olika platser':['olika ställen'],'deltagare':['deltagarna','några','dem'],
 'vill prata':['vill berätta','gärna vill prata','gärna vill berätta'],
 'vill prova':['vill testa','vill pröva'],'provlektion':['lektion på prov','en lektion'],
 'digitalt alternativ':['delta digitalt','vara med digitalt','vara med på distans','delta på distans','alternativ på distans'],
})
FORMS['tar']+=['får bli']
FORMS['väljer']+=['föredrar','röstar på','satsar på']

# Context supplies the omitted object/duration in these bounded two-option turns.
# Keeping unnecessary nouns would reject ordinary short answers such as "Efter
# lunch passar mig bättre" even though the offered option is unambiguous.
GROUPS={
 ('neighbours_m1','choose_friday'):[['fredag','fredagen']],
 ('neighbours_m2','choose_tonight'):[['i kväll','ikväll']],
 ('neighbours_m2','choose_tomorrow'):[['i morgon','imorgon']],
 ('community_centre_m2','choose_hour'):[['om en timme','om 1 timme']],
 ('community_centre_m2','choose_closing'):[['före stängning','innan stängning','innan ni stänger']],
 ('colleagues_m2','choose_later'):[['efter lunch']],
 ('housing_m2','choose_visit'):[['besök','kommer hit','komma hit','komma och titta'],['besök','titta','kontrollera','undersöka','tekniker']],
}

# Each situation restricts optional keyword matches to an appropriate decision
# frame. Complete short answers are separately approved, without accepting the
# same option noun embedded in an unrelated story about somebody else.
DECISIONS={
'cafe':['jag tar','jag vill','jag skulle vilja','jag sitter','jag dricker','jag väljer','jag kan','jag stannar','tack','blir bra','går bra'],
'groceries':['jag tar','jag vill','jag skulle vilja','jag söker','jag letar','jag väljer','jag väntar','jag kommer','jag kan','kan du','kan jag','tack','blir bra','går bra','passar bättre'],
'transport':['jag väntar','jag kan vänta','jag stannar','jag sitter kvar','jag går','jag åker','jag tar','jag vill','jag behöver','jag ska','jag väljer','tack','blir bra'],
'library':['jag vill','jag skulle vilja','jag läser','jag kan läsa','jag tar','jag väljer','jag tittar','kan du','skriv gärna','tack','går bra','blir bra','det räcker'],
'clothes':['jag vill','jag skulle','jag provar','jag kan vänta','jag väntar','jag stannar','jag kommer','jag tar','jag tittar','jag väljer','kan du','visa gärna','tack','blir bra'],
'reception':['jag ska','jag har','jag väntar','jag går','jag stannar','jag kan','jag skriver','jag vill','det stavas','namnet stavas','tack','blir bra'],
'parcel':['jag har','jag visar','jag behöver','jag skulle','jag vill','jag letar','jag tittar','jag kollar','jag kommer','jag får komma','jag återkommer','jag kan','kan jag','det är','paketet är','koden finns','koden står','tack'],
'community_centre':['jag kommer','jag lämnar','jag kan','jag vill','jag bokar','jag avbokar','jag skulle','passar mig','passar oss','kan vi','tack','blir bra'],
'neighbours':['jag lämnar','jag kan','jag kommer','du får','kan du','det hjälper','det vore bra','skulle hjälpa','sänk gärna','använd gärna','passar mig','blir bra','blir bäst','tack'],
'colleagues':['jag kan','jag tar','jag gör','jag vill','vi kan','vi tar','vi frågar','vi går','vi tittar','kan vi','låt oss','fungerar för mig','blir bra','räcker','tack'],
'housing':['jag kan','jag vill','jag skulle','jag föredrar','jag bokar','ring mig','kan någon','passar','fungerar','går bra','blir bra','tack'],
'customer_service':['jag vill','jag skulle','jag byter','jag undrar','jag läser','jag kan läsa','kan jag','kan ni','ni får gärna','kontakta lagret','kontrollera med lagret','fråga lagret','förklara gärna','skicka villkoren','vi går igenom','tack'],
'course_planning':['jag läser','jag kan','jag börjar','jag tar','jag går','jag vill','jag skulle','jag är intresserad','vi börjar','vi tar','vi kan','blir bra','tack'],
'social_plans':['jag kan','jag kommer','vi kan','vi ses','vi lagar','vi bestämmer','vi sätter','vi tar','vi låter','alla kan bidra','var och en bidrar','alla får bidra','passar mig','passar för','blir bra','blir gott','låter gott','tack'],
'time_balance':['jag provar','jag testar','jag lägger','jag stänger','jag tar','jag börjar','jag skriver','jag övar','jag tränar','vi övar','mobilen får','notiserna får','låter bra','blir bra','tack'],
'shared_home':['vi provar','vi testar','vi väljer','vi tar','vi skickar','vi meddelar','vi stämmer','vi pratar','vi delar','vi kan','vi turas','vi sitter','blir bra','tack'],
'community_project':['vi börjar','vi testar','vi träffas','vi bokar','vi gör','vi ringer','vi kan','vi pratar','jag tar','jag hälsar','jag kan','jag förbereder','jag gör','jag tycker','blir bra','blir en bra','blir min uppgift','tack'],
'next_steps':['jag undersöker','jag frågar','jag vill','jag skulle','jag testar','jag börjar','jag övar','jag skriver','jag provar','vill jag fråga','låter bra','blir bra','tack'],
}

YES=['Ja.','Ja tack.','Ja, gärna.','Gärna.','Absolut.','Absolut, det passar.','Visst.','Det går bra.','Det passar bra.','Det fungerar fint.','Det blir bra.','Det låter bra.','Det funkar.','Det gör jag.','Det kan jag.','Ja, det kan jag.','Ja, det vill jag.','Ja, det stämmer.','Det stämmer.','Ja, det passar mig.','Javisst.','Självklart.']
NO=['Nej.','Nej tack.','Nej, tack ändå.','Det passar inte.','Det passar tyvärr inte.','Jag vill inte.','Jag vill helst inte.','Jag kan inte.','Tyvärr, jag kan inte.','Det går tyvärr inte.','Nej, det fungerar inte.','Ja, men det passar inte.','Ja, men jag kan inte.','Ja, men jag vill helst inte.','Nej, helst inte.']

ANSWERS={
'Passar bordet vid fönstret?':(['Jag sitter gärna vid fönstret.','Ja, bordet vid fönstret passar.'],['Jag vill hellre sitta någon annanstans.','Ja, men jag vill inte sitta vid fönstret.']),
'Passar det att hämta det vid disken?':(['Jag hämtar kaffet vid disken.','Ja, jag kan hämta det där.'],['Jag behöver hjälp att hämta kaffet.','Ja, men jag kan inte hämta det vid disken.']),
'Vill du betala med kort?':(['Jag betalar med kort.','Med kort, tack.','Kort går bra.'],['Jag vill betala kontant.','Kontant, tack.','Ja, men jag har inget kort.']),
'Vill du ha det i en ny kopp?':(['En ny kopp, tack.','Ja, byt gärna kopp.'],['Samma kopp går bra.','Jag behöver ingen ny kopp.','Det behövs inte.']),
'Kan du gå dit själv?':(['Jag hittar själv.','Ja, jag går dit själv.'],['Jag behöver hjälp att hitta dit.','Kan du följa med och visa?','Nej, kan du visa mig?']),
'Går det bra med den här förpackningen?':(['Den förpackningen går bra.'],['Jag vill ha en annan förpackning.']),
'Vill du ta en förpackning?':(['En förpackning, tack.'],['Jag väntar med att köpa något.']),
'Passar det att komma efter lunch?':(['Jag kommer efter lunch.','Ja, efter lunch passar.'],['Jag kan inte komma efter lunch.','Ja, men efter lunch passar inte.']),
'Vill du att jag visar hållplatsen på kartan?':(['Visa gärna hållplatsen på kartan.','Ja, kan du visa mig?'],['Jag hittar själv.','Det behövs inte, jag hittar själv.','Jag behöver ingen karta.']),
'Vill du att jag visar den på kartan?':(['Visa gärna på kartan.','Ja, kan du visa mig?'],['Jag hittar själv.','Det behövs inte, jag hittar själv.','Jag behöver ingen karta.']),
'Vill du se biljetten på skärmen?':(['Visa gärna biljetten.','Jag tittar gärna på skärmen.'],['Du behöver inte visa skärmen.','Berätta gärna i stället.']),
'Vill du gå på här?':(['Jag går på här.','Ja, jag går på bussen här.'],['Jag vill vänta med att gå på.']),
'Vill du gå dit?':(['Ja, jag går dit.','Jag går till den hållplatsen.'],['Jag behöver hjälp att hitta dit.']),
'Vill du låna den?':(['Jag lånar den gärna.','Ja, jag vill låna boken.'],['Jag vill bara titta i den.','Jag vill inte låna den än.']),
'Vill du ta med lappen?':(['Jag tar gärna med lappen.','Ja, ge mig gärna lappen.'],['Jag behöver ingen lapp.','Det behövs inte, tack.']),
'Vill du skriva av det?':(['Jag skriver av datumet.','Ja, jag antecknar det.'],['Jag behöver inte skriva av det.','Jag kommer ihåg det.']),
'Går det bra att skriva ut en sida?':(['En sida räcker.','Ja, bara en sida.'],['Jag behöver fler sidor.','Ja, men jag behöver två sidor.']),
'Vill du prova den nu?':(['Jag provar den gärna nu.','Ja, jag går till provrummet.'],['Jag vill vänta med att prova.','Jag tittar bara just nu.']),
'Vill du vänta här?':(['Jag väntar här.','Ja, jag kan vänta.'],['Jag kan inte vänta här.','Ja, men jag har inte tid att vänta.']),
'Vill du följa med till nästa hylla?':(['Jag följer gärna med.','Ja, visa gärna.'],['Jag tittar vidare själv.','Jag vill inte följa med.']),
'Kan du vänta här?':(['Ja, jag väntar här.','Jag kan vänta i receptionen.'],['Jag kan inte vänta här.','Jag behöver en annan plats.']),
'Kan du vänta utanför rum två?':(['Jag väntar utanför rum två.','Ja, jag går dit och väntar.'],['Jag kan inte vänta där.','Jag behöver vänta här i receptionen.']),
'Stämmer det att namnet är Kim?':(['Ja, jag heter Kim.','Kim stämmer.','Ja, namnet är rätt.'],['Namnet blev fel.','Nej, det är fel namn.','Ja, men namnet stämmer inte.']),
'Vill du ta hissen?':(['Jag tar gärna hissen.','Ja, jag åker hiss.'],['Jag tar trappan.','Jag behöver inte hissen.']),
'Vill du sitta på stolen vid dörren?':(['Jag sitter gärna där.','Ja, stolen vid dörren passar.'],['Jag vill sitta någon annanstans.','Jag vill hellre stå.']),
'Vill du ha den lilla storleken?':(['Den lilla kartongen blir bra.'],['Jag behöver en större kartong.']),
'Går det bra att lägga det på vågen?':(['Ja, jag lägger paketet här.'],['Jag behöver vänta med vägningen.']),
'Vill du prova det?':(['Ja, jag provar att leta där.','Jag tittar i meddelandet.'],['Jag vill inte leta i meddelandet nu.']),
'Passar det att komma före stängning?':(['Jag kommer före stängning.'],['Jag hinner inte före stängning.','Ja, men jag kan inte komma innan ni stänger.']),
'Vill du komma då?':(['Ja, jag kommer då.','Den tiden passar mig.'],['Jag kan inte komma då.','Den tiden passar tyvärr inte.']),
'Kan du lämna den före klockan sju?':(['Jag lämnar den före sju.','Ja, före sju går bra.'],['Jag hinner inte före sju.','Ja, men jag kan inte lämna den före sju.']),
'Passar nästa lördag?':(['Nästa lördag passar.','Ja, jag kan nästa lördag.'],['Jag kan inte nästa lördag.','Nästa lördag passar inte.']),
'Stämmer det?':(['Ja, det är rätt.'],['Nej, det blev fel.']),
'Kan du säga till om det fortfarande hörs för mycket?':(['Jag säger till om det stör.','Ja, jag hör av mig om det fortfarande hörs.'],['Jag vill helst slippa säga till igen.']),
'Kan du säga till om något annat stör?':(['Jag säger till om något stör.'],['Jag vill helst slippa säga till igen.']),
'Vill du att vi frågar tillsammans?':(['Vi frågar tillsammans.','Ja, vi kan gå och fråga.'],['Jag vill fråga själv.']),
'Vill du följa med?':(['Jag följer gärna med.'],['Jag kan inte följa med.','Fråga gärna utan mig.']),
'Vill du öppna tabellen?':(['Jag öppnar tabellen nu.'],['Jag kan inte öppna den just nu.']),
'Vill du skicka frågorna först?':(['Jag skickar frågorna först.','Ja, jag skickar dem före lunch.'],['Jag vill ta frågorna när vi ses.']),
'Kan vi stämma av klockan två?':(['Klockan två passar.','Ja, vi ses klockan två.'],['Jag kan inte klockan två.','Ja, men klockan två passar inte.']),
'Kan du vara hemma då?':(['Jag är hemma då.','Ja, jag kan vara hemma.'],['Jag kan inte vara hemma då.','Ja, men jag är inte hemma då.']),
'Passar det att vi ringer i eftermiddag?':(['Ni kan ringa i eftermiddag.'],['Jag kan inte prata i eftermiddag.']),
'Passar fredag förmiddag?':(['Fredag förmiddag går bra.','Jag kan på fredag förmiddag.'],['Fredag förmiddag passar inte.']),
'Kan du möta teknikern vid porten?':(['Jag möter teknikern vid porten.','Ja, jag kan öppna vid porten.'],['Jag kan inte möta teknikern vid porten.','Ja, men jag kan inte öppna porten då.']),
'Vill du att vi börjar där?':(['Ja, börja gärna där.'],['Jag vill vänta med det.']),
'Vill du ha instruktionerna skriftligt?':(['Skriftligt, tack.','Jag vill gärna få instruktionerna på papper.'],['Det räcker att du berättar.','Jag behöver inga skriftliga instruktioner.']),
'Går det bra med ett skriftligt svar?':(['Ett skriftligt svar går bra.'],['Jag vill hellre bli uppringd.']),
'Går det bra att vänta till i morgon?':(['Jag kan vänta till i morgon.'],['Jag behöver besked i dag.','Jag kan inte vänta till imorgon.']),
'Vill du sedan be om skriftlig bekräftelse?':(['Jag ber om en skriftlig bekräftelse.'],['Jag väntar med bekräftelsen.']),
'Kan du skicka en fråga före nästa lektion?':(['Jag skickar en fråga innan nästa lektion.'],['Jag hinner inte före nästa lektion.','Jag tar frågan på lektionen.']),
'Vill du vara kund först?':(['Jag är gärna kund först.'],['Jag vill lyssna först.','Börja du som kund.']),
'Vill du börja med att fråga?':(['Ja, jag börjar med en fråga.'],['Börja du med en fråga.','Jag vill lyssna först.']),
'Vill du att vi undersöker det?':(['Ja, undersök gärna om det finns plats.'],['Jag vill fundera först.']),
'Passar klockan sex?':(['Klockan sex passar mig.'],['Jag kan inte klockan sex.','Ja, men sex passar inte.']),
'Kan du ta med bröd?':(['Jag tar med bröd.','Ja, jag köper bröd.'],['Jag kan inte ta med bröd.','Ja, men jag hinner inte köpa bröd.']),
'Kan du ta med sallad?':(['Jag tar med sallad.','Ja, jag ordnar sallad.'],['Jag kan inte ta med sallad.']),
'Känns det rimligt?':(['Det känns rimligt.','Det beloppet fungerar för mig.'],['Det blir för dyrt för mig.','Jag har inte råd med det.']),
'Vill du att vi frågar gruppen?':(['Ja, vi kan fråga gruppen.'],['Vi väntar med att fråga gruppen.']),
'Vill du att vi stämmer av på fredag?':(['Vi hörs på fredag.','Fredag passar för avstämning.'],['Jag kan inte på fredag.','Jag vill prova utan avstämning först.']),
'Vill du berätta i morgon hur det gick?':(['Jag berättar i morgon.','Ja, vi hörs imorgon.'],['Jag vill prova några dagar först.']),
'Vill du prova fram till söndag?':(['Jag provar fram till söndag.'],['Jag vill inte bestämma en slutdag än.']),
'Vill du prova fram till söndag och sedan utvärdera?':(['Vi provar fram till söndag.'],['Jag vill vänta med att bestämma perioden.']),
'Vill du att vi provar i två veckor?':(['Vi provar i två veckor.','Två veckor blir bra.'],['Två veckor passar inte.','Jag vill fundera på perioden först.']),
'Vill du prova den regeln nästa vecka?':(['Vi provar nästa vecka.'],['Jag vill prata mer om regeln först.']),
'Vill du prova nästa vecka?':(['Nästa vecka fungerar.'],['Jag kan inte nästa vecka.']),
'Vill du prova i tre dagar?':(['Tre dagar blir lagom.','Vi testar i tre dagar.'],['Jag vill vänta med att bestämma perioden.']),
'Vill du att vi delar de två uppgifterna?':(['Vi delar på uppgifterna.'],['Jag vill fördela dem på ett annat sätt.']),
'Vill du att vi delar de tre frågorna?':(['Vi delar på frågorna.'],['Jag vill fördela frågorna annorlunda.']),
'Vill du att vi skriver in bytet i planen?':(['Skriv gärna in bytet.'],['Jag vill vänta med att skriva in det.']),
'Vill du ha texten från mig senast onsdag?':(['Onsdag fungerar för texten.'],['Jag behöver texten tidigare.']),
'Vill du att svaren blir frivilliga?':(['Det ska vara frivilligt att svara.'],['Jag vill prata mer om hur vi frågar först.']),
'Vill du att vi sammanfattar svaren utan namn?':(['Utan namn blir bra.','Vi tar bort namnen.'],['Vi behöver prata om hur vi får använda svaren först.']),
'Vill du skriva ner de tre frågorna?':(['Jag skriver ner frågorna.'],['Jag vill inte skriva ner dem nu.']),
'Vill du bestämma en dag för uppföljning?':(['Vi kan välja en dag för uppföljning.'],['Jag vill börja utan att bestämma en dag.']),
'Vill du börja med en kort version?':(['Jag börjar med den korta versionen.'],['Jag vill fundera på versionen först.']),
'Vill du sedan berätta utan hela meningar framför dig?':(['Jag provar att bara ha stödord.'],['Jag behöver hela meningar som stöd än så länge.']),
'Vill du göra det före nästa vecka?':(['Jag gör det före nästa vecka.'],['Jag hinner inte före nästa vecka.']),
'Vill du skriva frågan i dag?':(['Jag skriver frågan i dag.'],['Jag hinner inte skriva den i dag.'])
}

# The first independent set exposed additional ordinary expression families.
# These are now explicit regression repairs, not claimed as unseen validation.
ADDITIONAL_ANSWERS={
'Passar det att hämta det vid disken?':(['Jag hämtar det där.','Jag hämtar det vid disken.'],[]),
'Vill du låna den?':(['Den lånar jag gärna.','Den vill jag gärna låna.'],[]),
'Vill du prova den nu?':([],['Inte nu, jag har bråttom.','Jag har bråttom, så jag provar senare.']),
'Kan du vänta här?':(['Jag väntar här.'],[]),
'Vill du komma då?':(['Jag kommer då.'],[]),
'Passar det att ses då?':([],['Den tiden fungerar inte för mig.','Den tiden passar inte mig.']),
'Passar det?':([],['Den tiden fungerar inte för mig.','Den tiden passar inte mig.']),
'Vill du att vi frågar tillsammans?':(['Vi går och frågar tillsammans.','Vi kan fråga tillsammans.'],[]),
'Kan du vara hemma då?':([],['Jag är inte hemma då.']),
'Vill du ha instruktionerna skriftligt?':(['Skicka dem gärna skriftligt.','Skicka gärna instruktionerna skriftligt.'],[]),
'Kan du skicka en fråga före nästa lektion?':([],['Jag hinner inte skicka något innan dess.','Jag hinner inte skicka en fråga före nästa lektion.']),
'Passar klockan sex?':(['Klockan sex fungerar fint.','Klockan sex går bra.'],['Ja, men sex passar inte alls.','Klockan sex fungerar inte för mig.']),
'Vill du att vi stämmer av på fredag?':([],['Fredag går inte för mig.','Fredag fungerar inte för mig.']),
'Vill du att vi provar i två veckor?':(['Vi testar i två veckor.'],[]),
'Vill du att vi delar de tre frågorna?':(['Vi delar upp frågorna mellan oss.'],[]),
'Vill du skriva ner de tre frågorna?':([],['Jag vill inte skriva ner dem.']),
'Stämmer det att namnet är Kim?':([],['Ja, men jag heter inte Kim.','Jag heter inte Kim.']),
'Kan vi stämma av klockan två?':([],['Ja, men klockan två går inte.','Klockan två fungerar inte.']),
'Går det bra att vänta till i morgon?':([],['Ja, men jag kan inte vänta till i morgon.','Jag kan inte vänta till i morgon.']),
'Vill du skriva frågan i dag?':([],['Ja, men jag tänker inte skriva frågan i dag.','Jag tänker inte skriva frågan i dag.'])
}
for question,(yes,no) in ADDITIONAL_ANSWERS.items():
    old=ANSWERS.setdefault(question,([],[]));old[0].extend(yes);old[1].extend(no)
for question in list(ANSWERS):
    if 'prova' in question:ANSWERS[question][1].extend(['Ja, men jag vill inte prova det.','Jag vill inte prova det.'])

# Contextual outcomes: a refusal of optional help does not cancel the request.
# Every row follows the two authored material choices in source order.
ENDINGS={
'cafe_m1':[('Varsågod, bordet vid fönstret är ledigt. Jag kommer med kaffet.','Okej, vi letar efter ett annat bord åt dig.'),('Bra, jag ställer kaffet vid disken när det är klart. Ha en fin dag!','Okej, säg till så hjälper jag dig att hämta kaffet.')],
'cafe_m2':[('Du kan betala här. Smörgåsen kommer strax.','Okej, då hittar vi ett annat sätt att betala för smörgåsen.'),('Du kan betala här. Här är din bulle.','Okej, då hittar vi ett annat sätt att betala för bullen.')],
'cafe_m3':[('Här kommer ditt svarta te i en ny kopp. Ursäkta att det blev fel.','Okej, då behöver vi ingen ny kopp. Jag ordnar ditt svarta te.'),('Här kommer ditt gröna te i en ny kopp. Ursäkta misstaget.','Okej, då behöver vi ingen ny kopp. Jag ordnar ditt gröna te.')],
'groceries_m1':[('Bra, det vanliga riset står i gång tre.','Självklart hjälper jag dig. Vi går till gång tre tillsammans.'),('Bra, fullkornsriset står längst ner i gång fyra.','Jag följer med och visar fullkornsriset i gång fyra.')],
'groceries_m2':[('Då packar jag den skivade osten så här. Varsågod!','Okej, jag tar en annan förpackning till den skivade osten.'),('Då packar jag ostbiten så här. Varsågod!','Okej, jag tar en annan förpackning till ostbiten.')],
'groceries_m3':[('Varsågod, här är en förpackning sojadryck.','Okej, vi väntar med sojadrycken så länge.'),('Då är du välkommen tillbaka efter lunch i morgon.','Okej, vi har ingen tid bestämd. Du kan komma när det passar dig.')],
'transport_m1':[('Här på kartan ser du hållplatsen. Du kan vänta här en stund till.','Då behöver du ingen karta. Du kan vänta här tills det är dags att gå.'),('Här är hållplatsen på kartan. Trevlig resa!','Då hittar du dit själv. Trevlig resa!')],
'transport_m2':[('Här ser du enkelbiljetten. Kontrollera gärna resmålet innan du betalar.','Okej, vi går igenom enkelbiljetten utan skärmen.'),('Här ser du biljetten för båda resorna. Kontrollera gärna tiderna.','Okej, jag berättar om biljetten för båda resorna utan skärmen.')],
'transport_m3':[('Då kan du gå på här. Bussen går via parken till torget.','Okej, vi väntar med påstigningen. Det här är bussen via parken.'),('Direktbussen går från hållplatsen på andra sidan. Trevlig resa!','Okej, jag kan hjälpa dig att hitta till direktbussens hållplats.')],
'library_m1':[('Då hjälper jag dig att låna berättelsen. Hoppas du tycker om den!','Det går bra att titta i berättelsen här utan att låna den.'),('Då hjälper jag dig att låna naturboken.','Du kan läsa i naturboken här först.')],
'library_m2':[('Varsågod, här är lappen med det nya datumet.','Då behåller jag lappen här. Omlånet och det nya datumet gäller ändå.'),('Ta den tid du behöver för att skriva av datumet.','Okej, du kan läsa datumet här utan att skriva av det.')],
'library_m3':[('Då skriver vi ut en sida i färg.','Då väntar vi med utskriften tills vi vet hur många sidor du behöver.'),('Då skriver vi ut en sida i svartvitt.','Då väntar vi med utskriften tills antalet sidor är bestämt.')],
'clothes_m1':[('Varsågod, här är den blå tröjan. Provrummet är till vänster.','Okej, du kan titta på den blå tröjan först.'),('Varsågod, här är den gröna tröjan. Provrummet är till vänster.','Okej, du kan titta på den gröna tröjan först.')],
'clothes_m2':[('Jag säger till så fort provrummet är ledigt.','Okej, då behöver vi hitta ett annat sätt som passar dig.'),('Då lägger jag undan byxorna i fem minuter.','Okej, då räknar jag inte med att du kommer tillbaka om fem minuter.')],
'clothes_m3':[('Jag kommer strax med en annan skjorta.','Okej, jag väntar med att hämta en annan skjorta tills du kan titta på den.'),('Följ med, så visar jag några andra modeller.','Okej, du kan titta vidare i din egen takt.')],
'reception_m1':[('Tack, läraren kommer hit och hämtar dig.','Okej, vi behöver hitta en annan plats där läraren kan möta dig.'),('Tack, vägledaren hämtar dig utanför rum två.','Okej, jag meddelar vägledaren att vi behöver en annan mötesplats.')],
'reception_m2':[('Tack, då har jag skrivit Kim.','Tack för att du säger till. Då behöver vi rätta namnet innan vi går vidare.'),('Tack, då står Kim på besökslappen.','Då väntar jag med besökslappen tills namnet är rätt.')],
'reception_m3':[('Hissen tar dig till plan två. Där kan du vänta.','Okej, du behöver inte ta hissen. Säg till om du vill ha hjälp att hitta upp.'),('Varsågod, jag meddelar att du sitter här nere.','Okej, välj en annan ledig plats här i receptionen.')],
'parcel_m1':[('Tack, jag läser koden på skärmen och letar fram paketet.','Okej, vi väntar med att visa koden. Säg till när det fungerar.'),('Tack, jag kontrollerar koden på lappen.','Okej, vi behöver hitta ett annat sätt att kontrollera koden.')],
'parcel_m2':[('Här är den lilla kartongen.','Okej, då tittar vi på en större kartong.'),('Tack, då väger vi paketet.','Okej, då väntar vi med vägningen.')],
'parcel_m3':[('Ta den tid du behöver. Jag hjälper dig om du fastnar.','Okej, då väntar vi med att leta i meddelandet.'),('Då är du välkommen tillbaka med koden före stängning.','Okej, vi har ingen tid bestämd. Kontrollera öppettiden innan du kommer tillbaka.')],
'community_centre_m1':[('Välkommen på måndag!','Okej, då räknar vi inte med dig på måndag.'),('Välkommen på torsdag!','Okej, då räknar vi inte med dig på torsdag.')],
'community_centre_m2':[('Varsågod! Vi ses om en timme när du lämnar tillbaka bollen.','Då behöver vi komma överens om en annan återlämningstid först.'),('Tack, då räknar vi med att få tillbaka bollen före sju.','Då är återlämningstiden inte bestämd än. Vi behöver lösa det innan du lånar bollen.')],
'community_centre_m3':[('Då bokar jag en plats nästa lördag.','Då bokar jag ingen ny plats nästa lördag.'),('Då är platsen avbokad. Tack för att du hörde av dig.','Tack för rättelsen. Då väntar jag med avbokningen.')],
'neighbours_m1':[('Bra, då ses vi på fredag efter sex när du lämnar nyckeln.','Okej, då behöver vi hitta en annan tid för nyckeln.'),('Då ses vi på lördag morgon före nio.','Okej, då är tiden för att lämna nyckeln fortfarande öppen.')],
'neighbours_m2':[('Då ses vi efter sju i kväll.','Då behöver vi hitta en annan tid för återlämningen i kväll.'),('Då ses vi före lunch i morgon.','Okej, då är tiden för återlämningen i morgon inte bestämd.')],
'neighbours_m3':[('Tack, jag sänker nu. Säg till om det behövs mer.','Jag sänker ändå. Vi kan prata igen när det passar dig.'),('Tack, jag använder hörlurar i kväll.','Jag använder hörlurar ändå. Du behöver inte återkomma om det just nu.')],
'colleagues_m1':[('Då frågar vi tillsammans om bytet. Det gäller först när vi har fått klartecken.','Då får vi fråga om bytet var för sig innan något är bestämt.'),('Då går vi och frågar kollegan tillsammans.','Okej, jag frågar kollegan och återkommer med besked.')],
'colleagues_m2':[('Öppna tabellen, så tittar vi på den i tio minuter.','Okej, vi väntar med tabellen tills du kan öppna den.'),('Tack, skicka frågorna så ses vi efter lunch.','Då tar vi frågorna tillsammans efter lunch i stället.')],
'colleagues_m3':[('Då jobbar du vidare själv, och vi stämmer av klockan två.','Då gör du listan själv, men vi behöver en annan tid för avstämningen.'),('Då börjar vi med första raden och stämmer av klockan två.','Vi börjar med första raden. Tiden för nästa avstämning är fortfarande öppen.')],
'housing_m1':[('Tack, då noterar jag tisdag förmiddag för besöket.','Då bokar jag inte tisdag förmiddag. Vi behöver hitta en tid när du kan vara hemma.'),('Tack, då noterar jag onsdag eftermiddag.','Då bokar jag inte onsdag eftermiddag. Vi behöver en annan tid.')],
'housing_m2':[('Då ringer vi i eftermiddag och går igenom felet.','Då behöver vi komma överens om en annan tid för samtalet.'),('Då bokar vi besöket på fredag förmiddag.','Då bokar vi inte fredag förmiddag. Besökstiden är fortfarande öppen.')],
'housing_m3':[('Tack, teknikern möter dig vid porten på torsdag efter tre.','Då behöver vi ordna hur teknikern kommer in innan besöket kan bekräftas.'),('Tack, teknikern möter dig vid porten på fredag morgon.','Då behöver vi lösa tillträdet innan fredagens besök kan bekräftas.')],
'customer_service_m1':[('Då börjar vi med att kontrollera om rätt storlek finns.','Okej, då väntar vi med att undersöka bytet.'),('Jag skriver ner hur returen går till och vad som behöver kontrolleras.','Okej, jag förklarar returen muntligt i stället.')],
'customer_service_m2':[('Då skickar vi ett skriftligt besked i dag.','Då behöver vi välja ett annat sätt att ge dig besked i dag.'),('Då kontaktar vi lagret och återkommer i morgon.','Då behöver vi undersöka om du kan få besked tidigare. Ingen ny tid är bestämd.')],
'customer_service_m3':[('Bra, läs villkoren först och be sedan om slutdatumet skriftligt.','Okej, du kan läsa villkoren först. Något slutdatum är ännu inte bekräftat.'),('Då går vi igenom villkoren och ber om en skriftlig bekräftelse på slutdatumet.','Då går vi igenom villkoren. Vi väntar med den skriftliga bekräftelsen.')],
'course_planning_m1':[('Bra, läs sammanfattningen och skicka det du undrar över.','Läs sammanfattningen först, så kan du ta frågan på nästa lektion.'),('Bra, gå igenom den med en klasskamrat och skicka sedan en fråga.','Gå igenom den med en klasskamrat, så tar vi frågan på nästa lektion.')],
'course_planning_m2':[('Då börjar du som kund och jag som butiksanställd.','Då börjar jag som kund, så kan du lyssna först.'),('Då är jag grannen och du börjar med din fråga.','Då börjar jag med en fråga, så kan du svara först.')],
'course_planning_m3':[('Då undersöker vi om det finns plats i morgongruppen.','Då väntar vi med förfrågan till morgongruppen.'),('Då undersöker vi om det finns plats i eftermiddagsgruppen.','Då väntar vi med förfrågan till eftermiddagsgruppen.')],
'social_plans_m1':[('Då ses vi på söndag klockan sex. Vad trevligt!','Söndag är fortfarande ett förslag, men vi behöver en annan tid.'),('Då siktar vi på en fika nästa vecka och bestämmer dagen senare.','Då lämnar vi planen öppen tills vi hittar en tid som passar.')],
'social_plans_m2':[('Tack! Då lagar vi grönsakssoppa och du tar med bröd.','Ingen fara, då ordnar jag bröd till soppan.'),('Tack! Då lagar vi pasta och du tar med sallad.','Ingen fara, då ordnar jag sallad till pastan.')],
'social_plans_m3':[('Då föreslår vi högst femtio kronor per person för gruppen.','Då behöver vi hitta ett annat maxbelopp innan vi föreslår något.'),('Då frågar vi gruppen hur var och en vill bidra.','Då väntar vi med att fråga gruppen och tänker vidare.')],
'time_balance_m1':[('Då provar du morgonrutinen och vi hörs på fredag.','Prova morgonrutinen i din egen takt. Vi har ingen avstämning bokad.'),('Då provar du två pass och vi hörs på fredag.','Du kan prova två pass. Vi bestämmer en tid för avstämning senare.')],
'time_balance_m2':[('Prova det andra rummet, så hörs vi i morgon.','Prova det andra rummet i din egen takt. Du behöver inte rapportera i morgon.'),('Prova att stänga av notiserna, så hörs vi i morgon.','Prova utan notiser i din egen takt. Vi har ingen avstämning bokad.')],
'time_balance_m3':[('Då börjar du med ett meddelande om dagen fram till söndag.','Då lämnar vi start och slutdag öppna tills planen känns lagom.'),('Då provar vi att öva tillsammans och pratar om det på söndag.','Då bokar vi ingen provperiod än. Vi kan hitta en enklare start senare.')],
'shared_home_m1':[('Då provar vi veckoschemat i två veckor och pratar igen efteråt.','Då väntar vi med att bestämma provperioden för schemat.'),('Då har vi varsin fast uppgift i två veckor och följer upp sedan.','Då behöver vi prata mer innan vi bestämmer en provperiod.')],
'shared_home_m2':[('Då provar vi att meddela varandra dagen före nästa vecka.','Då börjar ingen ny regel nästa vecka. Vi pratar vidare först.'),('Då provar vi söndagsavstämningen nästa vecka.','Då väntar vi med att införa söndagsavstämningen.')],
'shared_home_m3':[('Då delar vi tiden i tre dagar och ser hur det fungerar.','Då är ingen provperiod bestämd för att dela tiden.'),('Då provar vi olika platser i tre dagar och följer upp.','Då väntar vi med att bestämma en provperiod på olika platser.')],
'community_project_m1':[('Då tar jag reservlokalen och du kontrollerar vägen till parken.','Då behöver vi fördela kontrollen av parken och reservlokalen på ett annat sätt.'),('Då kontrollerar jag kostnaden och du undersöker storlek och tillgänglighet.','Då behöver vi bestämma vem som kontrollerar rummet innan vi bokar.')],
'community_project_m2':[('Då skriver vi in vem som tar över efter din första timme.','Då är avlösningen fortfarande olöst. Vi behöver bestämma den innan uppgiften är klar.'),('Då skickar jag texten senast onsdag så att du kan göra skyltarna.','Då behöver vi hitta en annan tid för texten till skyltarna.')],
'community_project_m3':[('Då skriver vi tydligt att enkäten är frivillig.','Då väntar vi med enkäten tills vi har rett ut hur vi vill fråga.'),('Då sammanfattar vi svaren utan namn.','Då behöver vi komma överens om hur svaren får användas innan vi sammanfattar dem.')],
'next_steps_m1':[('Då skriver du ner frågorna innan du kontaktar kursen om en provlektion.','Du kan undersöka provlektionen ändå. Frågorna behöver inte skrivas ner nu.'),('Då väljer du en dag att följa upp din egen studieplan.','Då kan du börja med planen utan att boka en avstämning än.')],
'next_steps_m2':[('Då lyssnar jag på den korta versionen först.','Då väntar vi med framförandet tills du vet vilken version du vill prova.'),('Då skriver du stödord och provar sedan att berätta med dem som hjälp.','Då får du behålla hela meningar som stöd tills du vill prova något annat.')],
'next_steps_m3':[('Då provar du resvägen före nästa vecka och jämför tiden med din plan.','Då lämnar vi dagen för provresan öppen.'),('Då skriver du frågan om digitalt deltagande i dag.','Då väntar du med frågan tills du har tid att formulera den.')]
}

def expand_group(group):
    out=list(group)
    for phrase in group:
        for before,afters in FORMS.items():
            pattern=r'(?<!\w)'+re.escape(before)+r'(?!\w)'
            if re.search(pattern,phrase):
                out.extend(re.sub(pattern,after,phrase) for after in afters)
    return list(dict.fromkeys(out))

def revise(situation):
    from library_sources.confirmation_copy import apply_confirmation_copy
    root=Path(__file__).parents[1]
    inventory=json.loads((root/'authored_reply_inventory.json').read_text(encoding='utf-8'))['missions']
    sid=situation['id'][4:]
    for mission in situation['missions']:
        key=mission['id'][4:]
        mission['recognition_version']='finite-variants-3'
        mission['recognition_limit_en']='This guided conversation recognises a reviewed set of common replies. A request to rephrase can reflect an app limitation, even when your Swedish is correct.'
        mission['objectives'][-1]='Answer the final follow-up question, accepting or declining that specific point.'
        mission['opening_sv']=mission['opening_sv'].replace('den påhittade intervjun','intervjun')
        mission['opening_en']=mission['opening_en'].replace('the fictional interview','the interview')
        for step in mission['steps']:
            step['prompt_sv']=step['prompt_sv'].replace('I övningen kan vi','Vi kan').replace('I övningen kan du','Du kan').replace(' i den här övningen','').replace(' i övningen','').replace('den påhittade intervjun','intervjun')
            step['unknown_feedback_en']='The app did not recognise this reply. Your Swedish may be correct. Choose what you meant to continue. You can also try another wording or show an example; this does not reduce your progress.'
            if step['id']=='choice':step['unknown_reply_sv']='Vilket alternativ vill du välja?'
            for intent in step['intents']:
                intent['meaning_sv']=intent['examples_sv'][0]
                intent['meaning_en']=step['hint_en']
                if (key,intent['id']) in GROUPS:intent['required_groups']=GROUPS[key,intent['id']]
                intent['required_groups']=[expand_group(g) for g in intent['required_groups']]
                approved=inventory.get(key,{}).get(step['id'],{}).get(intent['id'],[])
                intent['exact_replies_sv']=list(dict.fromkeys(intent['examples_sv']+approved))
                if step['id']=='choice':
                    family={'cafe':['det får bli'],'groceries':['då kommer jag tillbaka'],'library':['räcker för mig','räcker för oss','räcker bra'], 'clothes':['har ni','finns det'], 'community_centre':['kan jag komma','jag kan komma'], 'neighbours':['det vore bäst','det skulle hjälpa','du får nyckeln'], 'housing':['kom gärna','kom på'], 'course_planning':['vi börjar i'], 'social_plans':['jag röstar på','alla kan hjälpa till'], 'time_balance':['jag satsar på'], 'community_project':['jag ringer']}.get(sid,[])
                    intent['required_groups'].append(expand_group(DECISIONS[sid]+family+['jag föredrar','jag väljer','jag skulle helst vilja','jag tycker att vi ska','jag tycker vi ska','jag föreslår att vi','passar bäst','passar mig','passar oss','fungerar för mig','fungerar för oss','blir bäst','fungerar fint','går fint']))
                    card=next(p for p in mission['phrases'] if p['id']==mission['id']+'_'+intent['branch'])
                    intent['meaning_en']=card['en']
                    intent['reject_terms']=list(dict.fromkeys(intent['reject_terms']+['varken','både','båda','eller','vet inte','kanske','nja']))
                    if key=='cafe_m1' and intent['id']=='choose_takeaway':
                        intent['required_groups'].append(['kaffe','kaffet','det'])
                    if key=='community_centre_m3' and intent['id']=='choose_cancel':
                        intent['exact_replies_sv']+=['Avboka bara, jag vill inte boka något nytt.','Jag vill bara avboka, inte boka om.','Jag vill avboka utan att boka om.']
                if step['id'].startswith('confirm_'):
                    step['objective_label']='Respond to the specific final follow-up, accepting or declining it.'
                    step['prompt_en']='Answer the final question. Declining optional help does not cancel your earlier choice.'
                    intent['outcome_scope']='final_followup_only'
                    intent['reference_question_sv']=step['prompt_sv']
                    # A bare 'ja' must not match an unrelated sentence containing it.
                    intent['required_groups']=[]
                    answers=ANSWERS.get(step['prompt_sv'],([],[]))[0 if intent['id']=='confirm' else 1]
                    intent['meaning_sv']=answers[0] if answers else ('Jag accepterar ditt sista förslag.' if intent['id']=='confirm' else 'Jag tackar nej till ditt sista förslag.')
                    intent['meaning_en']='Accept the specific final question or follow-up.' if intent['id']=='confirm' else 'Decline the specific final question or follow-up; this does not automatically cancel the earlier choice.'
                    intent['feedback_en']='You accepted the final follow-up. This completes guided practice, not a language level.' if intent['id']=='confirm' else 'You declined that specific follow-up. The character response explains what remains agreed or unresolved. This is a valid practice outcome.'
                    # Finite authored statements have finite yes/no discourse variants.
                    # They are serialized as complete approved strings, never stripped
                    # or inferred at runtime. A contrary suffix cannot match them.
                    fuller=[]
                    for answer in answers:
                        fuller.append(answer)
                        if not answer.startswith(('Ja,','Nej,')):
                            fuller.append(('Ja, ' if intent['id']=='confirm' else 'Nej, ')+answer[0].lower()+answer[1:])
                    intent['exact_replies_sv']=list(dict.fromkeys(intent['exact_replies_sv']+(YES if intent['id']=='confirm' else NO)+fuller))
                text=intent['reply_sv']
                text=text.replace('I övningen kan vi','Vi kan').replace('I övningen kan du','Du kan')
                text=text.replace(' i den här övningen','').replace(' i övningen','')
                text=text.replace(' Använd bara en påhittad kod.','').replace(' Visa inga riktiga uppgifter.','')
                intent['reply_sv']=text
        confirmations=[s for s in mission['steps'] if s['id'].startswith('confirm_')]
        for step,endings in zip(confirmations,ENDINGS[key]):
            for intent,reply in zip(step['intents'],endings):intent['reply_sv']=reply
        writing={
        'cafe_m1':('Skriv till en vän vilken dryck du ville beställa och om du valde att sitta kvar eller ta med den. Skriv också om hämtning eller sittplats fortfarande är oklart.','Tell a friend which drink you wanted and whether you chose to stay or take it away. Mention any unresolved collection or seating arrangement.'),
        'transport_m1':('Skriv vilken buss du planerar att ta och när du tror att du kommer fram. Hitta på en ankomsttid.','Write which bus you plan to take and invent an expected arrival time.'),
        'library_m2':('Skriv en påminnelse om att lämna tillbaka boken. Använd datumet i lästexten och ange att det gäller det meddelandet.','Write a book-return reminder using the date in the reading message; make clear that the reminder refers to that message.'),
        'clothes_m2':('Skriv till en vän om du valde att vänta på provrummet eller komma tillbaka senare. Berätta om planen ändrades.','Tell a friend whether you chose to wait for the fitting room or return later, including any change to the plan.'),
        'parcel_m1':('Skriv till en vän att du vill hämta ett paket och om något fortfarande behöver ordnas.','Tell a friend you want to collect a parcel and whether anything still needs to be arranged.'),
        'parcel_m3':('Skriv om du vill leta efter koden nu eller komma tillbaka senare. Berätta vad nästa steg blir.','Write whether you want to look for the code now or return later, and describe the next step.'),
        'community_centre_m2':('Skriv en lapp om vad du vill låna och vilken återlämningstid du föreslog. Säg om tiden blev bestämd.','Write a note about what you want to borrow and your proposed return time; say whether the time was agreed.'),
        'community_centre_m3':('Skriv ett artigt meddelande om vad du vill ändra i bokningen: avboka, boka om eller vänta med ändringen.','Write a polite message explaining whether you want to cancel, rebook or wait before changing the booking.'),
        'neighbours_m1':('Skriv instruktioner om växten och tacka för hjälpen. Berätta om tiden för nyckeln blev bestämd. Använd påhittade uppgifter.','Write plant-care instructions, thank the neighbour and say whether the key handover time was agreed. Use fictional details.'),
        'neighbours_m2':('Skriv vad du vill låna, varför och när du föreslog att lämna tillbaka det. Säg om tiden fortfarande är öppen.','Write what you want to borrow, why, and the proposed return time. State whether the time is still unresolved.'),
        'colleagues_m3':('Skriv vilken uppgift du börjar med och om ni bestämde en tid för avstämning.','Write which task you will start with and whether you agreed a time to check in.'),
        'shared_home_m2':('Skriv ett vänligt förslag om gäster med plats för undantag. Skilj på det ni föreslog och det ni faktiskt bestämde.','Write a friendly proposal about visitors, allowing exceptions. Distinguish proposals from anything actually agreed.')
        }
        if key in writing:mission['writing']['prompt_sv'],mission['writing']['prompt_en']=writing[key]
        # Reading/listening are connected follow-ups, not purported records of this
        # branch. Writing explicitly permits an unresolved or declined outcome.
        for activity in ['reading','listening']:
            mission[activity]['context_en']='A separate message in the same everyday setting. Its details may differ from your conversation.'
        mission['writing']['prompt_sv']+=' Beskriv det som faktiskt blev bestämt eller fortfarande är öppet. Du kan också skriva att du tackade nej.'
        mission['writing']['prompt_en']+=' Describe what was actually agreed or is still open; you may say that you declined.'
        mission['learner_brief_en']+=' Use fictional names, codes and addresses. No real booking or purchase is made.'
        apply_confirmation_copy(mission)
