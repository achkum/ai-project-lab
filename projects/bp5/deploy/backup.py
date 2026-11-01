"""Private, atomic encrypted backups for the single managed Prata data directory."""
import argparse, contextlib, datetime as dt, json, os, re, shutil, sqlite3, stat, subprocess, tempfile, time, uuid
from pathlib import Path

BASE=Path('/home/openclaw/prata')
OPERATOR_UID=996


def operator():
    if os.name!='posix' or os.geteuid()!=OPERATOR_UID:
        raise RuntimeError('Run as the managed Prata operator (uid 996)')
    os.umask(0o077)


def checked(path,kind=None):
    # Check lexical components BEFORE resolving; resolving first hides symlinks.
    path=Path(os.path.abspath(path));root=Path(os.path.abspath(BASE))
    if not path.is_relative_to(root):raise ValueError('Path is outside managed Prata storage')
    for item in [*reversed(path.parents),path]:
        if item.is_symlink():raise ValueError('Symlinks are not permitted in managed paths')
    if path.exists():
        mode=path.stat()
        if kind=='file' and (not stat.S_ISREG(mode.st_mode) or mode.st_nlink!=1):raise ValueError('Expected a private regular file')
        if kind=='dir' and not stat.S_ISDIR(mode.st_mode):raise ValueError('Expected a private directory')
    return path


def directory(path):
    path=checked(path,'dir');path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='posix' and path.stat().st_uid!=os.geteuid():raise RuntimeError('Managed directory has an unexpected owner')
    os.chmod(path,0o700);return path


def atomic_json(path,value):
    path=checked(path,'file');directory(path.parent)
    tmp=checked(path.parent/('.write-'+uuid.uuid4().hex))
    try:
        with tmp.open('x',encoding='utf-8') as f:
            json.dump(value,f);f.flush();os.fsync(f.fileno())
        checked(path,'file');os.replace(tmp,path)
        if os.name=='posix':
            fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
    finally:tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def locked(name):
    import fcntl
    directory(BASE);path=checked(BASE/name,'file')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def snapshot(source,dest):
    source=checked(source,'file');dest=checked(dest,'file')
    for suffix in ('-wal','-shm'):checked(Path(str(source)+suffix),'file')
    if not source.is_file() or dest.exists():raise RuntimeError('Snapshot requires an existing source and new destination')
    deadline=time.monotonic()+90
    def progress(*_):
        if time.monotonic()>deadline:raise RuntimeError('SQLite snapshot timed out')
    try:
        with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=5)) as old:
            with contextlib.closing(sqlite3.connect(dest,timeout=5)) as out:
                old.backup(out,pages=256,progress=progress,sleep=.1)
                if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Snapshot integrity check failed')
        os.chmod(dest,0o600)
    except BaseException:
        dest.unlink(missing_ok=True);raise


def remove_tree(path,parent):
    path=checked(path,'dir');parent=checked(parent,'dir')
    if path.parent!=parent or path==BASE:raise ValueError('Refusing unsafe cleanup target')
    if path.exists():shutil.rmtree(path)


def active_mounts():
    result=subprocess.run(['docker','ps','-q'],check=True,text=True,capture_output=True,timeout=20)
    ids=result.stdout.split()
    if not ids:return []
    if len(ids)>256 or any(not re.fullmatch('[a-f0-9]{12,64}',value) for value in ids):raise RuntimeError('Unexpected container inventory')
    result=subprocess.run(['docker','inspect',*ids],check=True,text=True,capture_output=True,timeout=20)
    return [Path(m['Source']).resolve() for c in json.loads(result.stdout) if c.get('State',{}).get('Running') for m in c.get('Mounts',[]) if m.get('Source')]


def in_use(path,mounts):
    path=checked(path).resolve()
    return any(path.is_relative_to(mount) or mount.is_relative_to(path) for mount in mounts)


