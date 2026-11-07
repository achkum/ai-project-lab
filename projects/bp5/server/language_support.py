"""Conservative, source-bound language support; never selects a lesson intent."""
import math,re,unicodedata

def tokens(text):
    if not isinstance(text,str):raise ValueError('Invalid text')
    return re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold())

def language_support(text,objective,label,top_probability,swedish_probability,vocabulary):
    """Return (supported, evidence) using language signals, not task meaning."""
    if not isinstance(label,str) or not re.fullmatch(r'[a-z]{2,3}',label):raise ValueError('Invalid language')
    for v in (top_probability,swedish_probability):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1:raise ValueError('Invalid language score')
    if swedish_probability>top_probability+1e-5 or (label=='sv' and abs(top_probability-swedish_probability)>1e-5):raise ValueError('Invalid language score')
    if not isinstance(vocabulary,(set,frozenset)):raise ValueError('Invalid vocabulary')
    terms=tokens(text)
    if not terms:return False,'unresolved'
    shared={('ja',),('nej',),('ok',),('okej',),('gärna',),('ja','tack'),('nej','tack')}
    if objective=='confirm' and tuple(terms) in shared:return True,'shared_confirmation'
    if label!='sv' and top_probability>=.35 and top_probability>swedish_probability:return False,'foreign_veto'
    if len(terms)<=5:
        if all(term in vocabulary for term in terms):return True,'lexical_support'
        if label=='sv' and top_probability>=.8:return True,'detector'
        return False,'unresolved'
    if swedish_probability>=.05:return True,'detector'
    return False,'unresolved'
