"""Sanitized resource probe for an isolated, networkless candidate container.

It creates one disposable account and deletes only that account and its invite.
It never establishes model quality or substitutes for independent acceptance.
"""
import hashlib,json,os,secrets,signal,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path

if os.getenv('BP5_STAGING_PROBE')!='1' or os.getenv('LAB_DATA_DIR')!='/data' or os.getenv('BP5_PUBLIC_ORIGIN')!='http://127.0.0.1:8788':
    raise SystemExit('Explicit isolated staging configuration required')
token=os.getenv('BP5_STAGING_PROBE_TOKEN','');marker=Path('/data/.bp5-isolated-language-staging')
if not 24<=len(token)<=128 or not marker.is_file() or marker.is_symlink() or marker.read_text(encoding='utf8').strip()!=token:
    raise SystemExit('Isolated staging marker required')
if os.getenv('BP5_SEMANTIC_REQUIRED')!='1':raise SystemExit('Semantic candidate must be required')
sys.path.insert(0,'/app/server')
from smoke_http import Client,start,require
from language_context import current_offer
from language_runtime_inventory import record

CGROUP=Path('/sys/fs/cgroup')
def number(name):
    try:
        value=(CGROUP/name).read_text().strip()
        return int(value) if value!='max' else None
    except (OSError,ValueError):return None

def mapping(name):
    try:return {a:int(b) for a,b in (line.split() for line in (CGROUP/name).read_text().splitlines())}
    except (OSError,ValueError):return {}

def binding_receipt():
    manifest=Path('/app/LANGUAGE_CHECKER_MANIFEST.json');library=Path('/app/content/library.json');vocab=Path('/app/server/swedish_support_vocabulary.json')
    if any(not p.is_file() or p.is_symlink() for p in (manifest,library,vocab)) or manifest.stat().st_size>65536:raise ValueError('Invalid binding')
    raw=manifest.read_bytes();document=json.loads(raw);configuration=document['adapter']['configuration'];items=document['artifacts'];artifacts={item['path']:item['sha256'] for item in items}
    if len(artifacts)!=len(items):raise ValueError('Invalid binding')
    source_sha=hashlib.sha256(library.read_bytes()).hexdigest();vocab_sha=hashlib.sha256(vocab.read_bytes()).hexdigest()
    if source_sha!=configuration['library_sha256'] or vocab_sha!=configuration['vocabulary_sha256']:raise ValueError('Invalid binding')
    return {'manifest_sha256':hashlib.sha256(raw).hexdigest(),'library_sha256':source_sha,'vocabulary_sha256':vocab_sha,'model_sha256':artifacts[configuration['model']],'tokenizer_sha256':artifacts[configuration['tokenizer']],'language_model_sha256':artifacts[configuration['language_model']],'checkpoint_id':configuration['checkpoint_id']}

def worker_pid():
    found=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        try:argv=(entry/'cmdline').read_bytes().split(b'\0')
        except OSError:continue
        if len(argv)>=3 and argv[1:3]==[b'-I',b'/app/server/language_worker.py']:found.append(int(entry.name))
    if len(found)!=1:raise ValueError('Expected exactly one isolated candidate worker')
    return found[0]

def worker_native_inventory(pid):
    paths=set()
    for line in Path(f'/proc/{pid}/maps').read_text(encoding='utf8').splitlines():
        fields=line.split(None,5)
        if len(fields)==6 and fields[5].startswith('/') and '.so' in Path(fields[5]).name:
            path=Path(fields[5])
            if not path.is_file():raise ValueError('Mapped library is unavailable')
            paths.add(str(path.resolve(strict=True)))
    if not paths or len(paths)>256:raise ValueError('Invalid worker native inventory')
    return [record(p) for p in sorted(paths)]

def long_reply(mission,step,turns):
    from tokenizers import Tokenizer
    config=json.loads(Path('/app/LANGUAGE_CHECKER_MANIFEST.json').read_text(encoding='utf8'))['adapter']['configuration']
    root=Path(os.environ['BP5_LANGUAGE_ARTIFACT_ROOT']).resolve(strict=True)
    tokenizer=Tokenizer.from_file(str(root/config['tokenizer']));tokenizer.no_truncation()
    offer=current_offer(mission,step,turns);hypotheses=['Svaret betyder: '+(i.get('meaning_sv') or i['examples_sv'][0]) for i in step['intents']]
    for repeat in range(1,300):
        text='Jag tycker att det är viktigt. '*repeat+'Jag vill inte göra det.'
        if len(text)>2000:break
        premise=f"Erbjudande: {offer}\nFråga: {step['prompt_sv']}\nSvar: {text}"
        counts=[len(tokenizer.encode(premise,h).ids) for h in hypotheses]
        if min(counts)>=490 and max(counts)<=512:return text,counts
    raise ValueError('Cannot construct bounded near-limit multi-intent probe')

