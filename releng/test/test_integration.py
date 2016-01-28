import os.path
import unittest

from releng.test.utils import TestHelper

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
