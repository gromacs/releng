import textwrap
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.context import ContextFactory
from releng.executor import Executor

class TestHelper(object):
    def __init__(self, env):
        self.executor = mock.create_autospec(Executor, spec_set=True, instance=True)
        self.executor.read_file.side_effect = self._read_file
        self.factory = ContextFactory(env=env)
        self.factory.init_executor(self.executor)
        if 'WORKSPACE' in env:
            self.factory.init_workspace(skip_checkouts=True)
        self._input_files = dict()

    def add_input_file(self, path, contents):
        lines = textwrap.dedent(contents).splitlines(True)
        self._input_files[path] = lines

    def _read_file(self, path):
        if path not in self._input_files:
            raise IOError(path + ': not part of test')
        return self._input_files[path]
