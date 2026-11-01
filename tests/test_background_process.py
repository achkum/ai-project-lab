import sys
import unittest
from unittest.mock import patch
from engine import background_process as process


class BackgroundProcessTests(unittest.TestCase):
    def test_windows_flags_preserve_existing_options(self):
        with patch.object(process.os, 'name', 'nt'), patch.object(process._subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True):
            for name in ('run', 'Popen', 'check_output'):
                with patch.object(process._subprocess, name) as call:
                    getattr(process, name)(['ssh', '-V'], creationflags=512, stdout=process.PIPE)
                    self.assertEqual(call.call_args.kwargs['creationflags'], 0x08000200)
                    self.assertEqual(call.call_args.kwargs['stdout'], process.PIPE)

    def test_posix_does_not_receive_windows_flag(self):
        with patch.object(process.os, 'name', 'posix'), patch.object(process._subprocess, 'run') as call:
            process.run(['ssh', '-V'], capture_output=True)
            self.assertNotIn('creationflags', call.call_args.kwargs)

    def test_real_child_keeps_piped_input_and_output(self):
        result = process.run([sys.executable, '-c', 'import sys; print(sys.stdin.read().upper())'], input='quiet', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'QUIET')
