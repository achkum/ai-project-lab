"""Privileged local administration. Never expose this script over HTTP."""
import argparse, json, os, sqlite3, sys, uuid
from contextlib import closing
from pathlib import Path
import production_store as st

def main():
 parser=argparse.ArgumentParser();subs=parser.add_subparsers(dest='action',required=True)
 inv=subs.add_parser('create-invite');inv.add_argument('--output',required=True,help='new private file, never stdout')
 migrate=subs.add_parser('import-legacy');migrate.add_argument('--username',required=True);migrate.add_argument('--legacy-db',required=True);migrate.add_argument('--confirm-owner',required=True,help='must exactly equal username')
 args=parser.parse_args();st.init()
 if args.action=='create-invite':
  path=Path(args.output);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  try:
   token=st.create_invite()
   with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(token+'\n')
  except BaseException:
   try:os.close(fd)
   except OSError:pass
   path.unlink(missing_ok=True);raise
  print('Invitation written to private file; deliver it through a trusted channel.')
 else:
  u=args.username.strip().casefold()
  if args.confirm_owner!=args.username:raise SystemExit('Confirmation must match the target username exactly')
  uri=Path(args.legacy_db).resolve().as_uri()+'?mode=ro'
  rows=[]
  with closing(sqlite3.connect(uri,uri=True)) as old:
   # Bound text length before materializing each record; then verify its encoded byte size.
   for rowid,id_chars,payload_chars in old.execute('SELECT rowid,length(id),length(payload) FROM sessions LIMIT 201'):
    if len(rows)>=200:raise SystemExit('Legacy import exceeds 200 records; no records were imported')
    if id_chars is None or id_chars>128 or payload_chars is None or payload_chars>131072:raise SystemExit('A legacy record is invalid or exceeds 128 KiB; no records were imported')
    payload_row=old.execute('SELECT id,payload FROM sessions WHERE rowid=?',(rowid,)).fetchone();sid,payload=payload_row if payload_row else (None,None)
    if not isinstance(sid,str) or not isinstance(payload,str) or len(payload.encode('utf-8'))>131072:raise SystemExit('A legacy record is invalid; no records were imported')
    def reject_constant(_):raise ValueError('Non-finite JSON number')
    try:
     parsed=json.loads(payload,parse_constant=reject_constant);valid=isinstance(parsed,dict);json.dumps(parsed,allow_nan=False)
    except (ValueError,RecursionError,TypeError):valid=False
    if not valid:raise SystemExit('A legacy record is invalid; no records were imported')
    rows.append((sid,payload))
  with st.connect() as c:
   c.execute('BEGIN IMMEDIATE');user=c.execute('SELECT id FROM users WHERE username=?',(u,)).fetchone()
   if not user:c.execute('ROLLBACK');raise SystemExit('Target account not found')
   current=c.execute('SELECT count(*) FROM legacy_imports WHERE user_id=?',(user['id'],)).fetchone()[0]
   new_count=sum(1 for sid,_ in rows if not c.execute('SELECT 1 FROM legacy_imports WHERE id=?',(str(sid),)).fetchone())
   if current+new_count>200:c.execute('ROLLBACK');raise SystemExit('Import would exceed 200 legacy records; no records were imported')
   inserted=0
   for sid,payload in rows:inserted+=c.execute('INSERT OR IGNORE INTO legacy_imports VALUES(?,?,?)',(str(sid),user['id'],payload)).rowcount
   c.execute('COMMIT')
  print(f'Imported {inserted} of {len(rows)} legacy records into the explicitly named account; existing IDs were not reassigned.')
if __name__=='__main__':main()

