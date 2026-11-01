"""Separately authored evaluation utterances, not derived from example strings.

This is an engineering holdout for the deterministic contract, not an externally
reviewed learner corpus. Do not silently tune the matcher to these cases and keep
calling them unseen. Valid paraphrases can still be unsupported by a narrow guide.
"""
import json
from pathlib import Path

# Each row: mission suffix, positive paraphrase, negated/contradictory request,
# nearby-topic distractor. These do not import the library or its examples.
ROWS = [
 ('cafe_m1','Hej! Kan jag få en kaffe, tack?','Jag vill inte ha kaffe.','Jag dricker kaffe hemma.'),
 ('cafe_m2','Hur mycket kostar smörgåsen här?','Jag undrar inte vad en smörgås kostar.','Smörgåsen ser god ut.'),
 ('cafe_m3','Ursäkta, jag bad om te.','Jag beställde inte te.','Jag tycker om att dricka te hemma.'),
 ('groceries_m1','Ursäkta, var hittar jag riset?','Jag frågar inte var riset finns.','Jag köpte ris i går.'),
 ('groceries_m2','Kan jag få 200 gram ost, tack?','Jag vill inte ha 200 gram ost.','Osten kostar tjugo kronor.'),
 ('groceries_m3','Hej, jag söker havredryck.','Jag söker inte havredryck.','Min vän drack havredryck i går.'),
 ('transport_m1','Vilken tid går bussen till centrum?','Jag undrar inte när nästa buss till centrum går.','Bussen till centrum är blå.'),
 ('transport_m2','Kan jag köpa en biljett till stationen här?','Jag vill inte köpa en biljett till stationen.','Stationen ligger nära mitt hem.'),
 ('transport_m3','Åker bussen till torget?','Går bussen inte till torget?','Torget har många butiker.'),
 ('library_m1','Jag letar efter lättlästa böcker, tack.','Jag vill inte ha lättlästa böcker.','Biblioteket är fint.'),
 ('library_m2','Går det att förlänga lånet?','Jag vill inte förlänga lånet.','Boken är intressant.'),
 ('library_m3','Jag behöver hjälp med en utskrift av min fil.','Jag ska inte skriva ut dokumentet.','Jag läser ett dokument.'),
 ('clothes_m1','Finns tröjan i storlek M?','Jag vill inte ha tröjan i medium.','Tröjan är mjuk.'),
 ('clothes_m2','Ursäkta, var finns provrummet?','Jag undrar inte var provrummet är.','Byxorna är svarta.'),
 ('clothes_m3','Här fattas en knapp.','Det saknas inte någon knapp.','Jag tycker om knapparna.'),
 ('reception_m1','Hej, jag har bokat en tid klockan tio.','Jag har ingen tid klockan tio.','Klockan är tio nu.'),
 ('reception_m2','Mitt namn är Kim.','Jag heter inte Kim.','Kim är min vän.'),
 ('reception_m3','Var kan jag vänta tills mötet börjar?','Jag frågar inte var jag ska vänta.','Jag tycker om den här stolen.'),
 ('parcel_m1','Hej, ska hämta ett paket.','Jag ska inte hämta något paket.','Paketet är stort.'),
 ('parcel_m2','Kan jag skicka ett paket här?','Jag vill inte skicka paketet.','Paketet kom i går.'),
 ('parcel_m3','Kan du hjälpa mig att hitta koden?','Jag behöver inte hjälp att hitta koden.','Meddelandet finns på min telefon.'),
 ('community_centre_m1','Vilken tid börjar språkcaféet här?','Jag undrar inte när språkcaféet börjar.','Språkcaféet verkar trevligt.'),
 ('community_centre_m2','Får jag låna en boll en stund?','Jag vill inte låna en boll.','Bollen ligger på golvet.'),
 ('community_centre_m3','Jag behöver avboka min plats på målning.','Jag vill inte avboka min plats.','Målningen var rolig förra veckan.'),
 ('neighbours_m1','Skulle du kunna vattna blommor åt mig?','Kan du inte vattna min växt?','Min växt är grön.'),
 ('neighbours_m2','Kan jag låna skruvmejseln?','Jag vill inte låna din skruvmejsel.','Skruvmejseln är röd.'),
 ('neighbours_m3','Vi behöver tala om musiken.','Jag vill inte prata om musiken.','Musiken är från en film.'),
 ('colleagues_m1','Skulle vi kunna byta pass på fredag?','Jag vill inte byta pass på fredag.','På fredag går jag hem tidigt.'),
 ('colleagues_m2','Skulle du kunna hjälpa mig med en tabell?','Jag behöver inte hjälp med tabellen.','Tabellen har tre kolumner.'),
 ('colleagues_m3','Vad ska jag göra först?','Jag frågar inte vilken uppgift jag ska börja med.','Listan är lång.'),
 ('housing_m1','Det droppar från kranen i köket.','Kranen i köket läcker inte.','Kranen i köket är ny.'),
 ('housing_m2','Nu stannar maskinen igen.','Tvättmaskinen stannar inte igen.','Tvättmaskinen är vit.'),
 ('housing_m3','Kan vi boka om tiden för besöket?','Jag vill inte ändra tiden för besöket.','Besöket var trevligt.'),
 ('customer_service_m1','Det kom fel storlek på skorna.','Jag fick inte fel storlek.','Skorna är fina.'),
 ('customer_service_m2','Jag undrar var mitt paket finns.','Jag vill inte veta var paketet är.','Paketet väger två kilo.'),
 ('customer_service_m3','Jag behöver avsluta abonnemanget.','Jag vill inte avsluta abonnemanget.','Abonnemanget kostar mycket.'),
 ('course_planning_m1','Hur gör jag för att komma ikapp undervisningen?','Jag vill inte ta igen lektionen.','Lektionen är på tisdag.'),
 ('course_planning_m2','Jag behöver öva på att ställa frågor.','Jag vill inte träna på att ställa frågor.','Frågorna är på svenska.'),
 ('course_planning_m3','Kan jag byta gruppen?','Jag vill inte byta till en annan grupp.','Gruppen har tolv elever.'),
 ('social_plans_m1','Tack för din inbjudan, kan vi välja en annan dag?','Tack för inbjudan, jag vill inte föreslå en annan dag.','Jag gillar att träffa vänner.'),
 ('social_plans_m2','Jag föredrar vegetariskt.','Jag vill inte ha vegetarisk mat.','Maten luktar gott.'),
 ('social_plans_m3','Hur kan vi dela kostnaderna?','Jag undrar inte hur vi ska dela kostnaden.','Festen är på lördag.'),
 ('time_balance_m1','Jag behöver få tid att träna svenska.','Jag vill inte hitta tid för att öva svenska.','Svenska är ett språk.'),
 ('time_balance_m2','Notiser stör mig när jag läser på kvällen.','Meddelanden stör mig inte när jag läser.','Min mobil är ny.'),
 ('time_balance_m3','Jag missade några pass och vill börja igen nu.','Jag missade pass men vill inte börja igen.','Övningen börjar klockan fem.'),
 ('shared_home_m1','Vi behöver dela städningen rättvist.','Jag vill inte dela städningen jämnare.','Köket har vita väggar.'),
 ('shared_home_m2','Kan vi meddela varandra innan gäster kommer?','Jag vill inte att vi säger till innan gäster kommer.','Gästerna kommer från en annan stad.'),
 ('shared_home_m3','Jag behöver tyst för att plugga när du har möten.','Jag behöver inte lugn för att studera under möten.','Rummet har ett stort fönster.'),
 ('community_project_m1','Jag hoppas att alla kan delta.','Jag vill inte att alla ska kunna delta.','Parken ligger vid ån.'),
 ('community_project_m2','Jag kan hjälpa till, men vill begränsa min uppgift.','Jag vill inte hjälpa till eller begränsa någon uppgift.','Skyltarna är blå.'),
 ('community_project_m3','Vi behöver förstå varför det var få deltagare och vad vi kan ändra.','Jag vill inte förstå varför få kom eller vad vi kan ändra.','Det regnade i går.'),
 ('next_steps_m1','Kan vi jämföra kvällskurs med att studera själv?','Jag vill inte jämföra kvällskurs med att studera själv.','Skolan ligger nära stationen.'),
 ('next_steps_m2','Jag behöver förklara en styrka genom ett konkret exempel.','Jag vill inte förklara mina styrkor med ett konkret exempel.','Intervjun börjar på måndag.'),
 ('next_steps_m3','Jag behöver jämföra restid och chansen att lära mig mer.','Jag vill inte jämföra restiden med att lära mig mer.','Bussen är röd.')
]

def main():
    cases=[]
    for mid,positive,negative,offtopic in ROWS:
        cases.extend([{'mission_id':'lib_'+mid,'step_id':'request','text_sv':positive,'expected_intent':'request_answer','kind':'heldout_positive'}, {'mission_id':'lib_'+mid,'step_id':'request','text_sv':negative,'expected_intent':None,'kind':'heldout_negation'}, {'mission_id':'lib_'+mid,'step_id':'request','text_sv':offtopic,'expected_intent':None,'kind':'heldout_nearby_topic'}])
    data={'schema_version':'1.0','status':'Authored separately from demonstration examples; engineering evaluation, not an external learner-validation set. After running, these become regression cases; keep new unseen cases for later evaluation.','cases':cases}
    (Path(__file__).parent/'library_evaluation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {len(cases)} separately authored evaluation cases.')

if __name__=='__main__':main()
