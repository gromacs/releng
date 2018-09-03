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

from distutils.spawn import find_executable
import os
import pipes
import re
import shutil
import subprocess
import sys

from common import AbortError, CommandError, System
import utils

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

    def call(self, cmd, **kwargs):
        return subprocess.call(cmd, **kwargs)

    def check_call(self, cmd, **kwargs):
        subprocess.check_call(cmd, **kwargs)

    def check_output(self, cmd, **kwargs):
        return subprocess.check_output(cmd, **kwargs)

    def remove_path(self, path):
        """Deletes a file or a directory at a given path if it exists."""
        path = self._cwd.to_abs_path(path)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)

    def ensure_dir_exists(self, path, ensure_empty=False):
        """Ensures that a directory exists and optionally that it is empty."""
        path = self._cwd.to_abs_path(path)
        if ensure_empty:
            self.remove_path(path)
        elif os.path.isdir(path):
            return
        os.makedirs(path)

    def copy_file(self, source, dest):
        """Copies a file."""
        source = self._cwd.to_abs_path(source)
        dest = self._cwd.to_abs_path(dest)
        if os.path.isfile(source):
            shutil.copy(source, dest)

    def read_file(self, path, binary=False):
        """Iterates over lines in a file."""
        path = self._cwd.to_abs_path(path)
        return _read_file(path, binary)

    def write_file(self, path, contents):
        """Writes a file with the given contents."""
        path = self._cwd.to_abs_path(path)
        with open(path, 'w') as fp:
            fp.write(contents)

    def find_executable_with_path(self, name, environment_path):
        """Returns the full path to the given executable,
        including resolving symlinks."""
        # If we at some point require Python 3.3, shutil.which() would be
        # more obvious.
        return os.path.realpath(find_executable(name, environment_path))

class DryRunExecutor(object):
    """Executor replacement for manual testing dry runs."""

    def __init__(self, factory):
        self._cwd = factory.cwd

    @property
    def console(self):
        return sys.stdout

    def exit(self, exitcode):
        sys.exit(exitcode)

    def call(self, cmd, **kwargs):
        return 0

    def check_call(self, cmd, **kwargs):
        pass

    def check_output(self, cmd, **kwargs):
        return subprocess.check_output(cmd, **kwargs)

    def remove_path(self, path):
        print('delete: ' + path)

    def ensure_dir_exists(self, path, ensure_empty=False):
        pass

    def copy_file(self, source, dest):
        print('copy {0} -> {1}'.format(source, dest))
        if os.path.isfile(source):
            shutil.copy(source, dest)

    def read_file(self, path, binary=False):
        path = self._cwd.to_abs_path(path)
        return _read_file(path, binary)

    def write_file(self, path, contents):
        print('write: ' + path + ' <<<')
        print(contents + '<<<')

    def find_executable_with_path(self, name, environment_path):
        print('find: ' + name)
        return '/usr/local/bin/' + name

class CurrentDirectoryTracker(object):
    """Helper class for tracking the current directory for command execution."""

    def __init__(self):
        self.cwd = os.getcwd()
        self._dirstack = []

    def chdir(self, path):
        assert os.path.isabs(path)
        self.cwd = path

    def to_abs_path(self, path):
        if not os.path.isabs(path):
            return os.path.join(self.cwd, path)
        return path

    def pushd(self, path):
        self._dirstack.append(self.cwd)
        self.chdir(path)

    def popd(self):
        self.chdir(self._dirstack.pop())

