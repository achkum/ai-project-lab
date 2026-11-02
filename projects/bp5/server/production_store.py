"""Account-scoped BP5 persistence and deterministic, authored mission matching."""
import hashlib, hmac, json, os, re, secrets, sqlite3, time, unicodedata, uuid, tempfile, shutil
from contextlib import contextmanager
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('LAB_DATA_DIR',str(ROOT/'data'))); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'production.sqlite3'
MAX_SESSION_SECONDS=12*60*60

class ClosingConnection(sqlite3.Connection):
 def __exit__(self,*args):
  try:return super().__exit__(*args)
  finally:self.close()

def connect():
 c=sqlite3.connect(DB,timeout=20,isolation_level=None,factory=ClosingConnection); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=20000'); return c

def init():
 with connect() as c:
  c.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, profile TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS invitations(token_hash TEXT PRIMARY KEY, created REAL NOT NULL, consumed REAL);
CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, csrf_hash TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_codes(code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, payload TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS creation_requests(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, request_id TEXT NOT NULL, mission_id TEXT NOT NULL, payload_hash TEXT NOT NULL, PRIMARY KEY(user_id,request_id));
CREATE TABLE IF NOT EXISTS attempts(key TEXT NOT NULL, occurred REAL NOT NULL, subject TEXT);
CREATE TABLE IF NOT EXISTS semantic_budgets(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, available REAL NOT NULL CHECK(available>=0), updated REAL NOT NULL, blocked_until REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS legacy_imports(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions(expires);
CREATE INDEX IF NOT EXISTS auth_sessions_user_expiry ON auth_sessions(user_id,expires);
CREATE INDEX IF NOT EXISTS attempts_key_time ON attempts(key,occurred);
CREATE INDEX IF NOT EXISTS attempts_occurred ON attempts(occurred);
CREATE INDEX IF NOT EXISTS missions_owner ON missions(user_id,updated);
''')
  if 'subject' not in {r['name'] for r in c.execute('PRAGMA table_info(attempts)')}:c.execute('ALTER TABLE attempts ADD COLUMN subject TEXT')
  if 'blocked_until' not in {r['name'] for r in c.execute('PRAGMA table_info(semantic_budgets)')}:c.execute('ALTER TABLE semantic_budgets ADD COLUMN blocked_until REAL NOT NULL DEFAULT 0')
  if 'payload_hash' not in {r['name'] for r in c.execute('PRAGMA table_info(creation_requests)')}:c.execute("ALTER TABLE creation_requests ADD COLUMN payload_hash TEXT NOT NULL DEFAULT ''")

def digest(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def hash_password(s):
 salt=secrets.token_bytes(16); h=hashlib.scrypt(s.encode(),salt=salt,n=32768,r=8,p=1,dklen=32,maxmem=64*1024*1024);return 'scrypt$32768$8$1$'+salt.hex()+'$'+h.hex()
def verify_password(s,encoded):
 try:
  typ,n,r,p,salt,want=encoded.split('$'); assert typ=='scrypt' and (n,r,p)==('32768','8','1'); got=hashlib.scrypt(s.encode(),salt=bytes.fromhex(salt),n=int(n),r=int(r),p=int(p),dklen=32,maxmem=64*1024*1024);return hmac.compare_digest(got,bytes.fromhex(want))
 except (ValueError,AssertionError):return False

def get_library():
 p=ROOT/'content'/'library.json'
 if not p.exists(): raise RuntimeError('Mission library is not installed')
 return json.loads(p.read_text(encoding='utf-8'))
def get_curriculum():return json.loads((ROOT/'content'/'curriculum.json').read_text(encoding='utf-8'))

def library_ready(lib):
 try:
  situations=lib['situations'];missions=[m for sit in situations for m in sit['missions']]
  if len(situations)<18 or len(missions)<54 or len({m['id'] for m in missions})!=len(missions):return False
  for m in missions:
   steps=m['steps'];ids={s['id'] for s in steps};objectives={s['objective'] for s in steps}
   if len(ids)!=len(steps) or m['start_step'] not in ids or not m.get('completion_objectives') or not set(m['completion_objectives']).issubset(objectives):return False
   terminals=0
   for step in steps:
    if not step.get('unknown_reply_sv') or not step.get('intents'):return False
    for intent in step['intents']:
     if not valid_match_spec(intent):return False
     if not intent.get('reply_sv') or 'next_step' not in intent:return False
     nxt=intent['next_step']
     if nxt is None:terminals+=1
     elif nxt not in ids:return False
   if not terminals:return False
  return True
 except (KeyError,TypeError,ValueError):return False

def normalize_text(s):
 # Token boundaries prevent substring matches such as "ja" inside another word.
 s=unicodedata.normalize('NFKC',s).casefold();return re.findall(r'[^\W_]+',s,flags=re.UNICODE)
def contains(tokens,phrase):
 p=normalize_text(phrase)
 return bool(p) and any(tokens[i:i+len(p)]==p for i in range(len(tokens)-len(p)+1))
def valid_match_spec(intent):
 if not isinstance(intent,dict):return False
 groups=intent.get('required_groups',[]);exact=intent.get('exact_replies_sv',[]);reject=intent.get('reject_terms',[])
 if not isinstance(groups,list) or not isinstance(exact,list) or not isinstance(reject,list):return False
 if not groups and not exact:return False
 def phrase_ok(value):return isinstance(value,str) and bool(normalize_text(value))
 if any(not isinstance(group,list) or not group or any(not phrase_ok(v) for v in group) for group in groups):return False
 if any(not phrase_ok(v) for v in exact) or any(not phrase_ok(v) for v in reject):return False
 return True

def match_step(step,text):
 tokens=normalize_text(text);matches=[]
 if not tokens:return None
 for intent in step.get('intents',[]):
  if not valid_match_spec(intent):continue
  # Only an explicitly authored complete token sequence may bypass reject
  # terms. Extra words, including contradictory ones, cannot be an exact hit.
  exact=any(tokens==normalize_text(phrase) for phrase in intent.get('exact_replies_sv',[]))
  if exact:matches.append(intent);continue
  groups=intent.get('required_groups',[])
  if not groups or any(contains(tokens,x) for x in intent.get('reject_terms',[])):continue
  if all(any(contains(tokens,variant) for variant in group) for group in groups):matches.append(intent)
 return matches[0] if len(matches)==1 else None

def mission_lookup(mid):
 lib=get_library()
 for sit in lib.get('situations',[]):
  for mission in sit.get('missions',[]):
   if mission.get('id')==mid:return lib,sit,mission
 raise ValueError('Mission not found')

def mission_content_status(session):
 """Compare the saved authored mission itself, never a client/version claim."""
 saved=session.get('snapshot',{}).get('mission');mid=session.get('mission_id')
 if not isinstance(saved,dict) or not isinstance(mid,str) or saved.get('id')!=mid:
  return {'current':False,'can_start_updated':False}
 lib=get_library();matches=[m for sit in lib.get('situations',[]) for m in sit.get('missions',[]) if m.get('id')==mid]
 if len(matches)!=1:return {'current':False,'can_start_updated':False}
 def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
 return {'current':canonical(saved)==canonical(matches[0]),'can_start_updated':True}

def owner_session(c,uid,sid):
 row=c.execute('SELECT payload FROM missions WHERE id=? AND user_id=?',(sid,uid)).fetchone()
 if not row: raise LookupError('Not found')
 s=json.loads(row['payload'])
 # Stable compatibility identity for user turns created before turn IDs existed.
 for i,turn in enumerate(s.get('turns',[])):
  if turn.get('role')=='user' and not turn.get('turn_id') and isinstance(turn.get('created_at'),(float,int)):
   identity=json.dumps([sid,i,turn['created_at'],turn.get('text',''),turn.get('step_id','')],ensure_ascii=False,separators=(',',':'))
   turn['turn_id']='legacy-'+digest(identity)
 return s
def save_session(c,uid,s):
 payload=json.dumps(s,ensure_ascii=False)
 if len(payload.encode('utf-8'))>131072:raise ValueError('This session is full; start a new practice session')
 c.execute('UPDATE missions SET payload=?,updated=? WHERE id=? AND user_id=?',(payload,s['updated_at'],s['id'],uid))

def create_invite():
 init(); token=secrets.token_urlsafe(32)
 with connect() as c:c.execute('INSERT INTO invitations VALUES(?,?,NULL)',(digest(token),time.time()))
 return token

def _lock_file(handle, blocking=False):
 try:
  if os.name=='nt':
   import msvcrt
   handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK,1)
  else:
   import fcntl
   fcntl.flock(handle.fileno(),fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
  return True
 except (OSError,BlockingIOError):return False

def _unlock_file(handle):
 if os.name=='nt':
  import msvcrt
  handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
 else:
  import fcntl
  fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

@contextmanager
def audio_workspace():
 # Lock a companion file before the workspace name becomes visible to cleanup.
 job_id=uuid.uuid4().hex;target=DATA/('bp5-audio-'+job_id);marker=DATA/('.bp5-audio-lock-'+job_id);handle=None;locked=False
 try:
  with marker.open('xb') as f:f.write(b'1')
  handle=marker.open('r+b')
  if not _lock_file(handle,True):raise RuntimeError('Audio workspace unavailable')
  locked=True;target.mkdir(mode=0o700)
  yield target
 finally:
  if handle:
   try:
    if locked:_unlock_file(handle)
   finally:handle.close()
  shutil.rmtree(target,ignore_errors=True)
  try:marker.unlink(missing_ok=True)
  except OSError:pass

def cleanup_abandoned_audio():
 root=DATA.resolve();removed=0
 for path in DATA.glob('bp5-audio-*'):
  try:
   if path.is_symlink() or not path.is_dir() or path.resolve().parent!=root or not re.fullmatch(r'bp5-audio-[0-9a-f]{32}',path.name):continue
   job_id=path.name.removeprefix('bp5-audio-');marker=DATA/('.bp5-audio-lock-'+job_id)
   if marker.is_symlink() or not marker.is_file() or marker.resolve().parent!=root:continue
   with marker.open('r+b') as handle:
    if not _lock_file(handle):continue
    _unlock_file(handle)
   # A live creator holds the companion lock until it has finished using the workspace.
   shutil.rmtree(path);marker.unlink(missing_ok=True);removed+=1
  except OSError:continue
 return removed
