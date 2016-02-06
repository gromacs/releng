import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import JobType
from releng.context import BuildContext

from releng.test.utils import TestHelper

class TestRunBuild(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self, workspace='/ws')

    def test_NoOptions(self):
        self.helper.add_input_file('script/build.py',
                """\
                def do_build(context):
                    pass
                """);
        BuildContext._run_build(self.helper.factory,
                'script/build.py', JobType.GERRIT, None)

    def test_ScriptOptions(self):
        self.helper.add_input_file('script/build.py',
                """\
                build_options = ['gcc-4.8']
                def do_build(context):
                    pass
                """);
        BuildContext._run_build(self.helper.factory,
                'script/build.py', JobType.GERRIT, None)

    def test_MixedOptions(self):
        self.helper.add_input_file('script/build.py',
                """\
                build_options = ['gcc-4.8']
                def do_build(context):
                    pass
                """);
        BuildContext._run_build(self.helper.factory,
                'script/build.py', JobType.GERRIT, ['build-jobs=3'])

    def test_ExtraOptions(self):
        self.helper.add_input_file('script/build.py',
                """\
                TestEnum = Enum.create('TestEnum', 'foo', 'bar')
                extra_options = {
                    'extra': Option.simple,
                    'enum': Option.enum(TestEnum)
                }
                def do_build(context):
                    pass
                """);
        BuildContext._run_build(self.helper.factory,
                'script/build.py', JobType.GERRIT, ['extra', 'enum=foo'])

    def test_Parameters(self):
        self.helper.add_input_file('script/build.py',
                """\
                def do_build(context):
                    context.params.get('PARAM', Parameter.bool)
                """);
        BuildContext._run_build(self.helper.factory,
                'script/build.py', JobType.GERRIT, None)

if __name__ == '__main__':
    unittest.main()
