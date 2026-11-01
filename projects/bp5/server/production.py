"""BP5 authenticated, authored-mission service. Run with uvicorn, single worker."""
import asyncio, hmac, json, os, re, secrets, shutil, subprocess, tempfile, threading, time, uuid, wave
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator
import production_store as st
from app import normalize_selection

st.init()
st.cleanup_abandoned_audio()
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
ORIGIN=os.getenv('BP5_PUBLIC_ORIGIN','http://127.0.0.1:8788').rstrip('/')
COOKIE_PATH=os.getenv('BP5_COOKIE_PATH','/')
SECURE=os.getenv('BP5_SECURE_COOKIE','1')=='1'
INVITE_TTL=max(60,min(int(os.getenv('BP5_INVITATION_TTL_SECONDS','604800')),2592000))
with st.connect() as c:
 c.execute('DELETE FROM invitations WHERE consumed IS NULL AND created<?',(time.time()-INVITE_TTL,))
 c.execute('DELETE FROM auth_sessions WHERE expires<=?',(time.time(),))
COOKIE='bp5_session'
AUDIO_LOCK=threading.BoundedSemaphore(1)
AUDIO_UPLOAD_LOCK=threading.BoundedSemaphore(1)
HISTORY_STREAM_LOCK=threading.BoundedSemaphore(2)
PASSWORD_LOCK=threading.BoundedSemaphore(2)
MAX_RATE_ROWS=50000
MAX_CREATION_REQUESTS=10000
MAX_AUTH_SESSIONS=10
MAX_MISSION_CREATIONS_PER_HOUR=60
MAX_AUDIO=12*1024*1024
AUDIO_FORMATS={'audio/wav':'wav','audio/x-wav':'wav','audio/wave':'wav','audio/webm':'matroska','video/webm':'matroska','audio/mp4':'mov','audio/x-m4a':'mov','video/mp4':'mov','audio/ogg':'ogg','audio/mpeg':'mp3'}
CREATE_NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)

class Model(BaseModel): model_config=ConfigDict(extra='forbid',strict=True)
class Login(Model): username:StrictStr=Field(min_length=3,max_length=64); password:StrictStr=Field(min_length=1,max_length=256)
class Register(Login): invite:StrictStr=Field(min_length=16,max_length=256)
class Recover(Model): username:StrictStr=Field(min_length=3,max_length=64); recovery_code:StrictStr=Field(min_length=16,max_length=128); new_password:StrictStr=Field(min_length=12,max_length=256)
class Confirm(Model): password:StrictStr=Field(min_length=1,max_length=256)
class Profile(Model): framework_id:StrictStr=Field(default='',max_length=100); course:StrictStr=Field(default='',max_length=80); study_path:StrictStr=Field(default='',max_length=20)
class Start(Profile): mission_id:StrictStr=Field(min_length=1,max_length=120); request_id:StrictStr=Field(min_length=1,max_length=100)
class Action(Model): request_id:StrictStr=Field(min_length=1,max_length=100)
class SupportAction(Action):
 help_used:list[StrictStr]=Field(default_factory=list,max_length=20)
 @field_validator('help_used')
 @classmethod
 def check_support(cls,v):
  if any(not x.strip() or len(x)>100 for x in v):raise ValueError('Invalid support')
  return v
class Turn(SupportAction): text:StrictStr=Field(min_length=1,max_length=2000); input_mode:StrictStr=Field(default='text',pattern='^(text|voice)$'); transcript_edited:StrictBool=False
class Clarify(Action): step_id:StrictStr=Field(min_length=1,max_length=120); intent_id:StrictStr=Field(min_length=1,max_length=120); turn_index:StrictInt=Field(ge=0,le=199); turn_id:StrictStr=Field(min_length=1,max_length=100)
class Evidence(SupportAction): activity:StrictStr=Field(pattern='^(listening|reading|writing|recall)$'); response:StrictStr=Field(min_length=1,max_length=4000)
class Phrase(Action): sv:StrictStr=Field(min_length=1,max_length=500); en:StrictStr=Field(default='',max_length=500)
class Speech(Model): text:StrictStr=Field(min_length=1,max_length=1000); slow:StrictBool=False

