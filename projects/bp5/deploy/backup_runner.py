"""Stable systemd entry point selecting the last committed production release."""
import json,os,re,subprocess,sys
from pathlib import Path
base=Path('/home/openclaw/prata')
if os.geteuid()!=996:raise RuntimeError('Run as the Prata operator')
record=base/'deployment.json'
if any(p.is_symlink() for p in [record,*record.parents]):raise RuntimeError('Unexpected deployment record path')
source=json.loads(record.read_text())['source']
if not re.fullmatch('[a-f0-9]{64}',source):raise RuntimeError('Invalid deployment identity')
script=base/'releases'/source/'deploy/backup.py'
if any(p.is_symlink() for p in [script,*script.parents]) or not script.is_file():raise RuntimeError('Backup code is unavailable')
subprocess.run([sys.executable,'-B',str(script)],check=True,timeout=300)
