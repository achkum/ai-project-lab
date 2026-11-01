import json, os, sys, time, uuid, sqlite3, threading, tempfile, subprocess, shutil, re
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent.parent
RUNTIME = Path(os.environ.get('BP5_RUNTIME', BASE.parent.parent / 'runtime' / 'local-products' / 'bp5'))
MODEL = Path(os.environ.get('BP5_MODEL_PATH', RUNTIME / 'qwen3-instruct-4b.gguf'))
DATA = Path(os.environ.get('LAB_DATA_DIR', BASE / 'data')); DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'bp5.sqlite3'
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
MODEL_LOCK = threading.Lock()
MUTATION_LOCK = threading.RLock()
MAX_AUDIO = 12 * 1024 * 1024

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()

def connect():
    c=sqlite3.connect(DB, timeout=30, factory=ClosingConnection); c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)'); return c

def all_sessions():
    with connect() as c: return [json.loads(row[0]) for row in c.execute('SELECT payload FROM sessions ORDER BY rowid DESC')]

def get_session(sid):
    with connect() as c: row=c.execute('SELECT payload FROM sessions WHERE id=?',(sid,)).fetchone()
    if not row: raise ValueError('Session not found')
    return json.loads(row[0])

def save(s):
    with connect() as c: c.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)',(s['id'],json.dumps(s,ensure_ascii=False)))

def content():
    def read(name):
        p=BASE/'content'/name
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    scenarios=read('scenarios.json'); curriculum=read('curriculum.json')
    return {'scenarios':scenarios.get('scenarios',[]),'curriculum':curriculum}

def bounded(v, maxlen=2000):
    if not isinstance(v,str) or len(v)>maxlen: raise ValueError('Invalid or too long text')
    return v.strip()

def execute(args, input_data=None, timeout=180):
    try:
        r=subprocess.run([str(x) for x in args],input=input_data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,creationflags=CREATE_NO_WINDOW)
    except (OSError,subprocess.TimeoutExpired) as e: raise RuntimeError('Local model unavailable or timed out') from e
    if r.returncode: raise RuntimeError('Local model failed; check the runtime installation')
    return r.stdout

def speak(text, slow=False):
    with tempfile.TemporaryDirectory(dir=DATA) as d:
        out=Path(d)/'speech.wav'
        args=[RUNTIME/'piper/piper/piper.exe','--model',RUNTIME/'sv_SE-nst-medium.onnx','--output_file',out]
        if slow: args += ['--length_scale','1.35']
        with MODEL_LOCK: execute(args,(text+'\n').encode('utf-8'),60)
        return out.read_bytes()

def transcribe(audio):
    if not audio or len(audio)>MAX_AUDIO: raise ValueError('Audio must be under 12 MB')
    with tempfile.TemporaryDirectory(dir=DATA) as d:
        src=Path(d)/'recording'; wav=Path(d)/'audio.wav'; target=Path(d)/'out'
        src.write_bytes(audio)
        ffmpeg=RUNTIME/'ffmpeg.exe'
        if not ffmpeg.exists():
            try:
                import imageio_ffmpeg
                ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                ffmpeg=shutil.which('ffmpeg')
        if not ffmpeg: raise RuntimeError('Audio decoder unavailable')
        # Stop at 181s and reject longer recordings; decode browser WebM, MP4, Ogg or WAV.
        execute([ffmpeg,'-v','error','-i',src,'-t','181','-ac','1','-ar','16000','-f','wav',wav],timeout=90)
        import wave
        with wave.open(str(wav),'rb') as w:
            if w.getnframes()/w.getframerate()>180: raise ValueError('Recording exceeds 180 seconds')
        with MODEL_LOCK: execute([RUNTIME/'whisper/Release/whisper-cli.exe','-m',RUNTIME/'whisper-base.bin','-f',wav,'-l','sv','-otxt','-of',target,'-nt','-t','4'],timeout=240)
        text=target.with_suffix('.txt').read_text(encoding='utf-8').strip()
        return text