@app.middleware('http')
async def protection(request:Request, call_next):
 path=request.url.path
 allowed=set(os.getenv('BP5_ALLOWED_HOSTS','127.0.0.1:8788,localhost:8788').lower().split(','))
 if request.headers.get('host','').lower() not in allowed:return JSONResponse({'error':'Invalid host'},status_code=403)
 if request.method in ('POST','PATCH','DELETE'):
  if request.headers.get('origin')!=ORIGIN: return JSONResponse({'error':'Request rejected'},status_code=403)
  if request.method!='DELETE':
   ct=request.headers.get('content-type','').split(';')[0].strip().lower()
   if path=='/api/transcribe':
    if ct not in AUDIO_FORMATS:return JSONResponse({'error':'Unsupported recording format'},status_code=415)
   elif ct!='application/json': return JSONResponse({'error':'Expected JSON'},status_code=415)
  limit=MAX_AUDIO if path=='/api/transcribe' else 65536
  if path=='/api/transcribe':
   try:auth(request,True)
   except HTTPException as exc:return JSONResponse({'error':str(exc.detail)},status_code=exc.status_code)
  try:
   if request.headers.get('transfer-encoding'):return JSONResponse({'error':'Content length required'},status_code=411)
   length=request.headers.get('content-length')
   if length is None and request.method!='DELETE':return JSONResponse({'error':'Content length required'},status_code=411)
   n=int(length or '0')
   if n<0 or n>limit:return JSONResponse({'error':'Request too large'},status_code=413)
   upload_locked=path=='/api/transcribe'
   if upload_locked and not AUDIO_UPLOAD_LOCK.acquire(blocking=False):return JSONResponse({'error':'Audio is busy; try again'},status_code=429)
   try:body=await asyncio.wait_for(request.body(),timeout=45)
   finally:
    if upload_locked:AUDIO_UPLOAD_LOCK.release()
   if len(body)>limit:return JSONResponse({'error':'Request too large'},status_code=413)
   if len(body)!=n:return JSONResponse({'error':'Invalid request'},status_code=400)
  except (ValueError,asyncio.TimeoutError):return JSONResponse({'error':'Invalid request'},status_code=400)
 response=await call_next(request)
 response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'; response.headers['Referrer-Policy']='no-referrer';response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
 return response

@app.exception_handler(RequestValidationError)
async def invalid_schema(request,exc):return JSONResponse({'error':'Invalid request'},status_code=400)
@app.exception_handler(HTTPException)
async def http_error(request,exc):return JSONResponse({'error':str(exc.detail)},status_code=exc.status_code)
@app.exception_handler(ValueError)
async def bad_value(request,exc):return JSONResponse({'error':str(exc) or 'Invalid request'},status_code=400)
@app.exception_handler(LookupError)
async def missing(request,exc):return JSONResponse({'error':'Not found'},status_code=404)
@app.exception_handler(OSError)
async def os_error(request,exc):return JSONResponse({'error':'Service unavailable'},status_code=503)
@app.exception_handler(RuntimeError)
async def unavailable(request,exc):return JSONResponse({'error':'Service unavailable'},status_code=503)

def record_rate(c,key,limit=8,window=900,subject=''):
 now=time.time();c.execute('DELETE FROM attempts WHERE occurred<?',(now-86400,));n=c.execute('SELECT count(*) FROM attempts WHERE key=? AND occurred>?',(st.digest(key),now-window)).fetchone()[0]
 if n>=limit or c.execute('SELECT count(*) FROM attempts').fetchone()[0]>=MAX_RATE_ROWS:raise HTTPException(429,'Try again later')
 c.execute('INSERT INTO attempts(key,occurred,subject) VALUES(?,?,?)',(st.digest(key),now,st.digest(subject) if subject else None))
def rate(key,limit=8,window=900,subject=''):
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE')
  try:record_rate(c,key,limit,window,subject);c.execute('COMMIT')
  except BaseException:c.execute('ROLLBACK');raise
def password_hash(value):
 with PASSWORD_LOCK:return st.hash_password(value)
def password_verify(value,encoded):
 with PASSWORD_LOCK:return st.verify_password(value,encoded)

def username(s):
 u=s.strip().casefold()
 if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,63}',u):raise ValueError('Username must use 3–64 letters, numbers, dot, dash or underscore')
 return u
def valid_password(p):
 if not 12<=len(p)<=256 or len(p.encode('utf-8'))>1024:raise ValueError('Password must be 12–256 characters')
def set_cookie(response,token):response.set_cookie(COOKIE,token,max_age=st.MAX_SESSION_SECONDS,httponly=True,secure=SECURE,samesite='strict',path=COOKIE_PATH)
def new_session(c,uid):
 token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);now=time.time()
 c.execute('DELETE FROM auth_sessions WHERE expires<=?',(now,))
 c.execute('DELETE FROM auth_sessions WHERE token_hash IN (SELECT token_hash FROM auth_sessions WHERE user_id=? ORDER BY expires DESC,rowid DESC LIMIT -1 OFFSET ?)',(uid,MAX_AUTH_SESSIONS-1))
 c.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',(st.digest(token),uid,st.digest(csrf),time.time()+st.MAX_SESSION_SECONDS));return token,csrf
