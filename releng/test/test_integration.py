import base64
import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import AbortError, BuildError, Project
from releng.integration import BuildParameters, ParameterTypes, RefSpec
from releng.test.utils import RepositoryTestState, TestHelper

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
        self.assertEqual(refspec.change_number, '1234')
        self.assertEqual(str(refspec), value)

    def test_BranchRef(self):
        value = 'refs/heads/master'
        refspec = RefSpec(value)
        self.assertFalse(refspec.is_no_op)
        self.assertFalse(refspec.is_tarball)
        self.assertFalse(refspec.is_static)
        self.assertEqual(refspec.fetch, value)
        self.assertEqual(refspec.checkout, 'FETCH_HEAD')
        self.assertEqual(refspec.branch, 'master')
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


class TestProjectsManager(unittest.TestCase):
    def verifyProjectInfo(self, projects, commits, expect_hashes=False, tarball=None):
        for project in commits.projects:
            info = projects.get_project_info(project, expect_checkout=False)
            if tarball and project == tarball:
                self.assertTrue(info.is_tarball)
                continue
            reference = commits.get_head(project)
            self.assertEqual(info.refspec.fetch, reference.refspec)
            if expect_hashes:
                self.assertEqual(info.refspec.checkout, reference.sha1)
            else:
                self.assertEqual(info.refspec.checkout, 'FETCH_HEAD')

    def test_ManualTrigger(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': commits.gromacs.refspec,
                'GROMACS_REFSPEC': commits.gromacs.refspec,
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits)

    def test_GerritTrigger(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': commits.gromacs.refspec,
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits)

    def test_GerritTriggerInPipeline(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits)

    def test_ManualTriggerWithEmptyHash(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': commits.gromacs.refspec,
                'GROMACS_REFSPEC': commits.gromacs.refspec,
                'GROMACS_HASH': '',
                'RELENG_REFSPEC': 'refs/heads/master',
                'RELENG_HASH': ''
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits)

    def test_ManualTriggerWithHash(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/heads/master',
                'GROMACS_REFSPEC': 'refs/heads/master',
                'GROMACS_HASH': commits.gromacs.sha1,
                'RELENG_REFSPEC': 'refs/heads/master',
                'RELENG_HASH': commits.releng.sha1
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits, expect_hashes=True)

    def test_TarballsWithManualTrigger(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'GROMACS_REFSPEC': 'tarballs/gromacs',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('tarballs/gromacs/package-info.log', """\
                HEAD_HASH = 1234abcd
                """)
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits, tarball=Project.GROMACS)

    def test_TarballsWithGerritTrigger(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'tarballs/gromacs',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('tarballs/gromacs/package-info.log', """\
                HEAD_HASH = 1234abcd
                """)
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits, tarball=Project.GROMACS)

    def test_Checkout(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG, change_number=1234)
        helper = TestHelper(self, commits=commits, env={
                'CHECKOUT_PROJECT': 'releng',
                'CHECKOUT_REFSPEC': commits.releng.refspec,
                'GROMACS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        projects = helper.factory.projects
        self.verifyProjectInfo(projects, commits)
        projects.checkout_project(Project.GROMACS)
        # TODO: Verify some of the results

    def test_GetBuildRevisions(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.REGRESSIONTESTS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits)
        projects = helper.factory.projects
        result = projects.get_build_revisions()
        self.assertEqual(result, commits.expected_build_revisions)

    def test_GetBuildRevisionsNoRegressionTests(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits)
        projects = helper.factory.projects
        result = projects.get_build_revisions()
        self.assertEqual(result, commits.expected_build_revisions)


class TestGerritIntegration(unittest.TestCase):
    def test_SimpleTriggeringComment(self):
        helper = TestHelper(self, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_SimpleTriggeringCommentWithNewline(self):
        helper = TestHelper(self, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage\n')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_TriggeringCommentWithLeadingText(self):
        helper = TestHelper(self, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('Text\n\n[JENKINS] Coverage')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_TriggeringCommentWithTrailingText(self):
        helper = TestHelper(self, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage\n\nText')
            })
        gerrit = helper.factory.gerrit
        self.assertEqual(gerrit.get_triggering_comment(), 'Coverage')

    def test_MultilineTriggeringComment(self):
        helper = TestHelper(self, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'refs/heads/master',
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

    def test_Aborted(self):
        with self.helper.factory.status_reporter as status_reporter:
            raise AbortError(143)
        self.assertFalse(status_reporter.failed)
        self.assertEqual(self.helper.executor.mock_calls,
                [mock.call.remove_path('logs/unsuccessful-reason.log'),
                 mock.call.exit(143)])
        self.helper.assertConsoleOutput('')

    def test_AbortedAfterFailure(self):
        with self.helper.factory.status_reporter as status_reporter:
            status_reporter.mark_failed('Failure reason')
            raise AbortError(143)
        self.assertTrue(status_reporter.failed)
        self.assertEqual(self.helper.executor.mock_calls,
                [mock.call.remove_path('logs/unsuccessful-reason.log'),
                 mock.call.exit(143)])
        self.helper.assertConsoleOutput('')


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

    def test_Aborted(self):
        with self.helper.factory.status_reporter as status_reporter:
            raise AbortError(143)
        self.assertFalse(status_reporter.failed)
        self.helper.executor.exit.assert_called_with(143)
        self.helper.assertConsoleOutput('')
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'ABORTED',
                'reason': None
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

    def test_Aborted(self):
        with self.helper.factory.status_reporter as status_reporter:
            raise AbortError(143)
        self.assertFalse(self.helper.executor.exit.called)
        self.helper.assertOutputJsonFile('ws/logs/status.json', {
                'result': 'ABORTED',
                'reason': None
            })

if __name__ == '__main__':
    unittest.main()