def generate(system, turns, max_tokens=120):
    prompt='<|im_start|>system\n'+system+'<|im_end|>\n'
    recent=[]; remaining=2200
    for t in reversed(turns[-12:]):
        txt=t['text'][:min(1000,remaining)]
        if not txt: break
        recent.append((t['role'],txt)); remaining-=len(txt)
    for role,txt in reversed(recent):
        role='assistant' if role=='assistant' else 'user'
        prompt+=f'<|im_start|>{role}\n{txt}<|im_end|>\n'
    prompt+='<|im_start|>assistant\n'
    if 'qwen35' in MODEL.name.lower(): prompt+='<think>\n\n</think>\n\n'
    with MODEL_LOCK, tempfile.TemporaryDirectory(dir=DATA) as d:
        prompt_file=Path(d)/'prompt.txt'; prompt_file.write_text(prompt,encoding='utf-8')
        raw=execute([RUNTIME/'llama/llama-completion.exe','-m',MODEL,'-f',prompt_file,'-n',str(max_tokens),'-c','1536','-b','128','-ub','64','-t','4','--temp','0.2','--no-display-prompt','-no-cnv'],timeout=240)
    out=raw.decode('utf-8',errors='replace').replace('\ufffd','').split('<|im_end|>')[0].strip()
    out=re.sub(r'\s*\[end of text\]\s*$', '', out).strip()
    if not out: raise RuntimeError('Local model returned an empty reply')
    return out[:1800]

def scene(sid):
    for s in content()['scenarios']:
        if s.get('id')==sid:return s
    raise ValueError('Unknown scenario')

def normalize_selection(curriculum, framework, course_input, study_path):
    """Return a source-backed selection; unknowns remain unknown, never inferred by date."""
    if study_path not in ('','1','2','3'): raise ValueError('Invalid study path')
    entered=course_input.strip().upper()
    selection={'framework_id':framework,'course_input':course_input,'study_path_input':study_path,
               'course':'','study_path':study_path,'status':'unverified' if entered and not framework else 'incomplete'}
    if not framework: return selection
    frame=next((x for x in curriculum.get('frameworks',[]) if x.get('id')==framework),None)
    if not frame: raise ValueError('Unknown SFI framework')
    if not entered: return selection
    courses=frame.get('courses',[]); alias_path=''; is_old_code=False
    item=next((x for x in courses if str(x.get('id','')).upper()==entered),None)
    if not item and framework=='SKOLFS-2017-91-consolidated' and re.fullmatch(r'[123][ABCD]',entered):
        alias_path=entered[0]; item=next((x for x in courses if str(x.get('id','')).upper()==entered[1:]),None)
    if not item:
        item=next((x for x in courses if entered in [str(code).upper() for code in x.get('course_codes',[])]),None)
        is_old_code=bool(item) and framework=='SKOLFS-2017-91-consolidated'
    if not item: raise ValueError('Course is not valid for this framework')
    allowed=[str(x) for x in item.get('study_paths',[])]
    if is_old_code and study_path:
        raise ValueError('For this course code, choose the course letter to specify a study path')
    if alias_path and study_path and alias_path!=study_path: raise ValueError('Course and study path do not match')
    resolved=alias_path or study_path
    if not resolved and len(allowed)==1: resolved=allowed[0]
    if resolved and resolved not in allowed: raise ValueError('Course and study path do not match')
    selection.update(course=item['id'],study_path=resolved,status='validated')
    return selection

def character(s):
    sc=s.get('snapshot',{}).get('scenario') or scene(s['scenario_id'])
    system=('Du spelar en person i ett svenskt rollspel. Svara med en eller två korta, naturliga svenska meningar. Hitta inte på namn på eleven. Rätta inte och ge inga råd om språket. '
            'Stay in character and react to the learner; ask at most one relevant follow-up. No markdown. '
            'Scenario: '+str(sc.get('context_prompt',''))+' Scene goal: '+str(sc.get('goal',''))+' Dialogue direction: '+str(sc.get('dialogue',{}).get('system_instructions',''))+' Scene beats: '+json.dumps(sc.get('dialogue',{}).get('beats',[]),ensure_ascii=False)+' Character: '+json.dumps(sc.get('character',{}),ensure_ascii=False)+
            ' Learner context: '+s.get('context','')+' Feeling: '+s.get('feeling',''))
    return generate(system,s['turns'],80)

