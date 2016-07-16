import base64
import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import BuildError, Project
from releng.integration import BuildParameters, ParameterTypes, RefSpec
from releng.test.utils import TestHelper

class TestRefSpec(unittest.TestCase):
    def test_NoOpRef(self):
        refspec = RefSpec('HEAD')
        self.assertTrue(refspec.is_no_op)
        self.assertFalse(refspec.is_tarball)
        self.assertEqual(str(refspec), 'HEAD')

    def test_ChangeRef(self):
        value = 'refs/changes/34/1234/3'
        refspec = RefSpec(value)
        self.assertFalse(refspec.is_no_op)
        self.assertFalse(refspec.is_tarball)
        self.assertTrue(refspec.is_static)
        self.assertEqual(refspec.fetch, value)
        self.assertEqual(refspec.checkout, 'FETCH_HEAD')
        self.assertEqual(str(refspec), value)

    def test_BranchRef(self):
        value = 'refs/heads/master'
        refspec = RefSpec(value)
        self.assertFalse(refspec.is_no_op)
        self.assertFalse(refspec.is_tarball)
        self.assertFalse(refspec.is_static)
        self.assertEqual(refspec.fetch, value)
        self.assertEqual(refspec.checkout, 'FETCH_HEAD')
        self.assertEqual(str(refspec), value)

    def test_BranchRefWithHash(self):
        value = 'refs/heads/master'
        refspec = RefSpec(value, '1234abcd')
        self.assertFalse(refspec.is_no_op)
        self.assertFalse(refspec.is_tarball)
        self.assertFalse(refspec.is_static)
        self.assertEqual(refspec.fetch, value)
        self.assertEqual(refspec.checkout, '1234abcd')
        self.assertEqual(str(refspec), value)

    def test_TarballRef(self):
        helper = TestHelper(self)
        helper.add_input_file('tarballs/gromacs/package-info.log', """\
                PACKAGE_FILE_NAME = gromacs-xyz-dev.tar.gz
                HEAD_HASH = 1234abcd
                """)
        refspec = RefSpec('tarballs/gromacs', executor=helper.executor)
        self.assertFalse(refspec.is_no_op)
        self.assertTrue(refspec.is_tarball)
        self.assertFalse(refspec.is_static)
        self.assertEqual(refspec.tarball_path, 'tarballs/gromacs/gromacs-xyz-dev.tar.gz')
        self.assertEqual(str(refspec), 'tarballs/gromacs')


