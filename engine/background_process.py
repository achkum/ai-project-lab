"""Run unattended child processes without creating Windows console windows."""
import os
import subprocess as _subprocess
from subprocess import PIPE, STDOUT, DEVNULL, TimeoutExpired, CalledProcessError


def _options(kwargs):
    options = dict(kwargs)
    if os.name == 'nt':
        options['creationflags'] = options.get('creationflags', 0) | _subprocess.CREATE_NO_WINDOW
    return options


def run(*args, **kwargs):
    return _subprocess.run(*args, **_options(kwargs))


def Popen(*args, **kwargs):
    return _subprocess.Popen(*args, **_options(kwargs))


def check_output(*args, **kwargs):
    return _subprocess.check_output(*args, **_options(kwargs))
