from StringIO import StringIO
import textwrap
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.context import ContextFactory
from releng.executor import Executor

class TestHelper(object):
    def __init__(self, test, workspace=None, env=dict()):
        self._test = test
        self._console = None
        self.executor = mock.create_autospec(Executor, spec_set=True, instance=True)
        self.executor.check_output.side_effect = self._check_output
        self.executor.read_file.side_effect = self._read_file
        self.executor.write_file.side_effect = self._write_file
        self.reset_console_output()

        if workspace:
            env['WORKSPACE'] = workspace
            if 'CHECKOUT_PROJECT' not in env:
                env['CHECKOUT_PROJECT'] = Project.GROMACS
            if 'CHECKOUT_REFSPEC' not in env:
                env['CHECKOUT_REFSPEC'] = 'HEAD'
            if 'GROMACS_REFSPEC' not in env:
                env['GROMACS_REFSPEC'] = 'HEAD'
            if 'RELENG_REFSPEC' not in env:
                env['RELENG_REFSPEC'] = 'HEAD'
            if 'REGRESSIONTESTS_REFSPEC' not in env:
                env['REGRESSIONTESTS_REFSPEC'] = 'HEAD'
        self.factory = ContextFactory(env=env)
        self.factory.init_executor(instance=self.executor)
        if workspace:
            self.factory.init_workspace()
            self.executor.reset_mock()
            self.reset_console_output()
        self._input_files = dict()
        self._output_files = dict()

    def reset_console_output(self):
        self._console = StringIO()
        type(self.executor).console = mock.PropertyMock(return_value=self._console)

    def _check_output(self, cmd, **kwargs):
        if cmd == ['git', 'rev-list', '-n1', '--format=oneline', 'HEAD']:
            sha1 = '1234567890abcdef0123456789abcdef01234567'
            title = 'Mock title'
            return '{0} {1}\n'.format(sha1, title)
        return None

    def _read_file(self, path):
        if path not in self._input_files:
            raise IOError(path + ': not part of test')
        return self._input_files[path]

    def _write_file(self, path, contents):
        self._output_files[path] = contents

    def add_input_file(self, path, contents):
        lines = textwrap.dedent(contents).splitlines(True)
        self._input_files[path] = lines

    def assertConsoleOutput(self, expected):
        text = textwrap.dedent(expected)
        self._test.assertEqual(text, self._console.getvalue())

    def assertOutputFile(self, path, expected):
        if path not in self._output_files:
            self._test.fail('output file not produced: ' + path)
        text = textwrap.dedent(expected)
        self._test.assertEqual(text, self._output_files[path])
