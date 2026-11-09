"""Rebuild source-bound lexical language-support data from authored Swedish fields."""
import hashlib,json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def extract(library):
    words=set()
    def add(text):
        if isinstance(text,str):words.update(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold()))
    for situation in library['situations']:
        for mission in situation['missions']:
            add(mission.get('opening_sv'))
            for step in mission['steps']:
                add(step.get('prompt_sv'));add(step.get('unknown_reply_sv'))
                for intent in step['intents']:
                    add(intent.get('meaning_sv'));add(intent.get('reply_sv'))
                    for text in intent.get('examples_sv',[]):add(text)
                    for text in intent.get('exact_replies_sv',[]):add(text)
    return sorted(words)

if __name__=='__main__':
    source=ROOT/'content'/'library.json';raw=source.read_bytes();library=json.loads(raw)
    result={'schema_version':'1','source_sha256':hashlib.sha256(raw).hexdigest(),'content_version':library.get('content_version'),'words':extract(library)}
    Path(__file__).with_name('swedish_support_vocabulary.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
    print('words',len(result['words']),'source_sha256',result['source_sha256'])