def auth(request,mutation=False):
 token=request.cookies.get(COOKIE,'')
 if len(token)>128 or not token:raise HTTPException(401,'Sign in required')
 with st.connect() as c:row=c.execute('SELECT s.user_id,s.csrf_hash,u.username FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(st.digest(token),time.time())).fetchone()
 if not row:raise HTTPException(401,'Sign in required')
 if mutation:
  csrf=request.headers.get('x-csrf-token','')
  if not csrf or len(csrf)>128 or not hmac.compare_digest(st.digest(csrf),row['csrf_hash']):raise HTTPException(403,'Request rejected')
 return dict(row)
def csrf_for_session(request):
 # CSRF secret is held in an HttpOnly-independent, strict cookie so a refresh can recover it.
 return request.cookies.get('bp5_csrf','')
def set_csrf(response,csrf): response.set_cookie('bp5_csrf',csrf,max_age=st.MAX_SESSION_SECONDS,httponly=False,secure=SECURE,samesite='strict',path=COOKIE_PATH)

@app.get('/health')
def health():return {'ok':True,'instance':os.getenv('LAB_INSTANCE_ID','')}
@app.get('/ready')
def readiness():
 try:
  lib=st.get_library();library_ok=st.library_ready(lib)
 except (OSError,ValueError,RuntimeError,TypeError):library_ok=False
 def exe(name,default):return bool(shutil.which(os.getenv(name,default)))
 def model(name,default):return Path(os.getenv(name,default)).is_file()
 voice_model=os.getenv('BP5_PIPER_MODEL','sv_SE-nst-medium.onnx')
 audio_ok=exe('BP5_FFMPEG','ffmpeg') and exe('BP5_WHISPER_BIN','whisper-cli') and model('BP5_WHISPER_MODEL','whisper-base.bin') and exe('BP5_PIPER_BIN','piper') and Path(voice_model).is_file() and Path(voice_model+'.json').is_file()
 return JSONResponse({'ok':bool(library_ok and audio_ok),'library':library_ok,'audio':audio_ok},status_code=200 if library_ok and audio_ok else 503)
@app.get('/api/config')
def public_config():
 return {'support_contact':os.getenv('BP5_SUPPORT_CONTACT','')[:300],'privacy_contact':os.getenv('BP5_PRIVACY_CONTACT','')[:300]}
@app.get('/api/auth/session')
def session_info(request:Request):
 try:
  a=auth(request);csrf=csrf_for_session(request)
  if not csrf or not hmac.compare_digest(st.digest(csrf),a['csrf_hash']):return {'authenticated':False}
  return {'authenticated':True,'user':{'id':a['user_id'],'username':a['username']},'csrf':csrf}
 except HTTPException:return {'authenticated':False}
@app.post('/api/auth/register')
def register(body:Register,request:Request,response:Response):
 rate('register:'+str(request.client.host),10);u=username(body.username);valid_password(body.password);pw=password_hash(body.password);codes=[secrets.token_urlsafe(18) for _ in range(8)];uid=uuid.uuid4().hex
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE');inv=c.execute('SELECT consumed,created FROM invitations WHERE token_hash=?',(st.digest(body.invite),)).fetchone()
  if not inv or inv['consumed'] is not None or inv['created']<time.time()-INVITE_TTL or c.execute('SELECT 1 FROM users WHERE username=?',(u,)).fetchone():c.execute('ROLLBACK');raise HTTPException(400,'Cannot register with those details')
  c.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,u,pw,'{}',time.time()));c.execute('UPDATE invitations SET consumed=? WHERE token_hash=?',(time.time(),st.digest(body.invite)))
  c.executemany('INSERT INTO recovery_codes VALUES(?,?)',[(st.digest(x),uid) for x in codes]);token,csrf=new_session(c,uid);c.execute('COMMIT')
 set_cookie(response,token);set_csrf(response,csrf);return {'user':{'id':uid,'username':u},'csrf':csrf,'recovery_codes':codes}
@app.post('/api/auth/login')
def login(body:Login,request:Request,response:Response):
 u=username(body.username);rate('login-ip:'+str(request.client.host),40);rate('login:'+str(request.client.host)+':'+u,subject=u)
 with st.connect() as c:row=c.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone()
 # Always perform a scrypt derivation for unknown usernames to reduce enumeration.
 encoded=row['password'] if row else 'scrypt$32768$8$1$'+'00'*16+'$'+'00'*32
 if not password_verify(body.password,encoded) or not row:raise HTTPException(401,'Invalid credentials')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE');current=c.execute('SELECT password FROM users WHERE id=?',(row['id'],)).fetchone()
  if not current or not hmac.compare_digest(current['password'],encoded):
   c.execute('ROLLBACK');raise HTTPException(401,'Invalid credentials')
  token,csrf=new_session(c,row['id']);c.execute('COMMIT')
 set_cookie(response,token);set_csrf(response,csrf);return {'user':{'id':row['id'],'username':u},'csrf':csrf}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response):
 auth(request,True)
 with st.connect() as c:c.execute('DELETE FROM auth_sessions WHERE token_hash=?',(st.digest(request.cookies[COOKIE]),))
 response.delete_cookie(COOKIE,path=COOKIE_PATH);response.delete_cookie('bp5_csrf',path=COOKIE_PATH);return {'ok':True}
