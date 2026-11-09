"""Explicit source-inventory exclusions. No exclusions become new negative gold."""
import re,unicodedata

def normalized(text):return tuple(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold()))

VERIFICATION_YES={normalized(x) for x in [
 'Ja.','Ja tack.','Absolut.','Visst.','Javisst.','Självklart.',
 'Ja, det stämmer.','Det stämmer.','Ja, jag heter Kim.','Kim stämmer.',
 'Ja, namnet är rätt.','Jag heter Kim.','Namnet är rätt.'
]}
VERIFICATION_NO={normalized(x) for x in [
 'Nej.','Nej tack.','Nej, tack ändå.','Jag vill inte.','Jag vill helst inte.',
 'Nej, helst inte.','Ja, men jag vill helst inte.',
 'Namnet blev fel.','Nej, namnet blev fel.','Nej, det är fel namn.',
 'Ja, men namnet stämmer inte.','Jag heter inte Kim.','Ja, men jag heter inte Kim.',
 'Nej, jag heter inte Kim.','Nej, det stämmer inte.'
]}

def exclusion_reason(mission_id,step,intent,text):
    if step['prompt_sv']=='Stämmer det att namnet är Kim?':
        allowed=VERIFICATION_YES if intent['id']=='confirm' else VERIFICATION_NO
        if normalized(text) not in allowed:
            return 'A generic offer-response does not reliably affirm the name, deny it, or explicitly refuse verification. Preserve it for context review rather than assign UNKNOWN as a new gold label.'
    ambiguous={
      ('lib_cafe_m1','confirm_takeaway','decline',normalized('Jag behöver hjälp att hämta kaffet.')):
        'Needing collection assistance does not by itself refuse collection at the counter; unaided collection was not required.',
      ('lib_transport_m3','confirm_direct','decline',normalized('Jag behöver hjälp att hitta dit.')):
        'Needing route assistance does not by itself refuse going to the other stop.',
      ('lib_customer_service_m3','confirm_written','decline',normalized('Jag väntar med bekräftelsen.')):
        'The offer already asks about confirmation later, after reading. An unspecified delay does not reliably refuse that later request.',
      ('lib_customer_service_m3','confirm_explain','decline',normalized('Jag väntar med bekräftelsen.')):
        'The offer already asks about confirmation later, after explanation. An unspecified delay does not reliably refuse that later request.'
    }
    return ambiguous.get((mission_id,step['id'],intent['id'],normalized(text)))

def apply_example_adjudication(mission):
    for step in mission['steps']:
        if not step['id'].startswith('confirm_'):continue
        for intent in step['intents']:
            intent['exact_replies_sv']=[text for text in intent['exact_replies_sv'] if exclusion_reason(mission['id'],step,intent,text) is None]
            if step['prompt_sv']=='Stämmer det att namnet är Kim?':
                intent['examples_sv']=['Ja, det stämmer.'] if intent['id']=='confirm' else ['Nej, det stämmer inte.']
                for text in intent['examples_sv']:
                    if text not in intent['exact_replies_sv']:intent['exact_replies_sv'].append(text)
                step['hint_sv']='Ja, det stämmer. / Nej, det stämmer inte.'
                step['hint_en']='Yes, that is correct. / No, that is not correct.'
