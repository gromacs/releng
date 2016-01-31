import os.path
import unittest

from releng.common import Project
from releng.integration import RefSpec
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


class TestFailureTracker(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self, workspace='ws')

    def test_Success(self):
        executor = self.helper.executor
        failure_tracker = self.helper.factory.failure_tracker
        self.assertFalse(failure_tracker.failed)
        failure_tracker.report(self.helper.factory.workspace)
        self.assertFalse(failure_tracker.failed)
        self.assertFalse(executor.mock_calls)

    def test_Failure(self):
        failure_tracker = self.helper.factory.failure_tracker
        failure_tracker.mark_failed('Failure reason')
        self.assertTrue(failure_tracker.failed)
        failure_tracker.report(self.helper.factory.workspace)
        self.helper.assertConsoleOutput("""\
                Build FAILED:
                  Failure reason
                """)
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                Failure reason
                """)

    def test_Unstable(self):
        failure_tracker = self.helper.factory.failure_tracker
        failure_tracker.mark_unstable('Unstable reason')
        self.assertFalse(failure_tracker.failed)
        failure_tracker.report(self.helper.factory.workspace)
        self.helper.assertConsoleOutput("""\
                FAILED: Unstable reason
                Build FAILED:
                  Unstable reason
                """)
        self.helper.assertOutputFile('ws/logs/unsuccessful-reason.log',
                """\
                Unstable reason
                """)

if __name__ == '__main__':
    unittest.main()