@app.post('/api/auth/recover')
def recover(body:Recover,request:Request):
 u=username(body.username);valid_password(body.new_password);rate('recover-ip:'+str(request.client.host),30);rate('recover:'+str(request.client.host)+':'+u,6,subject=u);pw=password_hash(body.new_password)
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT id FROM users WHERE username=?',(u,)).fetchone();uid=row['id'] if row else ''
  hit=c.execute('SELECT 1 FROM recovery_codes WHERE code_hash=? AND user_id=?',(st.digest(body.recovery_code),uid)).fetchone()
  if not hit:c.execute('ROLLBACK');raise HTTPException(400,'Recovery details were not accepted')
  c.execute('DELETE FROM recovery_codes WHERE code_hash=? AND user_id=?',(st.digest(body.recovery_code),uid));c.execute('UPDATE users SET password=? WHERE id=?',(pw,uid));c.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,));c.execute('COMMIT')
 return {'ok':True}
@app.post('/api/auth/recovery-codes')
def regenerate_codes(body:Confirm,request:Request):
 a=auth(request,True);rate('regenerate:'+a['user_id'],8,subject=a['user_id'])
 with st.connect() as c:row=c.execute('SELECT password FROM users WHERE id=?',(a['user_id'],)).fetchone()
 if not row or not password_verify(body.password,row['password']):raise HTTPException(401,'Invalid credentials')
 encoded=row['password'];codes=[secrets.token_urlsafe(18) for _ in range(8)];token=request.cookies.get(COOKIE,'')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE')
  current=c.execute('SELECT u.password FROM users u JOIN auth_sessions s ON s.user_id=u.id WHERE u.id=? AND s.token_hash=? AND s.expires>?',(a['user_id'],st.digest(token),time.time())).fetchone()
  if not current or not hmac.compare_digest(current['password'],encoded):
   c.execute('ROLLBACK');raise HTTPException(401,'Sign in required')
  c.execute('DELETE FROM recovery_codes WHERE user_id=?',(a['user_id'],));c.executemany('INSERT INTO recovery_codes VALUES(?,?)',[(st.digest(code),a['user_id']) for code in codes]);c.execute('COMMIT')
 return {'recovery_codes':codes}
@app.delete('/api/account')
def delete_account(body:Confirm,request:Request,response:Response):
 a=auth(request,True);rate('account:'+a['user_id'],8,subject=a['user_id'])
 with st.connect() as c:row=c.execute('SELECT password FROM users WHERE id=?',(a['user_id'],)).fetchone()
 if not row or not password_verify(body.password,row['password']):raise HTTPException(401,'Invalid credentials')
 encoded=row['password'];token=request.cookies.get(COOKIE,'')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE')
  current=c.execute('SELECT u.password FROM users u JOIN auth_sessions s ON s.user_id=u.id WHERE u.id=? AND s.token_hash=? AND s.expires>?',(a['user_id'],st.digest(token),time.time())).fetchone()
  if not current or not hmac.compare_digest(current['password'],encoded):
   c.execute('ROLLBACK');raise HTTPException(401,'Sign in required')
  # Both account deletion and audio admission take the database write lock before AUDIO_JOBS_LOCK.
  with AUDIO_JOBS_LOCK:
   for job in AUDIO_JOBS.values():
    if job['user_id']==a['user_id']:
     job['cancelled']=True
     if job['process'] and job['process'].poll() is None:job['process'].terminate()
   c.execute('DELETE FROM attempts WHERE subject IN (?,?)',(st.digest(a['user_id']),st.digest(a['username'])));c.execute('DELETE FROM users WHERE id=?',(a['user_id'],));c.execute('COMMIT')
 response.delete_cookie(COOKIE,path=COOKIE_PATH);response.delete_cookie('bp5_csrf',path=COOKIE_PATH);return {'ok':True}
@app.get('/api/profile')
def get_profile(request:Request):
 a=auth(request)
 with st.connect() as c:r=c.execute('SELECT profile FROM users WHERE id=?',(a['user_id'],)).fetchone()
 return {'profile':json.loads(r['profile'])}