class Sampler:
    def __init__(self):self.stop=threading.Event();self.peak=0;self.thread=threading.Thread(target=self.sample,daemon=True)
    def sample(self):
        while not self.stop.wait(.2):self.peak=max(self.peak,number('memory.current') or 0)
    def __enter__(self):self.peak=number('memory.current') or 0;self.thread.start();return self
    def __exit__(self,*args):self.stop.set();self.thread.join(3)

def main():
    cap=number('memory.max');peak=number('memory.peak')
    try:
        expected=int(os.environ['BP5_STAGING_EXPECTED_MEMORY_BYTES']);quota,period=(CGROUP/'cpu.max').read_text().split();cpu_limit=int(quota)/int(period)
    except (KeyError,OSError,ValueError,ZeroDivisionError):raise SystemExit('Bounded cgroup v2 limits are required')
    if cap!=expected or cap<=0 or cap>3*1024**3 or peak is None or not 0<cpu_limit<=2 or 'oom_kill' not in mapping('memory.events') or 'usage_usec' not in mapping('cpu.stat'):raise SystemExit('Staging cgroup limits do not match')
    client=Client();created=False;result={'status':'incomplete','measurement_only':True,'physical_device_tested':False,'candidate_quality_evaluated':False,'memory_max_bytes':cap,'cpu_limit':cpu_limit,'samples':{},'checks':{}};before=mapping('memory.events');cpu_before=mapping('cpu.stat');failure=None;clean=False
    try:
        with Sampler() as sampler:
            result['binding']=binding_receipt();result['samples']['initial_bytes']=number('memory.current')
            start_time=time.monotonic();status,body,_=client.request('GET','/ready',timeout=120);require(status==200 and body.get('ok') is True and body.get('semantic_required') is True and body.get('semantic') is True,'candidate readiness')
            result['checks']['ready_seconds']=round(time.monotonic()-start_time,3);result['samples']['ready_bytes']=number('memory.current')
            client.register();created=True;status,library,_=client.request('GET','/api/library');require(status==200,'library');situations=library.get('situations',[]);mission=next(m for s in situations for m in s['missions'] if any(len(x['intents'])>=2 for x in m['steps']));session=start(client,mission['id'])
            setup_inference_seconds=0
            for _ in range(12):
                step=next(s for s in mission['steps'] if s['id']==session['current_step'])
                if len(step['intents'])>=2:break
                intent=step['intents'][0];started=time.monotonic();status,body,_=client.request('POST','/api/missions/'+session['id']+'/turn',{'request_id':str(uuid.uuid4()),'text':intent['examples_sv'][0],'input_mode':'text','transcript_edited':False,'help_used':[]},timeout=180);setup_inference_seconds+=time.monotonic()-started;require(status==200,'setup turn');session=body['session']
                if not body.get('matched'):
                    original=session['turns'][-2];status,body,_=client.request('POST','/api/missions/'+session['id']+'/clarify',{'request_id':str(uuid.uuid4()),'step_id':step['id'],'intent_id':intent['id'],'turn_index':len(session['turns'])-2,'turn_id':original['turn_id']});require(status==200,'setup clarification');session=body['session']
                require(session['status']=='in_progress','setup reached terminal')
            else:raise ValueError('No reachable multi-intent step')
            utterance,counts=long_reply(mission,step,session['turns']);result['checks']['semantic_pair_tokens']=counts;result['checks']['semantic_intents']=len(counts);result['checks']['input_characters']=len(utterance)
            old_pid=worker_pid();os.kill(old_pid,signal.SIGKILL);start_time=time.monotonic();status,body,_=client.request('GET','/ready',timeout=120);require(status==200 and body.get('semantic') is True and worker_pid()!=old_pid,'worker restart');result['checks']['worker_restart_seconds']=round(time.monotonic()-start_time,3);result['worker_native_libraries']=worker_native_inventory(worker_pid())
            # The public budget imposes cooldown after setup inference. Let the
            # disposable account refill instead of modifying its database row.
            delay=min(300,setup_inference_seconds*2)+120;time.sleep(delay);result['checks']['budget_refill_wait_seconds']=round(delay,3)
            start_time=time.monotonic();status,wav,_=client.request('POST','/api/speech',{'text':'Hej, jag vill ha en kopp kaffe, tack.','slow':False},extra={'X-Audio-Job':str(uuid.uuid4())},timeout=120);require(status==200 and isinstance(wav,bytes) and wav.startswith(b'RIFF'),'synthetic speech');result['checks']['speech_seconds']=round(time.monotonic()-start_time,3);result['samples']['speech_complete_bytes']=number('memory.current')
            with tempfile.TemporaryDirectory(prefix='bp5-language-probe-',dir='/tmp') as d:
                source=Path(d)/'speech.wav';audio=Path(d)/'speech.m4a';source.write_bytes(wav)
                converted=subprocess.run([os.getenv('BP5_FFMPEG','ffmpeg'),'-v','error','-y','-i',str(source),str(audio)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60,check=False);require(converted.returncode==0 and audio.is_file(),'audio conversion');recording=audio.read_bytes()
                audio_client=Client();audio_client.cookies=dict(client.cookies);audio_client.csrf=client.csrf;results={};barrier=threading.Barrier(3)
                def transcribe():
                    barrier.wait(timeout=10);t=time.monotonic()
                    try:status,body,_=audio_client.request('POST','/api/transcribe',recording,'audio/mp4',extra={'X-Audio-Job':str(uuid.uuid4())},timeout=240);end=time.monotonic();results['audio']=(status,round(end-t,3),isinstance(body,dict) and isinstance(body.get('text'),str) and bool(body['text'].strip()),t,end)
                    except Exception:results['audio']=('error',round(time.monotonic()-t,3),False)
                def semantic():
                    barrier.wait(timeout=10);t=time.monotonic()
                    try:status,body,_=client.request('POST','/api/missions/'+session['id']+'/turn',{'request_id':str(uuid.uuid4()),'text':utterance,'input_mode':'text','transcript_edited':False,'help_used':[]},timeout=180);end=time.monotonic();results['semantic']=(status,round(end-t,3),isinstance(body,dict) and body.get('match_source')=='semantic',t,end)
                    except Exception:results['semantic']=('error',round(time.monotonic()-t,3),False)
                threads=[threading.Thread(target=transcribe,daemon=True),threading.Thread(target=semantic,daemon=True)]
                for thread in threads:thread.start()
                barrier.wait(timeout=10)
                for thread in threads:thread.join(245)
                require(not any(t.is_alive() for t in threads),'probe deadline')
                result['checks']['audio_http_status']=results.get('audio',('missing',))[0];result['checks']['semantic_http_status']=results.get('semantic',('missing',))[0]
                require(results.get('audio',(None,None,False))[0]==200 and results['audio'][2],'synthetic transcription');require(results.get('semantic',(None,None,False))[0]==200 and results['semantic'][2],'semantic route')
                require(max(results['audio'][3],results['semantic'][3])<min(results['audio'][4],results['semantic'][4]),'request overlap')
                result['checks']['audio_seconds']=results['audio'][1];result['checks']['semantic_seconds']=results['semantic'][1]
            require(binding_receipt()==result['binding'],'candidate binding changed');result['samples']['post_request_bytes']=number('memory.current');result['samples']['sampled_peak_bytes']=sampler.peak;result['samples']['cgroup_peak_bytes']=number('memory.peak');result['status']='measurement_complete_not_acceptance'
    except Exception as exc:failure=type(exc).__name__;result['error']='probe failed'
    finally:
        try:clean=client.cleanup()
        except Exception:clean=False
        after=mapping('memory.events');result['checks']['disposable_account_deleted']=bool(clean);result['memory_events_before']=before;result['memory_events_after']=after;result['cpu_before']=cpu_before;result['cpu_after']=mapping('cpu.stat')
        if failure or not clean or after.get('oom_kill',0)>before.get('oom_kill',0):result['status']='failed'
        print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='measurement_complete_not_acceptance' else 1
if __name__=='__main__':raise SystemExit(main())
