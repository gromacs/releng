import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.script import BuildScript

from releng.test.utils import TestHelper

class TestBuildScript(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self)

    def test_EmptyScript(self):
        executor = self.helper.executor
        self.helper.add_input_file('build.py',
                """\
                def do_build(context):
                    pass
                """);
        script = BuildScript(executor, 'build.py')
        self.assertEqual(script.settings.build_opts, [])
        self.assertFalse(script.settings.build_out_of_source)
        self.assertEqual(script.settings.extra_projects, [])

    def test_SetGlobals(self):
        executor = self.helper.executor
        self.helper.add_input_file('build.py',
                """\
                build_options = ['foo', 'bar']
                build_out_of_source = True
                extra_projects = [Project.REGRESSIONTESTS]
                def do_build(context):
                    pass
                """);
        script = BuildScript(executor, 'build.py')
        self.assertEqual(script.settings.build_opts, ['foo', 'bar'])
        self.assertTrue(script.settings.build_out_of_source)
        self.assertEqual(script.settings.extra_projects, [Project.REGRESSIONTESTS])

if __name__ == '__main__':
    unittest.main()