@app.patch('/api/profile')
def set_profile(body:Profile,request:Request):
 a=auth(request,True);sel=normalize_selection(st.get_curriculum(),body.framework_id,body.course,body.study_path)
 profile={'framework_id':sel['framework_id'],'course':sel['course'],'study_path':sel['study_path'],'selection':sel}
 with st.connect() as c:c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile,ensure_ascii=False),a['user_id']))
 return {'profile':profile}
@app.get('/api/library')
def library(request:Request):
 auth(request);lib=st.get_library();return {'situations':lib.get('situations',[]),'content_version':lib.get('content_version'),'curriculum':st.get_curriculum()}
@app.post('/api/missions')
def start_mission(body:Start,request:Request):
 a=auth(request,True)
 if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',body.request_id):raise ValueError('Invalid request ID')
 lib,sit,mission=st.mission_lookup(body.mission_id);curr=st.get_curriculum();sel=normalize_selection(curr,body.framework_id,body.course,body.study_path)
 criteria=[x for x in curr.get('criteria',[]) if x.get('framework_id')==sel['framework_id'] and x.get('course')==sel['course'] and (not sel['study_path'] or int(sel['study_path']) in x.get('study_paths',[]))] if sel['framework_id'] and sel['course'] else []
 ids={x['id'] for x in criteria};links=[x for x in mission.get('criterion_links',[]) if x.get('framework_id')==sel['framework_id'] and x.get('criterion_id') in ids]
 steps={x['id']:x for x in mission.get('steps',[])};first=mission.get('start_step')
 if first not in steps:raise RuntimeError('Invalid library')
 now=time.time();sid=uuid.uuid4().hex
 s={'id':sid,'mission_id':mission['id'],'situation_id':sit['id'],'status':'in_progress','current_step':first,'completed_objectives':[],'turns':[{'role':'assistant','text':mission.get('opening_sv',''),'created_at':now}],'evidence':[],'phrases':[],'prior_runs':[],'request_results':{},'created_at':now,'updated_at':now,'snapshot':{'mission':mission,'situation':{k:v for k,v in sit.items() if k!='missions'},'selection':sel,'criteria':criteria,'criterion_links':links,'content_version':lib.get('content_version'),'curriculum_content_version':curr.get('content_version')}}
 if len(json.dumps(s,ensure_ascii=False).encode('utf-8'))>131072:raise RuntimeError('Mission exceeds storage limit')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE');previous=c.execute('SELECT mission_id,payload_hash FROM creation_requests WHERE user_id=? AND request_id=?',(a['user_id'],st.digest(body.request_id))).fetchone()
  if previous:
   if previous['payload_hash']!=st.digest(body.model_dump_json()):c.execute('ROLLBACK');raise HTTPException(409,'Request ID was already used for different input')
   try: existing=st.owner_session(c,a['user_id'],previous['mission_id'])
   except LookupError:c.execute('ROLLBACK');raise HTTPException(409,'This request was already used for a deleted mission')
   c.execute('COMMIT');return {'session':existing}
  try:record_rate(c,'mission-create:'+a['user_id'],MAX_MISSION_CREATIONS_PER_HOUR,3600,subject=a['user_id'])
  except BaseException:c.execute('ROLLBACK');raise
  if c.execute('SELECT count(*) FROM creation_requests WHERE user_id=?',(a['user_id'],)).fetchone()[0]>=MAX_CREATION_REQUESTS:c.execute('ROLLBACK');raise HTTPException(409,'Account request limit reached')
  if c.execute('SELECT count(*) FROM missions WHERE user_id=?',(a['user_id'],)).fetchone()[0]>=200:c.execute('ROLLBACK');raise HTTPException(409,'Practice history limit reached; export and remove old sessions')
  c.execute('INSERT INTO missions VALUES(?,?,?,?)',(sid,a['user_id'],json.dumps(s,ensure_ascii=False),now));c.execute('INSERT INTO creation_requests VALUES(?,?,?,?)',(a['user_id'],st.digest(body.request_id),sid,st.digest(body.model_dump_json())));c.execute('COMMIT')
 return {'session':s}
class BoundedHistoryResponse(StreamingResponse):
 async def __call__(self,scope,receive,send):
  try:
   await asyncio.wait_for(super().__call__(scope,receive,send),timeout=180)
  finally:
   try:
    close=getattr(self.body_iterator,'aclose',None)
    if close:await close()
   finally:HISTORY_STREAM_LOCK.release()

