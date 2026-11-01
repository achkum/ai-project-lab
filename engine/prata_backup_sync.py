"""Mirror the newest encrypted Prata backup to the private local runtime.

Only fixed SSH commands read remote backup status and encrypted files. No keys,
SQLite plaintext or remote error output are copied or logged by this module.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import shlex
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import background_process as sp

MAX_BYTES = 1024 * 1024 * 1024
RETENTION_SECONDS = 6 * 86400
NAME = re.compile(r'prata-[0-9]{8}T[0-9]{12}Z\.sqlite3\.age\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15',
       '-o', 'ServerAliveCountMax=3', 'openclaw']

# These programs are constants, not constructed from remote status or profile
# values. They open only backup-status.json and the validated ciphertext name.
REMOTE_META = r'''import os,stat,json,hashlib,re,sys
base='/home/openclaw/prata'
fd=os.open(base+'/backup-status.json',os.O_RDONLY|os.O_NOFOLLOW)
try:
 s=os.fstat(fd)
 if not stat.S_ISREG(s.st_mode) or s.st_size>65536: raise ValueError()
 with os.fdopen(fd,'rb',closefd=False) as f: raw=f.read(65537)
 status=json.loads(raw)
finally: os.close(fd)
if status.get('ok') is not True or status.get('encrypted') is not True: print('{"ok":false}');sys.exit(0)
name=status.get('filename','')
if not isinstance(name,str) or not re.fullmatch(r'prata-[0-9]{8}T[0-9]{12}Z\.sqlite3\.age',name): raise ValueError()
d=os.open(base+'/backups',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
 try:
  s=os.fstat(fd)
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or not 0<s.st_size<=1073741824: raise ValueError()
  h=hashlib.sha256();remaining=s.st_size
  while remaining:
   chunk=os.read(fd,min(1048576,remaining))
   if not chunk: raise ValueError()
   h.update(chunk);remaining-=len(chunk)
  if os.read(fd,1): raise ValueError()
  after=os.fstat(fd)
  if (s.st_ino,s.st_size,s.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns): raise ValueError()
  print(json.dumps({'ok':True,'filename':name,'size':s.st_size,'sha256':h.hexdigest()},separators=(',',':')))
 finally: os.close(fd)
finally: os.close(d)
'''
REMOTE_COPY = r'''import os,stat,re,sys
name=sys.argv[1];size=int(sys.argv[2])
if not re.fullmatch(r'prata-[0-9]{8}T[0-9]{12}Z\.sqlite3\.age',name) or not 0<size<=1073741824: raise ValueError()
d=os.open('/home/openclaw/prata/backups',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
 try:
  s=os.fstat(fd)
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=size: raise ValueError()
  remaining=size
  while remaining:
   chunk=os.read(fd,min(1048576,remaining))
   if not chunk: raise ValueError()
   sys.stdout.buffer.write(chunk);remaining-=len(chunk)
  if os.read(fd,1): raise ValueError()
  sys.stdout.buffer.flush()
  after=os.fstat(fd)
  if (s.st_ino,s.st_size,s.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns): raise ValueError()
 finally: os.close(fd)
finally: os.close(d)
'''

class SyncError(Exception):
    pass


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def _root(profile):
    if not isinstance(profile, dict):
        raise SyncError('invalid_runtime_root')
    value = profile.get('runtime_root')
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise SyncError('invalid_runtime_root')
    root = Path(os.path.abspath(value))
    for path in (root, *root.parents):
        if _linked(path):
            raise SyncError('unsafe_runtime_path')
    if not root.is_dir():
        raise SyncError('invalid_runtime_root')
    root = root.resolve(strict=True)
    target = root / 'prata-backups'
    if _linked(target):
        raise SyncError('unsafe_backup_directory')
    target.mkdir(exist_ok=True)
    if _linked(target) or not target.is_dir() or target.resolve(strict=True).parent != root:
        raise SyncError('unsafe_backup_directory')
    return target.resolve(strict=True)


def _regular(path):
    try:
        if _linked(path):
            return False
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    except FileNotFoundError:
        return False


def _contained(directory, path):
    return path.parent == directory and path.name not in ('', '.', '..')


@contextmanager
def _lock(directory):
    path = directory / '.sync.lock'
    if not _contained(directory, path) or _linked(path):
        raise SyncError('unsafe_lock')
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise SyncError('unsafe_lock') from exc
    try:
        if not _regular(path) or not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SyncError('unsafe_lock')
        if os.fstat(fd).st_size == 0:
            os.write(fd, b'1')
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SyncError('sync_already_running') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _timestamp(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise SyncError('invalid_remote_metadata')
    try:
        return dt.datetime.strptime(name[6:-12], '%Y%m%dT%H%M%S%fZ').replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise SyncError('invalid_remote_metadata') from exc


def _read_manifest(directory):
    path = directory / 'sync-manifest.json'
    if _linked(path):
        raise SyncError('unsafe_manifest')
    if not path.exists():
        return []
    if not _regular(path) or path.stat().st_size > 1024 * 1024:
        raise SyncError('unsafe_manifest')
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as f:
            before = os.fstat(f.fileno())
            raw = f.read(1024 * 1024 + 1)
            after = os.fstat(f.fileno())
            if len(raw) > 1024 * 1024 or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns) or _linked(path):
                raise ValueError()
        data = json.loads(raw.decode('utf-8'))
        items = data['managed']
        if data.get('version') != 1 or not isinstance(items, list) or len(items) > 1024:
            raise ValueError()
        seen = set()
        for item in items:
            if not isinstance(item, dict): raise ValueError()
            name, size, digest = item.get('filename'), item.get('size'), item.get('sha256')
            _timestamp(name)
            if name in seen or type(size) is not int or not 0 < size <= MAX_BYTES or not isinstance(digest, str) or not SHA.fullmatch(digest): raise ValueError()
            seen.add(name)
        return items
    except (OSError, ValueError, TypeError, KeyError, SyncError) as exc:
        raise SyncError('unsafe_manifest') from exc


def _prune(directory, now, managed):
    count = 0
    retained = []
    for item in managed:
        path = directory / item['filename']
        if not _contained(directory, path) or not _regular(path):
            # A missing or replaced file is no longer under our management.
            continue
        try:
            if (now - _timestamp(path.name)).total_seconds() > RETENTION_SECONDS:
                # Hash only expired candidates; recent copies need not be read
                # in full on every daily run.
                if _hash_file(path) != (item['size'], item['sha256']):
                    continue
                if _regular(path) and path.resolve(strict=True).parent == directory:
                    path.unlink()
                    count += 1
                    continue
        except OSError:
            # A transient I/O or permission failure is retried on the next run.
            retained.append(item)
            continue
        except SyncError:
            # Do not delete or continue claiming a file whose identity is uncertain.
            continue
        retained.append(item)
    return count, retained


def _ssh(command, write, limit, timeout):
    try:
        process = sp.Popen(SSH + [command], stdin=sp.DEVNULL, stdout=sp.PIPE, stderr=sp.DEVNULL)
    except OSError as exc:
        raise SyncError('ssh_unavailable') from exc
    expired = threading.Event()
    def stop():
        expired.set()
        try: process.kill()
        except OSError: pass
    timer = threading.Timer(timeout, stop)
    timer.daemon = True
    timer.start()
    total = 0
    try:
        while True:
            data = process.stdout.read(min(1024 * 1024, limit + 1 - total))
            if not data:
                break
            total += len(data)
            if total > limit:
                raise SyncError('remote_output_too_large')
            write(data)
        try: code = process.wait(timeout=5)
        except sp.TimeoutExpired as exc: raise SyncError('ssh_timeout') from exc
        if expired.is_set():
            raise SyncError('ssh_timeout')
        if code:
            raise SyncError('remote_unavailable')
        return total
    finally:
        timer.cancel()
        if process.poll() is None:
            try: process.kill()
            except OSError: pass
            try: process.wait(timeout=5)
            except sp.TimeoutExpired: pass
        if process.stdout:
            process.stdout.close()


def _metadata(now):
    out = io.BytesIO()
    _ssh('python3 -c ' + shlex.quote(REMOTE_META), out.write, 8192, 120)
    try:
        record = json.loads(out.getvalue().decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SyncError('invalid_remote_metadata') from exc
    if not isinstance(record, dict) or record.get('ok') is not True:
        raise SyncError('remote_backup_unavailable')
    name, size, digest = record.get('filename'), record.get('size'), record.get('sha256')
    stamp = _timestamp(name)
    if type(size) is not int or not 0 < size <= MAX_BYTES or not isinstance(digest, str) or not SHA.fullmatch(digest):
        raise SyncError('invalid_remote_metadata')
    age = (now - stamp).total_seconds()
    if age < -300:
        raise SyncError('remote_backup_future')
    if age > RETENTION_SECONDS:
        raise SyncError('remote_backup_stale')
    return {'filename': name, 'size': size, 'sha256': digest, 'age_seconds': max(0, int(age))}


def _hash_file(path):
    if not _regular(path):
        raise SyncError('unsafe_local_file')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
            raise SyncError('unsafe_local_file')
        h = hashlib.sha256()
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
        after = os.fstat(f.fileno())
        if (info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise SyncError('local_file_changed')
        return info.st_size, h.hexdigest()


def _copy(directory, record):
    target = directory / record['filename']
    if not _contained(directory, target) or _linked(target):
        raise SyncError('unsafe_local_file')
    if target.exists():
        if _hash_file(target) == (record['size'], record['sha256']):
            return False
        raise SyncError('local_name_conflict')
    fd, name = tempfile.mkstemp(prefix='.prata-sync-', dir=directory)
    temporary = Path(name)
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, 'wb') as f:
            def write(chunk):
                f.write(chunk)
                h.update(chunk)
            command = 'python3 -c ' + shlex.quote(REMOTE_COPY) + ' ' + shlex.quote(record['filename']) + ' ' + str(record['size'])
            size = _ssh(command, write, record['size'], 1800)
            f.flush()
            os.fsync(f.fileno())
        if size != record['size'] or h.hexdigest() != record['sha256'] or _hash_file(temporary) != (size, record['sha256']):
            raise SyncError('checksum_mismatch')
        # Windows rename is exclusive. On POSIX an exclusive hard-link publish
        # prevents overwriting an unrelated destination; unlink removes the temp.
        try:
            if os.name == 'nt':
                os.rename(temporary, target)
            else:
                os.link(temporary, target, follow_symlinks=False)
                temporary.unlink()
        except FileExistsError as exc:
            raise SyncError('local_name_conflict') from exc
        return True
    finally:
        if _contained(directory, temporary) and _regular(temporary):
            temporary.unlink()


def _write_json(directory, filename, value):
    target = directory / filename
    if filename not in ('sync-status.json', 'sync-manifest.json') or not _contained(directory, target) or _linked(target) or (target.exists() and not _regular(target)):
        raise SyncError('unsafe_metadata_file')
    fd, name = tempfile.mkstemp(prefix='.prata-metadata-', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, target)
    finally:
        if _contained(directory, temporary) and _regular(temporary):
            temporary.unlink()


def sync(profile):
    now = dt.datetime.now(dt.timezone.utc)
    result = {'version': 1, 'ok': False, 'checked_at': now.isoformat(), 'copied': False, 'expired_count': 0}
    directory = None
    try:
        directory = _root(profile)
        with _lock(directory):
            try:
                managed = _read_manifest(directory)
                result['expired_count'], retained = _prune(directory, now, managed)
                if retained != managed:
                    _write_json(directory, 'sync-manifest.json', {'version': 1, 'managed': retained})
                record = _metadata(now)
                result['remote_backup'] = record
                if len(retained) >= 1024 and not (directory / record['filename']).exists():
                    raise SyncError('manifest_limit_reached')
                result['copied'] = _copy(directory, record)
                if result['copied']:
                    retained.append({k: record[k] for k in ('filename', 'size', 'sha256')})
                    _write_json(directory, 'sync-manifest.json', {'version': 1, 'managed': retained})
                result['managed'] = any(item['filename'] == record['filename'] and item['sha256'] == record['sha256'] and item['size'] == record['size'] for item in retained)
                result['ok'] = True
            except SyncError as exc:
                result['error'] = str(exc)
            except (OSError, ValueError):
                result['error'] = 'local_sync_failed'
            _write_json(directory, 'sync-status.json', result)
    except SyncError as exc:
        result['error'] = str(exc)
    except (OSError, ValueError):
        result['error'] = 'local_sync_failed'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default=str(Path(__file__).resolve().parents[1] / 'config' / 'profile.local.json'))
    args = parser.parse_args()
    try:
        profile = json.loads(Path(args.profile).read_text(encoding='utf-8'))
        result = sync(profile)
    except (OSError, ValueError):
        result = {'version': 1, 'ok': False, 'error': 'profile_unavailable'}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ok'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