def coach(s):
    if not any(t['role']=='user' for t in s['turns']): raise ValueError('Practise a turn first')
    system=('You are an encouraging Swedish learning coach. In English, give brief provisional feedback based only on the transcript: what the learner communicated and one specific next practice suggestion. Mention if a hint was used. Never judge pronunciation, assign grades, infer course placement or claim official assessment. Transcript may contain speech recognition errors.')
    notes=[{'role':'user','text':json.dumps([{'role':t['role'],'text':t['text'][:200],'input_mode':t.get('input_mode'),'help_used':t.get('help_used',[])} for t in s['turns'][-6:]],ensure_ascii=False)}]
    result=generate(system,notes,160)
    if re.search(r'(?i)pronounc|uttal|accent|intonation|\bsound(?:s|ed|ing)?\b|\bfluen\w*|\brhythm\b|\bvowel\w*|\bconsonant\w*|\barticulat\w*|speech sounds|spoken fluency|\b(?:grade|graded|betyg|placement|pass(?:ed)? the (?:exam|course))\b',result):
        raise RuntimeError('Feedback was withheld because it included an unsupported assessment. Try again.')
    return result

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(20)
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json; charset=utf-8'):
        b=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(b)
    def body(self,limit=65536):
        try: n=int(self.headers.get('Content-Length','0'))
        except ValueError: raise ValueError('Invalid length')
        if n<0 or n>limit: raise ValueError('Request too large')
        deadline=time.monotonic()+45; chunks=[]; remaining=n
        while remaining:
            left=deadline-time.monotonic()
            if left<=0: raise ValueError('Request body timed out')
            self.connection.settimeout(min(10,left))
            try: part=self.rfile.read1(min(65536,remaining))
            except TimeoutError: raise ValueError('Request body timed out')
            if not part: raise ValueError('Incomplete request body')
            chunks.append(part); remaining-=len(part)
        return b''.join(chunks)
    def obj(self):
        if self.headers.get('Content-Type','').split(';',1)[0].strip().lower() != 'application/json':
            raise ValueError('Content-Type must be application/json')
        try:
            v=json.loads(self.body())
            if not isinstance(v,dict): raise ValueError()
            return v
        except (json.JSONDecodeError,UnicodeDecodeError): raise ValueError('Invalid JSON')
    def do_GET(self): self.dispatch('GET')
    def do_POST(self): self.dispatch('POST')
    def do_DELETE(self): self.dispatch('DELETE')
    def dispatch(self,method):
        try:
            port=self.server.server_address[1]
            allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
            if self.headers.get('Host','').lower() not in allowed:
                return self.send(403,{'error':'Invalid host'})
            origin=self.headers.get('Origin')
            if method in ('POST','DELETE') and origin and origin.lower() not in {f'http://{host}' for host in allowed}:
                return self.send(403,{'error':'Invalid origin'})
            if method in ('POST','DELETE') and urlsplit(self.path).path.startswith('/api/sessions'):
                with MUTATION_LOCK: self.route(method)
            else: self.route(method)
        except ValueError as e: self.send(400,{'error':str(e) or 'Invalid request'})
        except RuntimeError as e: self.send(503,{'error':str(e)})
        except OSError: self.send(503,{'error':'Local service unavailable'})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception: self.send(500,{'error':'Unexpected server error'})
    def route(self,method):
        path=urlsplit(self.path).path.rstrip('/') or '/'
        if method=='GET' and path=='/health': return self.send(200,{'ok':True,'instance':os.environ.get('LAB_INSTANCE_ID','')})
        if method=='GET' and path=='/api/content': return self.send(200,content())
        if method=='GET' and path=='/api/sessions': return self.send(200,{'sessions':all_sessions()})
        if method=='GET' and path=='/api/export': return self.send(200,{'version':1,'sessions':all_sessions()})
        if method=='DELETE' and path=='/api/sessions':
            with connect() as c:c.execute('DELETE FROM sessions')
            return self.send(200,{'ok':True})
        if method=='POST' and path=='/api/sessions':
            o=self.obj(); sc=scene(bounded(o.get('scenario_id',''),100)); now=time.time()
            co=content(); scenario_data=json.loads((BASE/'content'/'scenarios.json').read_text(encoding='utf-8')); curr=co['curriculum']
            framework=bounded(o.get('framework_id',''),100); course_input=bounded(o.get('course',''),80); study_path=bounded(str(o.get('study_path','')),20)
            selection=normalize_selection(curr,framework,course_input,study_path)
            course=selection['course']; study_path=selection['study_path']
            criteria=[x for x in curr.get('criteria',[]) if x.get('framework_id')==framework and str(x.get('course','')).upper()==course.upper() and (not study_path or int(study_path) in x.get('study_paths',[]))] if framework and course else []
            ids={x['id'] for x in criteria}; links=[x for x in sc.get('criterion_links',[]) if x.get('criterion_id') in ids and x.get('framework_id')==framework]
            s={'id':uuid.uuid4().hex,'scenario_id':sc['id'],'framework_id':framework,'course':course,'study_path':study_path,'support':o.get('support',[]),'context':bounded(o.get('context',''),500),'feeling':bounded(o.get('feeling',''),100),'created_at':now,'turns':[{'role':'assistant','text':sc.get('opening_sv',''),'created_at':now}],'evidence':[],'phrases':[],'coaching':[],'snapshot':{'scenario_content_version':scenario_data.get('content_version'),'curriculum_content_version':curr.get('content_version'),'selection':selection,'scenario':sc,'criteria':criteria,'criterion_links':links}}
            if not isinstance(s['support'],list) or len(s['support'])>20: raise ValueError('Invalid support')
            save(s); return self.send(201,{'session':s})
        if method=='POST' and path=='/api/transcribe':
            ct=self.headers.get('Content-Type','').split(';',1)[0].strip().lower()
            if not (ct.startswith('audio/') or ct in ('application/octet-stream','video/webm','video/mp4')): raise ValueError('Expected recorded audio')
            return self.send(200,{'text':transcribe(self.body(MAX_AUDIO))})
        if method=='POST' and path=='/api/speech':
            o=self.obj(); t=bounded(o.get('text',''),1000)
            if not t: raise ValueError('Text required')
            return self.send(200,speak(t,bool(o.get('slow'))),'audio/wav')
        m=re.fullmatch(r'/api/sessions/([a-f0-9]{32})(?:/(turn|coach|evidence|phrases))?',path)
        if m:
            sid,action=m.groups(); s=get_session(sid)
            if method=='GET' and not action: return self.send(200,{'session':s})
            if method=='DELETE' and not action:
                with connect() as c:c.execute('DELETE FROM sessions WHERE id=?',(sid,))
                return self.send(200,{'ok':True})
            if method=='POST' and action=='turn':
                o=self.obj(); t=bounded(o.get('text',''),2000); mode=o.get('input_mode','text'); help_used=o.get('help_used',[]); request_id=bounded(o.get('request_id',''),100)
                if request_id:
                    prev=next((x for x in s['turns'] if x.get('role')=='assistant' and x.get('request_id')==request_id),None)
                    if prev: return self.send(200,{'session':s,'reply':prev['text']})
                if not t or mode not in ('text','voice') or not isinstance(help_used,list) or len(help_used)>20 or not isinstance(o.get('transcript_edited',False),bool): raise ValueError('Invalid turn')
                if len(s['turns'])>=100: raise ValueError('Session turn limit reached')
                s['turns'].append({'role':'user','text':t,'input_mode':mode,'transcript_edited':bool(o.get('transcript_edited',False)) if mode=='voice' else False,'help_used':help_used,'request_id':request_id,'evidence_state':'practised','created_at':time.time()})
                reply=character(s); s['turns'].append({'role':'assistant','text':reply,'request_id':request_id,'created_at':time.time()}); save(s)
                return self.send(200,{'session':s,'reply':reply})
            if method=='POST' and action=='coach':
                o=self.obj(); request_id=bounded(o.get('request_id',''),100)
                prev=next((x for x in s.get('coaching',[]) if request_id and x.get('request_id')==request_id),None)
                if prev: return self.send(200,{'session':s,'feedback':prev['feedback']})
                feedback=coach(s); s.setdefault('coaching',[]).append({'feedback':feedback,'request_id':request_id,'created_at':time.time(),'basis':'transcript','based_on_turn_count':len(s['turns']),'status':'provisional'}); save(s)
                return self.send(200,{'session':s,'feedback':feedback})
            if method=='POST' and action=='evidence':
                o=self.obj(); activity=o.get('activity'); response=bounded(o.get('response',''),4000); used=o.get('help_used',[]); request_id=bounded(o.get('request_id',''),100); mode=o.get('input_mode','text')
                if request_id and any(x.get('request_id')==request_id for x in s['evidence']): return self.send(200,{'session':s})
                if activity not in ('listening','reading','writing','recall','dialogue_summary','writing_copy_extension') or mode not in ('text','voice') or not response or not isinstance(used,list) or len(used)>20: raise ValueError('Invalid evidence')
                s['evidence'].append({'activity':activity,'response':response,'help_used':used,'request_id':request_id,'evidence_state':'practised','input_mode':mode,'created_at':time.time()}); save(s); return self.send(200,{'session':s})
            if method=='POST' and action=='phrases':
                o=self.obj(); sv=bounded(o.get('sv',''),500); en=bounded(o.get('en',''),500)
                if not sv: raise ValueError('Phrase required')
                s['phrases'].append({'sv':sv,'en':en,'created_at':time.time()}); save(s); return self.send(200,{'session':s})
        if method=='GET' and not path.startswith('/api/'):
            name='index.html' if path=='/' else path.lstrip('/')
            if '/' in name or '\\' in name or name.startswith('.'): return self.send(404,{'error':'Not found'})
            f=BASE/'web'/name
            if f.is_file():
                import mimetypes
                return self.send(200,f.read_bytes(),mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
        return self.send(404,{'error':'Not found'})

if __name__=='__main__':
    server=ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler)
    server.serve_forever()