def history_response(uid,kind):
 if not HISTORY_STREAM_LOCK.acquire(blocking=False):raise HTTPException(429,'History is busy; try again')
 async def generate():
  with st.connect() as c:
   c.execute('BEGIN')
   if kind=='export':
    row=c.execute('SELECT profile FROM users WHERE id=?',(uid,)).fetchone()
    if not row:return
    yield b'{"version":2,"profile":'+row['profile'].encode('utf-8')+b',"sessions":['
   else:yield b'{"sessions":['
   table='legacy_imports' if kind=='legacy' else 'missions'
   order='' if kind=='legacy' else ' ORDER BY updated DESC'
   first=True
   for row in c.execute('SELECT payload FROM '+table+' WHERE user_id=?'+order,(uid,)):
    yield (b'' if first else b',')+row['payload'].encode('utf-8');first=False
   if kind=='export':
    yield b'],"legacy_sessions":[';first=True
    for row in c.execute('SELECT payload FROM legacy_imports WHERE user_id=?',(uid,)):
     yield (b'' if first else b',')+row['payload'].encode('utf-8');first=False
   yield b']}'
   c.execute('COMMIT')
 headers={'Content-Disposition':'attachment; filename="prata-export.json"'} if kind=='export' else {}
 try:return BoundedHistoryResponse(generate(),media_type='application/json',headers=headers)
 except BaseException:HISTORY_STREAM_LOCK.release();raise

@app.get('/api/progress')
def progress(request:Request):
 a=auth(request)
 with st.connect() as c:
  rows=c.execute("SELECT id,json_extract(payload,'$.mission_id') AS mission_id,json_extract(payload,'$.status') AS status,updated AS updated_at FROM missions WHERE user_id=? ORDER BY updated DESC LIMIT 200",(a['user_id'],))
  return {'sessions':[dict(row) for row in rows]}

@app.get('/api/missions')
def list_missions(request:Request):
 a=auth(request);return history_response(a['user_id'],'missions')
@app.get('/api/missions/{sid}')
def get_mission(sid:str,request:Request):
 a=auth(request)
 with st.connect() as c:s=st.owner_session(c,a['user_id'],sid)
 return {'session':s}
@app.delete('/api/missions')
def delete_all(request:Request):
 a=auth(request,True)
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM missions WHERE user_id=?',(a['user_id'],));c.execute('DELETE FROM legacy_imports WHERE user_id=?',(a['user_id'],));c.execute('COMMIT')
 return {'ok':True}
@app.delete('/api/missions/{sid}')
def delete_mission(sid:str,request:Request):
 a=auth(request,True)
 with st.connect() as c:
  if c.execute('DELETE FROM missions WHERE id=? AND user_id=?',(sid,a['user_id'])).rowcount!=1:raise LookupError()
 return {'ok':True}
@app.get('/api/legacy')
def legacy_history(request:Request):
 a=auth(request);return history_response(a['user_id'],'legacy')
@app.get('/api/export')
def export(request:Request):
 a=auth(request);return history_response(a['user_id'],'export')

def advance_intent(s,mission,steps,step,intent,now):
 objective=step.get('objective')
 if objective and objective not in s['completed_objectives']:s['completed_objectives'].append(objective)
 if 'next_step' not in intent:raise RuntimeError('Invalid mission')
 next_step=intent['next_step']
 if next_step is None:
  if not set(mission.get('completion_objectives',[])).issubset(s['completed_objectives']):raise RuntimeError('Invalid mission')
  s['status']='completed';s['current_step']=None;s['completed_at']=now
 elif next_step not in steps:raise RuntimeError('Invalid mission')
 else:s['current_step']=next_step

