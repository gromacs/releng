"""
Provides mockable object for all operations that affect the external state

The Executor object is used in Jenkins builds, but a DryRunExecutor can be
dropped into its place for local testing, and unit tests can use a mock
Executor object instead.

All operations that interact with the world outside the releng script (such as
the file system or external commands) should be wrapped within the Executor
object to allow the above replacements to work as intended.  For now, this is
not used throughout the scripts, but its use and scope will be extended with
expanding unit tests.
"""
from __future__ import print_function

import os
import shutil
import sys

def _ensure_abs_path(path, cwd):
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return path

def _read_file(path, binary):
    if binary:
        with open(path, 'rb') as fp:
            for block in iter(lambda: fp.read(4096), b''):
                yield block
    else:
        with open(path, 'r') as fp:
            for line in fp:
                yield line

class Executor(object):
    """Real executor for Jenkins builds that does all operations for real."""

    def __init__(self, factory):
        self._cwd = factory.cwd

    @property
    def console(self):
        return sys.stdout

    def exit(self, exitcode):
        sys.exit(exitcode)

    def ensure_dir_exists(self, path, ensure_empty=False):
        """Ensures that a directory exists and optionally that it is empty."""
        path = _ensure_abs_path(path, self._cwd.cwd)
        if ensure_empty:
            if os.path.exists(path):
                shutil.rmtree(path)
        elif os.path.isdir(path):
            return
        os.makedirs(path)

    def read_file(self, path, binary=False):
        """Iterates over lines in a file."""
        path = _ensure_abs_path(path, self._cwd.cwd)
        return _read_file(path, binary)

    def write_file(self, path, contents):
        """Writes a file with the given contents."""
        path = _ensure_abs_path(path, self._cwd.cwd)
        with open(path, 'w') as fp:
            fp.write(contents)

class DryRunExecutor(object):
    """Executor replacement for manual testing dry runs."""

    def __init__(self, factory):
        self._cwd = factory.cwd

    @property
    def console(self):
        return sys.stdout

    def exit(self, exitcode):
        sys.exit(exitcode)

    def ensure_dir_exists(self, path, ensure_empty=False):
        pass

    def read_file(self, path, binary=False):
        path = _ensure_abs_path(path, self._cwd.cwd)
        return _read_file(path, binary)

    def write_file(self, path, contents):
        print('write: ' + path + ' <<<')
        print(contents + '<<<')

class CurrentDirectoryTracker(object):
    """Helper class for tracking the current directory for command execution."""

    def __init__(self):
        self.cwd = os.getcwd()

    def chdir(self, path):
        assert os.path.isabs(path)
        self.cwd = path