class TestGerritIntegration(unittest.TestCase):
    def test_ManualTrigger(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'refs/changes/34/1234/5',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.GROMACS)
        self.assertEqual(gerrit.get_refspec(Project.GROMACS).fetch, 'refs/changes/34/1234/5')
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')

    def test_GerritTrigger(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/changes/34/1234/5',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.GROMACS)
        self.assertEqual(gerrit.get_refspec(Project.GROMACS).fetch, 'refs/changes/34/1234/5')
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')

    def test_GerritTriggerInWorkflowSecondaryCheckout(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.RELENG)
        self.assertEqual(gerrit.get_refspec(Project.GROMACS).fetch, 'refs/changes/34/1234/5')
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')

    def test_ManualTriggerWithHash(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'GROMACS_HASH': '1234abcd',
                'RELENG_REFSPEC': 'refs/heads/master',
                'RELENG_HASH': '5678abcd'
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.GROMACS)
        self.assertEqual(gerrit.get_refspec(Project.GROMACS).fetch, 'refs/heads/master')
        self.assertEqual(gerrit.get_refspec(Project.GROMACS).checkout, '1234abcd')
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')
        self.assertEqual(gerrit.get_refspec(Project.RELENG).checkout, '5678abcd')

    def test_TarballsWithManualTrigger(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'tarballs/gromacs',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('tarballs/gromacs/package-info.log', """\
                HEAD_HASH = 1234abcd
                """)
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.RELENG)
        self.assertTrue(gerrit.get_refspec(Project.GROMACS).is_tarball)
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')

    def test_TarballsWithGerritTrigger(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'tarballs/gromacs',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('tarballs/gromacs/package-info.log', """\
                HEAD_HASH = 1234abcd
                """)
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.checked_out_project, Project.RELENG)
        self.assertTrue(gerrit.get_refspec(Project.GROMACS).is_tarball)
        self.assertEqual(gerrit.get_refspec(Project.RELENG).fetch, 'refs/heads/master')

    def test_SimpleTriggeringComment(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_SimpleTriggeringCommentWithNewline(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage\n')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_TriggeringCommentWithLeadingText(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('Text\n\n[JENKINS] Coverage')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_TriggeringCommentWithTrailingText(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage\n\nText')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_MultilineTriggeringComment(self):
        helper = TestHelper(self, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS]\nCoverage\nMore')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage\nMore')


class TestBuildParameters(unittest.TestCase):
    def test_Unknown(self):
        helper = TestHelper(self)
        params = BuildParameters(helper.factory)
        self.assertIsNone(params.get('FOO', ParameterTypes.bool))

    def test_Boolean(self):
        helper = TestHelper(self, env={ 'FOO': 'true', 'BAR': 'false' })
        params = BuildParameters(helper.factory)
        self.assertEqual(params.get('FOO', ParameterTypes.bool), True)
        self.assertEqual(params.get('BAR', ParameterTypes.bool), False)

    def test_String(self):
        helper = TestHelper(self, env={ 'FOO': 'text' })
        params = BuildParameters(helper.factory)
        self.assertEqual(params.get('FOO', ParameterTypes.string), 'text')


class TestStatusReporter(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self, workspace='ws')

    def test_Success(self):
        with self.helper.factory.status_reporter as status_reporter:
            self.assertFalse(status_reporter.failed)
        self.assertFalse(status_reporter.failed)
        self.assertEqual(self.helper.executor.mock_calls,
                [mock.call.remove_path('logs/unsuccessful-reason.log')])
        self.helper.assertConsoleOutput('')

    def test_Failure(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_failed('Failure reason')
            self.assertTrue(status_reporter.failed)
        self.helper.assertConsoleOutput("""\
                Build FAILED:
                  Failure reason
                """)
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                Failure reason
                """)

    def test_Unstable(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_unstable('Unstable reason')
            self.assertFalse(status_reporter.failed)
        self.helper.assertConsoleOutput("""\
                FAILED: Unstable reason
                Build FAILED:
                  Unstable reason
                """)
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                Unstable reason
                """)

    def test_BuildError(self):
        self.helper.factory.init_status_reporter(tracebacks=False)
        with self.helper.factory.status_reporter:
            raise BuildError('Mock build error')
        self.assertTrue(self.helper.factory.status_reporter.failed)
        self.helper.assertConsoleOutput("""\
                BuildError: Mock build error
                Build FAILED:
                  Mock build error
                """)
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                Mock build error
                """)

    def test_OtherError(self):
        self.helper.factory.init_status_reporter(tracebacks=False)
        with self.assertRaises(ValueError):
            with self.helper.factory.status_reporter:
                raise ValueError('Mock Python error')
        self.helper.assertConsoleOutput('')
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                ValueError: Mock Python error
                """)


class TestStatusReporterJson(unittest.TestCase):
    def setUp(self):
        env = {
                'STATUS_FILE': 'logs/status.json'
            }
        self.helper = TestHelper(self, workspace='ws', env=env)

    def test_Success(self):
        with self.helper.factory.status_reporter as status_reporter:
            self.assertFalse(status_reporter.failed)
        self.assertFalse(status_reporter.failed)
        self.helper.assertConsoleOutput('')
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'SUCCESS',
                'reason': None
            })

    def test_Failure(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_failed('Failure reason')
        self.helper.executor.exit.assert_called_with(1)
        self.helper.assertConsoleOutput("""\
                Build FAILED:
                  Failure reason
                """)
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'FAILURE',
                'reason': 'Failure reason'
            })

    def test_Unstable(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_unstable('Unstable reason')
        self.assertFalse(self.helper.executor.exit.called)
        self.helper.assertConsoleOutput("""\
                FAILED: Unstable reason
                Build FAILED:
                  Unstable reason
                """)
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'UNSTABLE',
                'reason': 'Unstable reason'
            })


class TestStatusReporterNoPropagate(unittest.TestCase):
    def setUp(self):
        env = {
                'STATUS_FILE': 'logs/status.json',
                'NO_PROPAGATE_FAILURE': '1'
            }
        self.helper = TestHelper(self, workspace='ws', env=env)

    def test_Failure(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_failed('Failure reason')
        self.assertFalse(self.helper.executor.exit.called)
        self.helper.assertConsoleOutput("""\
                Build FAILED:
                  Failure reason
                """)
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'FAILURE',
                'reason': 'Failure reason'
            })

if __name__ == '__main__':
    unittest.main()