def perform(sid,request,body,operation):
 a=auth(request,True)
 if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',body.request_id):raise ValueError('Invalid request ID')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE')
  try:
   s=st.owner_session(c,a['user_id'],sid);key=operation+':'+body.request_id
   if key in s['request_results']:
    previous=s['request_results'][key]
    if previous['payload_hash']!=st.digest(body.model_dump_json()):raise HTTPException(409,'Request ID was already used for different input')
    c.execute('COMMIT');return {'session':s,**previous['result']}
   if len(s['request_results'])>=500:raise ValueError('Mission history limit reached')
   now=time.time();result={}
   if operation=='turn':
    if s['status']=='completed':raise ValueError('Mission already complete; revisit it to practise again')
    if not body.text.strip():raise ValueError('Enter an answer')
    if len(s['turns'])>=200:raise ValueError('Mission turn limit reached')
    mission=s['snapshot']['mission'];steps={x['id']:x for x in mission['steps']};step=steps.get(s['current_step'])
    if not step:raise RuntimeError('Invalid mission')
    intent=st.match_step(step,body.text)
    reply=intent.get('reply_sv','') if intent else step.get('unknown_reply_sv','')
    feedback=intent.get('feedback_en','') if intent else step.get('unknown_feedback_en','')
    if not reply:raise RuntimeError('Invalid mission')
    s['turns'].append({'role':'user','turn_id':uuid.uuid4().hex,'text':body.text.strip(),'input_mode':body.input_mode,'transcript_edited':body.transcript_edited if body.input_mode=='voice' else False,'help_used':body.help_used,'step_id':step['id'],'intent_id':intent.get('id') if intent else None,'evidence_state':'practised','created_at':now})
    s['turns'].append({'role':'assistant','text':reply,'feedback_en':feedback,'matched':bool(intent),'created_at':now})
    if intent:advance_intent(s,mission,steps,step,intent,now)
    result={'reply':reply,'matched':bool(intent),'feedback':feedback}
   elif operation=='clarify':
    if s['status']!='in_progress' or s['current_step']!=body.step_id:raise HTTPException(409,'This clarification is no longer current')
    if body.turn_index!=len(s['turns'])-2:raise HTTPException(409,'This clarification is no longer current')
    original,unmatched=s['turns'][-2:]
    if original.get('role')!='user' or original.get('turn_id')!=body.turn_id or original.get('step_id')!=body.step_id or original.get('intent_id') is not None or original.get('clarified') or unmatched.get('role')!='assistant' or unmatched.get('matched') is not False:raise HTTPException(409,'This clarification is no longer current')
    if len(s['turns'])>=200:raise ValueError('Mission turn limit reached')
    mission=s['snapshot']['mission'];steps={x['id']:x for x in mission['steps']};step=steps.get(s['current_step'])
    if not step:raise RuntimeError('Invalid mission')
    choices=[x for x in step.get('intents',[]) if x.get('id')==body.intent_id]
    if len(choices)!=1:raise ValueError('Invalid clarification choice')
    intent=choices[0];reply=intent.get('reply_sv','');feedback='You selected the meaning. This is supported practice and does not assess your Swedish.'
    if not reply:raise RuntimeError('Invalid mission')
    original['clarified']=True;original['confirmed_intent_id']=body.intent_id;original['match_source']='learner_confirmation'
    supports=original.setdefault('help_used',[])
    if 'learner_confirmation' not in supports:supports.append('learner_confirmation')
    s['turns'].append({'role':'assistant','text':reply,'feedback_en':feedback,'matched':False,'clarified':True,'match_source':'learner_confirmation','created_at':now})
    advance_intent(s,mission,steps,step,intent,now)
    result={'reply':reply,'matched':False,'feedback':feedback,'clarified':True,'match_source':'learner_confirmation'}
   elif operation=='evidence':
    if len(s['evidence'])>=200:raise ValueError('Evidence limit reached')
    if not body.response.strip():raise ValueError('Enter an answer')
    s['evidence'].append({'activity':body.activity,'response':body.response.strip(),'help_used':body.help_used,'input_mode':'text','evidence_state':'practised','created_at':now})
   elif operation=='phrases':
    if len(s['phrases'])>=200:raise ValueError('Phrase limit reached')
    if not body.sv.strip():raise ValueError('Enter a phrase')
    s['phrases'].append({'sv':body.sv.strip(),'en':body.en.strip(),'created_at':now})
   elif operation=='reset':
    if len(s['prior_runs'])>=50:raise ValueError('Revisit limit reached')
    s['prior_runs'].append({'status':s['status'],'turns':s['turns'],'completed_objectives':s['completed_objectives'],'completed_at':s.get('completed_at')})
    s['status']='in_progress';s['current_step']=s['snapshot']['mission']['start_step'];s['completed_objectives']=[];s.pop('completed_at',None);s['turns']=[{'role':'assistant','text':s['snapshot']['mission'].get('opening_sv',''),'created_at':now}]
   s['updated_at']=now;s['request_results'][key]={'payload_hash':st.digest(body.model_dump_json()),'result':result};st.save_session(c,a['user_id'],s);c.execute('COMMIT');return {'session':s,**result}
  except BaseException:c.execute('ROLLBACK');raise
@app.post('/api/missions/{sid}/turn')
def turn(sid:str,body:Turn,request:Request):return perform(sid,request,body,'turn')
@app.post('/api/missions/{sid}/clarify')
def clarify(sid:str,body:Clarify,request:Request):return perform(sid,request,body,'clarify')
@app.post('/api/missions/{sid}/reset')
def reset(sid:str,body:Action,request:Request):return perform(sid,request,body,'reset')
@app.post('/api/missions/{sid}/evidence')
def evidence(sid:str,body:Evidence,request:Request):return perform(sid,request,body,'evidence')
@app.post('/api/missions/{sid}/phrases')
def phrase(sid:str,body:Phrase,request:Request):return perform(sid,request,body,'phrases')
AUDIO_JOBS={}
AUDIO_JOBS_LOCK=threading.Lock()
def begin_audio(a,request):
 jid=request.headers.get('x-audio-job','')
 if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',jid):raise ValueError('Audio job ID required')
 token=request.cookies.get(COOKIE,'')
 with st.connect() as c:
  c.execute('BEGIN IMMEDIATE')
  live=c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=? AND user_id=? AND expires>?',(st.digest(token),a['user_id'],time.time())).fetchone()
  if not live:c.execute('ROLLBACK');raise HTTPException(401,'Sign in required')
  try:record_rate(c,'audio:'+a['user_id'],60,60,subject=a['user_id'])
  except BaseException:c.execute('ROLLBACK');raise
  with AUDIO_JOBS_LOCK:
   if jid in AUDIO_JOBS:c.execute('ROLLBACK');raise HTTPException(409,'Audio job already exists')
   if not AUDIO_LOCK.acquire(blocking=False):c.execute('ROLLBACK');raise HTTPException(429,'Audio is busy; try again')
   job={'user_id':a['user_id'],'cancelled':False,'process':None};AUDIO_JOBS[jid]=job
   try:c.execute('COMMIT')
   except BaseException:
    AUDIO_JOBS.pop(jid,None);AUDIO_LOCK.release()
    if c.in_transaction:c.execute('ROLLBACK')
    raise
 return jid,job