def expire_deployment_copies(now=None):
    """The daily timer removes only old, inactive, exactly named private clones."""
    report={'expired':[],'retained':[]};cutoff=(now or time.time())-6*86400
    try:
        with locked('deploy.lock'):
            mounts=active_mounts()
            candidates=checked(BASE/'candidate-data','dir')
            rollback=checked(BASE/'rollback','dir')
            paths=list(candidates.glob('*')) if candidates.exists() else []
            paths+=list(rollback.glob('*.sqlite3')) if rollback.exists() else []
            legacy=BASE/'rollback.sqlite3'
            if legacy.exists() or legacy.is_symlink():paths.append(legacy)
            for path in paths:
                operation=path.stem if path.suffix=='.sqlite3' else path.name
                legacy_candidate=path.parent==candidates and re.fullmatch('[a-f0-9]{64}',operation)
                known=re.fullmatch('[a-f0-9]{32}',operation) or legacy_candidate or path==legacy
                if not known:continue
                try:
                    checked(path,'dir' if path.parent==candidates else 'file')
                    children=list(path.rglob('*')) if path.is_dir() else []
                    for child in children:checked(child,'file' if child.is_file() else 'dir')
                    if max([path.stat().st_mtime,*[child.stat().st_mtime for child in children]])>=cutoff:continue
                    if in_use(path,mounts):report['retained'].append({'artifact':path.name,'reason':'active container reference'});continue
                    journal=checked(BASE/'operations'/(operation+'.json'),'file') if path!=legacy else None
                    state=json.loads(journal.read_text()) if journal and journal.exists() else None
                    if path!=legacy and not legacy_candidate and (not state or state.get('operation')!=operation):
                        report['retained'].append({'artifact':path.name,'reason':'missing managed journal'});continue
                    if path.is_dir():remove_tree(path,candidates)
                    else:path.unlink()
                    report['expired'].append(path.name)
                    atomic_json(BASE/'maintenance-history'/(uuid.uuid4().hex+'.json'),{'artifact':path.name,'expired_at':time.time(),'reason':'inactive deployment copy older than six days'})
                    if state:
                        state.setdefault('expired_artifacts',[]).append({'artifact':path.name,'expired_at':time.time()})
                        atomic_json(journal,state)
                except (OSError,ValueError,RuntimeError):report['retained'].append({'artifact':path.name,'reason':'unsafe or unavailable artifact'})
    except BlockingIOError:report['skipped']='deployment in progress'
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):report['skipped']='container inventory or managed path unavailable'
    atomic_json(BASE/'maintenance-status.json',report);return report


def _backup(data=None):
    operator()
    # Backups cannot be redirected to releases, candidate databases or other home files.
    data=checked(data or BASE/'data','dir')
    if data!=BASE/'data':raise ValueError('Only the active Prata database may be backed up')
    with locked('backup.lock'):
        maintenance=expire_deployment_copies()
        target=directory(BASE/'backups');work=directory(BASE/'backup-work')
        now=dt.datetime.now(dt.timezone.utc);cutoff=now.timestamp()-6*86400
        # Retention runs even when the next backup fails. The daily timer is required.
        for p in target.iterdir():
            if re.fullmatch(r'prata-[0-9]{8}T[0-9]{12}Z\.sqlite3\.age',p.name):
                checked(p,'file')
                if p.stat().st_mtime<cutoff:p.unlink()
            elif re.fullmatch(r'\.partial-[a-f0-9]{32}',p.name):checked(p,'file').unlink()
        for p in work.iterdir():
            if re.fullmatch(r'snapshot-[a-zA-Z0-9_-]+',p.name):remove_tree(p,work)
        source=checked(data/'production.sqlite3','file')
        if not source.is_file():raise RuntimeError('No application database to back up')
        recipient=checked(BASE/'backup-recipient.txt','file').read_text().strip()
        if not re.fullmatch(r'age1[a-z0-9]{58}',recipient):raise ValueError('Invalid backup recipient')
        age=checked(BASE/'runtime/age/age','file')
        filename='prata-'+now.strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3.age'
        partial=checked(target/('.partial-'+uuid.uuid4().hex));finished=checked(target/filename)
        try:
            with tempfile.TemporaryDirectory(prefix='snapshot-',dir=work) as temp:
                plain=Path(temp)/'snapshot.sqlite3';snapshot(source,plain)
                subprocess.run([str(age),'-r',recipient,'-o',str(partial),str(plain)],check=True,timeout=120,capture_output=True)
                if not checked(partial,'file').is_file() or partial.stat().st_size==0:raise RuntimeError('Encryption produced no backup')
                with partial.open('r+b') as f:os.fsync(f.fileno())
                if finished.exists():raise RuntimeError('Backup destination already exists')
                os.replace(partial,finished)
        finally:partial.unlink(missing_ok=True)
        record={'ok':True,'completed_at':now.isoformat(),'filename':filename,'encrypted':True,'retention_days_max':7,'maintenance':maintenance}
        atomic_json(BASE/'backup-status.json',record);return record


def backup(data=None):
    operator()
    try:return _backup(data)
    except BaseException:
        try:atomic_json(BASE/'backup-status.json',{'ok':False,'failed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'error':'Backup did not complete; inspect timer status'})
        except (OSError,ValueError,RuntimeError):pass
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data');args=p.parse_args()
    print(json.dumps(backup(args.data)))
