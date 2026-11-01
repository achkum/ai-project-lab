import datetime as dt
import hashlib
import io
import json
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import prata_backup_sync as backup


def filename(when):
    return 'prata-' + when.strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3.age'


def item(name, data):
    return {'filename': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class BackupSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.profile = {'runtime_root': str(self.root)}
        self.now = dt.datetime.now(dt.timezone.utc)
        self.data = b'age-encryption.org/v1\nfixture ciphertext\n'
        self.name = filename(self.now)
        self.remote = {'ok': True, **item(self.name, self.data)}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def ssh(self, command, write, limit, timeout):
        self.calls.append(command)
        data = json.dumps(self.remote).encode() if 'backup-status.json' in command else self.data
        if len(data) > limit:
            raise backup.SyncError('remote_output_too_large')
        write(data)
        return len(data)

    def test_sync_copies_once_and_records_safe_manifest_and_status(self):
        with patch.object(backup, '_ssh', side_effect=self.ssh):
            first = backup.sync(self.profile)
            second = backup.sync(self.profile)
        directory = self.root / 'prata-backups'
        self.assertTrue(first['ok']); self.assertTrue(first['copied']); self.assertTrue(first['managed'])
        self.assertTrue(second['ok']); self.assertFalse(second['copied']); self.assertTrue(second['managed'])
        self.assertEqual((directory / self.name).read_bytes(), self.data)
        self.assertEqual(len([c for c in self.calls if 'backup-status.json' not in c]), 1)
        self.assertEqual(json.loads((directory / 'sync-manifest.json').read_text())['managed'], [item(self.name, self.data)])
        status = json.loads((directory / 'sync-status.json').read_text())
        self.assertTrue(status['ok']); self.assertNotIn('recipient', json.dumps(status)); self.assertNotIn('private', json.dumps(status))

    def test_retention_removes_only_unchanged_manifest_owned_old_files(self):
        directory = self.root / 'prata-backups'; directory.mkdir()
        old = filename(self.now - dt.timedelta(days=7)); unknown = filename(self.now - dt.timedelta(days=8)); changed = filename(self.now - dt.timedelta(days=9))
        (directory / old).write_bytes(b'owned'); (directory / unknown).write_bytes(b'unrelated'); (directory / changed).write_bytes(b'modified')
        (directory / 'notes.txt').write_text('keep')
        (directory / 'sync-manifest.json').write_text(json.dumps({'version': 1, 'managed': [item(old, b'owned'), item(changed, b'original')]}))
        with patch.object(backup, '_ssh', side_effect=backup.SyncError('remote_unavailable')):
            result = backup.sync(self.profile)
        self.assertFalse(result['ok']); self.assertEqual(result['expired_count'], 1)
        self.assertFalse((directory / old).exists()); self.assertEqual((directory / unknown).read_bytes(), b'unrelated'); self.assertEqual((directory / changed).read_bytes(), b'modified'); self.assertTrue((directory / 'notes.txt').exists())
        self.assertEqual(json.loads((directory / 'sync-manifest.json').read_text())['managed'], [])

    def test_symlink_is_never_removed_or_overwritten(self):
        directory = self.root / 'prata-backups'; directory.mkdir(); outside = self.root / 'outside'; outside.write_bytes(b'keep')
        old = filename(self.now - dt.timedelta(days=7)); path = directory / old
        try: os.symlink(outside, path)
        except (OSError, NotImplementedError): self.skipTest('symlink creation unavailable')
        (directory / 'sync-manifest.json').write_text(json.dumps({'version': 1, 'managed': [item(old, b'keep')]}))
        with patch.object(backup, '_ssh', side_effect=backup.SyncError('remote_unavailable')): backup.sync(self.profile)
        self.assertTrue(path.is_symlink()); self.assertEqual(outside.read_bytes(), b'keep')

    def test_hardlink_is_never_removed_or_overwritten(self):
        directory = self.root / 'prata-backups'; directory.mkdir(); outside = self.root / 'outside'; outside.write_bytes(b'keep')
        old = filename(self.now - dt.timedelta(days=7)); path = directory / old
        try: os.link(outside, path)
        except (OSError, NotImplementedError): self.skipTest('hardlink creation unavailable')
        (directory / 'sync-manifest.json').write_text(json.dumps({'version': 1, 'managed': [item(old, b'keep')]}))
        with patch.object(backup, '_ssh', side_effect=backup.SyncError('remote_unavailable')): backup.sync(self.profile)
        self.assertTrue(path.exists()); self.assertEqual(outside.read_bytes(), b'keep')

    def test_link_marked_by_platform_is_never_deleted(self):
        directory=self.root/'prata-backups';directory.mkdir();old=filename(self.now-dt.timedelta(days=7));target=directory/old;target.write_bytes(b'keep')
        (directory/'sync-manifest.json').write_text(json.dumps({'version':1,'managed':[item(old,b'keep')]}));original=backup._linked
        with patch.object(backup,'_linked',side_effect=lambda p: p==target or original(p)),patch.object(backup,'_ssh',side_effect=backup.SyncError('remote_unavailable')):
            result=backup.sync(self.profile)
        self.assertFalse(result['ok']);self.assertEqual(result['expired_count'],0);self.assertEqual(target.read_bytes(),b'keep')

    def test_checksum_mismatch_preserves_existing_files_and_cleans_temp(self):
        self.remote['sha256'] = '0' * 64
        with patch.object(backup, '_ssh', side_effect=self.ssh): result = backup.sync(self.profile)
        directory = self.root / 'prata-backups'
        self.assertFalse(result['ok']); self.assertEqual(result['error'], 'checksum_mismatch')
        self.assertFalse((directory / self.name).exists()); self.assertFalse(list(directory.glob('.prata-sync-*')))

    def test_unmanaged_same_name_and_conflict_are_never_claimed_or_overwritten(self):
        directory = self.root / 'prata-backups'; directory.mkdir(); (directory / self.name).write_bytes(self.data)
        with patch.object(backup, '_ssh', side_effect=self.ssh): result = backup.sync(self.profile)
        self.assertTrue(result['ok']); self.assertFalse(result['copied']); self.assertFalse(result['managed'])
        (directory / self.name).write_bytes(b'other')
        with patch.object(backup, '_ssh', side_effect=self.ssh): result = backup.sync(self.profile)
        self.assertFalse(result['ok']); self.assertEqual(result['error'], 'local_name_conflict'); self.assertEqual((directory / self.name).read_bytes(), b'other')

    def test_invalid_remote_and_manifest_inputs_fail_closed(self):
        for bad in [dict(self.remote, filename='../private'), dict(self.remote, size=backup.MAX_BYTES+1), dict(self.remote, size=True), dict(self.remote, sha256='0'*63), dict(self.remote, filename=filename(self.now-dt.timedelta(days=8)))]:
            self.remote = bad
            with patch.object(backup, '_ssh', side_effect=self.ssh): result = backup.sync(self.profile)
            self.assertFalse(result['ok']); self.assertFalse(list((self.root/'prata-backups').glob('*.age')))
        directory=self.root/'prata-backups'; (directory/'sync-manifest.json').write_text(json.dumps({'version':1,'managed':[item('../outside', b'x')]}))
        with patch.object(backup, '_ssh', side_effect=self.ssh) as remote:
            result=backup.sync(self.profile)
        self.assertEqual(result['error'],'unsafe_manifest'); remote.assert_not_called()

    def test_invalid_runtime_root_is_rejected(self):
        self.assertEqual(backup.sync({'runtime_root':'.'})['error'],'invalid_runtime_root')
        self.assertEqual(backup.sync([])['error'],'invalid_runtime_root')

    def test_remote_programs_compile_and_transport_timeout_terminates_child(self):
        compile(backup.REMOTE_META,'remote-meta','exec');compile(backup.REMOTE_COPY,'remote-copy','exec')
        started=time.monotonic()
        with patch.object(backup,'SSH',[sys.executable,'-c','import time;time.sleep(10)']):
            with self.assertRaises(backup.SyncError) as error:backup._ssh('unused',lambda _:None,100,.3)
        self.assertEqual(str(error.exception),'ssh_timeout');self.assertLess(time.monotonic()-started,5)

    def test_ssh_is_strict_bounded_and_has_no_shell(self):
        class FakeProcess:
            def __init__(self, data): self.stdout=io.BytesIO(data); self.done=False; self.killed=False
            def wait(self, timeout=None): self.done=True; return 0
            def poll(self): return 0 if self.done else None
            def kill(self): self.killed=True; self.done=True
        process=FakeProcess(b'abc')
        with patch.object(backup.sp, 'Popen', return_value=process) as popen:
            data=io.BytesIO(); self.assertEqual(backup._ssh('fixed-command',data.write,3,10),3)
        args,kwargs=popen.call_args; self.assertIn('StrictHostKeyChecking=yes',args[0]); self.assertIn('BatchMode=yes',args[0]); self.assertEqual(args[0][-2:],[ 'openclaw','fixed-command']); self.assertNotIn('shell',kwargs); self.assertEqual(data.getvalue(),b'abc')
        process=FakeProcess(b'abcd')
        with patch.object(backup.sp,'Popen',return_value=process):
            with self.assertRaises(backup.SyncError):backup._ssh('fixed-command',lambda _:None,3,10)
        self.assertTrue(process.killed)

if __name__ == '__main__': unittest.main()