def end_audio(jid):
 with AUDIO_JOBS_LOCK:AUDIO_JOBS.pop(jid,None);AUDIO_LOCK.release()
def run_audio(job,args,data=None,timeout=90):
 with AUDIO_JOBS_LOCK:
  if job['cancelled']:raise RuntimeError('Audio cancelled')
  try:p=subprocess.Popen([str(x) for x in args],stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=CREATE_NO_WINDOW)
  except OSError:raise RuntimeError('Audio unavailable')
  job['process']=p
 try:
  try:out,err=p.communicate(data,timeout=timeout)
  except subprocess.TimeoutExpired:p.kill();p.communicate();raise RuntimeError('Audio timed out')
  if job['cancelled'] or p.returncode:raise RuntimeError('Audio unavailable')
  return out
 finally:
  with AUDIO_JOBS_LOCK:job['process']=None
@app.delete('/api/audio/jobs/{jid}')
def cancel_audio(jid:str,request:Request):
 a=auth(request,True)
 with AUDIO_JOBS_LOCK:
  job=AUDIO_JOBS.get(jid)
  if not job or job['user_id']!=a['user_id']:raise LookupError()
  job['cancelled']=True
  if job['process'] and job['process'].poll() is None:job['process'].terminate()
 return {'ok':True}
def runtime_path(env,default):return os.getenv(env,default)
@app.post('/api/speech')
def speech(body:Speech,request:Request):
 a=auth(request,True);jid,job=begin_audio(a,request)
 try:
  with st.audio_workspace() as d:
   wav=d/'speech.wav';args=[runtime_path('BP5_PIPER_BIN','piper'),'--model',runtime_path('BP5_PIPER_MODEL','sv_SE-nst-medium.onnx'),'--output_file',wav]
   if body.slow:args+=['--length_scale','1.35']
   run_audio(job,args,(body.text+'\n').encode('utf-8'),60)
   return Response(wav.read_bytes(),media_type='audio/wav',headers={'Cache-Control':'no-store'})
 finally:end_audio(jid)
@app.post('/api/transcribe')
async def transcribe(request:Request):
 a=auth(request,True);raw=await request.body();fmt=AUDIO_FORMATS[request.headers.get('content-type','').split(';')[0].strip().lower()]
 if not raw or len(raw)>MAX_AUDIO:raise ValueError('Audio must be under 12 MB')
 jid,job=begin_audio(a,request)
 def process():
  try:
   with st.audio_workspace() as d:
    src=d/'source';wav=d/'audio.wav';out=d/'out';src.write_bytes(raw)
    run_audio(job,[runtime_path('BP5_FFMPEG','ffmpeg'),'-v','error','-protocol_whitelist','file,pipe','-f',fmt,'-i',src,'-t','181','-ac','1','-ar','16000','-f','wav',wav],timeout=90)
    with wave.open(str(wav),'rb') as w:
     if w.getnframes()/w.getframerate()>180:raise ValueError('Recording exceeds 180 seconds')
    run_audio(job,[runtime_path('BP5_WHISPER_BIN','whisper-cli'),'-m',runtime_path('BP5_WHISPER_MODEL','whisper-base.bin'),'-f',wav,'-l','sv','-otxt','-of',out,'-nt','-t','2'],timeout=240)
    text=out.with_suffix('.txt').read_text(encoding='utf-8').strip();return {'text':text[:4000]}
  finally:end_audio(jid)
 return await asyncio.to_thread(process)

@app.get('/')
def index():return FileResponse(st.ROOT/'web'/'index.html')
@app.get('/{asset}')
def asset(asset:str):
 if asset not in ('app.js','style.css'):raise HTTPException(404,'Not found')
 return FileResponse(st.ROOT/'web'/asset)