class CommandRunner(object):

    def __init__(self, factory):
        self._cwd = factory.cwd
        self._env = dict(factory.env)
        self._shell_call_opts = dict()
        if factory.system and factory.system != System.WINDOWS:
            self._shell_call_opts['executable'] = '/bin/bash'
        self._is_windows = factory.system and factory.system == System.WINDOWS
        self._executor = factory.executor

    def set_env_var(self, variable, value):
        if value is not None:
            self._env[variable] = value

    def append_to_env_var(self, variable, value, sep=' '):
        if variable in self._env and self._env[variable]:
            self._env[variable] += sep + value
        else:
            self._env[variable] = value

    def prepend_to_env_var(self, variable, value, sep=' '):
        if variable in self._env and self._env[variable]:
            self._env[variable] = sep.join((value, self._env[variable]))
        else:
            self._env[variable] = value

    def copy_env_var(self, to_variable, from_variable):
        self._env[to_variable] = self._env[from_variable]

    def import_env(self, env_dump_cmd):
        """Runs env_dump_cmd and uses its output to import values into the current environment.

        The output of env_dump_cmd should contain lines of "key=value"
        for the environment variables present, e.g. as created by
        cmake -E environment.  Normally used to capture and import the
        environment resulting from sourcing a script that sets up the
        environment to use a particular build toolchain.
        """
        new_env = self.check_output(env_dump_cmd, shell=True)
        if new_env:
            for line in new_env.splitlines():
                if re.match(r'\w+=', line):
                    variable, value = line.strip().split('=', 1)
                    self._env[variable] = value
                else:
                    print(line, file=self._executor.console)

    def call(self, cmd, **kwargs):
        """Runs a command via subprocess.call()

        This wraps subprocess.call() with error-handling and other
        generic handling such as ensuring proper output flushing and
        using bash as the shell on Unix.

        Any arguments accepted by subprocess.call() can also be
        passed, e.g. cwd or env to make such calls in stateless ways.
        """
        cmd_string, kwargs = self._prepare_cmd(cmd, kwargs)
        returncode = self._executor.call(cmd, **kwargs)
        self._handle_return_code(returncode)
        return returncode

    def check_call(self, cmd, **kwargs):
        """Runs a command via subprocess.check_call()

        This wraps subprocess.check_call() with error-handling and
        generic handling such as ensuring proper output flushing and
        using bash as the shell on Unix.

        Any arguments accepted by subprocess.check_call() can also be
        passed, e.g. cwd or env to make such calls in stateless ways.
        """
        cmd_string, kwargs = self._prepare_cmd(cmd, kwargs)
        try:
            self._executor.check_call(cmd, **kwargs)
        except subprocess.CalledProcessError as e:
            self._handle_return_code(e.returncode)
            raise CommandError(cmd_string)

    def check_output(self, cmd, **kwargs):
        """Runs a command via subprocess_check_output().

        This wraps subprocess.check_output() with error-handling and
        other generic handling such as ensuring proper output flushing
        and using bash as the shell on Unix.

        Any arguments accepted by subprocess.check_output() can also
        be passed, e.g. cwd or env to make such calls in stateless
        ways.
        """
        cmd_string, kwargs = self._prepare_cmd(cmd, kwargs)
        try:
            return self._executor.check_output(cmd, **kwargs)
        except subprocess.CalledProcessError as e:
            if e.output:
                print(e.output, file=self._executor.console)
            self._handle_return_code(e.returncode)
            raise CommandError(cmd_string)

    def _prepare_cmd(self, cmd, kwargs):
        shell = kwargs.get('shell', False)
        cmd_string = self._cmd_to_string(cmd, shell)
        print('+ ' + cmd_string, file=self._executor.console)
        if shell:
            kwargs.update(self._shell_call_opts)
        if not 'cwd' in kwargs:
            kwargs['cwd'] = self._cwd.cwd
        if not 'env' in kwargs:
            kwargs['env'] = self._env
        utils.flush_output()
        return cmd_string, kwargs

    def _cmd_to_string(self, cmd, shell):
        """Converts a shell command from a string/list into properly escaped string."""
        if shell:
            return cmd
        elif self._is_windows:
            return subprocess.list2cmdline(cmd)
        else:
            return ' '.join([pipes.quote(x) for x in cmd])

    def _handle_return_code(self, returncode):
        if returncode != 0:
            print('(exited with code {0})'.format(returncode), file=self._executor.console)
        if self._is_windows:
            # Based on testing, at least a batch script returns -1 when aborted
            # as part of a workflow.
            # Timeouts do not work in Jenkins pipelines for bat scripts...
            if returncode == -1:
                raise AbortError(returncode)
        else:
            # Aborting a job seems to send SIGTERM to the child processes in
            # pipelines, which gives an exit code of 128+15 or -15.
            # Handle SIGKILL as well for robustness.
            if returncode in (-15, -9, 137, 143):
                raise AbortError(returncode)

    def find_executable(self, name):
        """Returns the full path to the given executable."""
        return self._executor.find_executable_with_path(name, environment_path=self._env['PATH'])
