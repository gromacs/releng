import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.matrixbuild import prepare_build_matrix
from releng.matrixbuild import write_triggered_build_url_file

from releng.test.utils import TestHelper

class TestTriggeredBuildUrl(unittest.TestCase):
    def setUp(self):
        env = {
                'JENKINS_URL': 'http://jenkins.gromacs.org/',
                'LAST_TRIGGERED_JOB_NAME': 'Test_Job',
                'TRIGGERED_BUILD_NUMBER_Test_Job': 42
        }
        self.helper = TestHelper(self, env=env)

    def test_TriggeredBuildUrl(self):
        factory = self.helper.factory
        executor = self.helper.executor
        write_triggered_build_url_file(factory, 'URL_TO_POST', 'build/url-to-post.txt')
        self.assertEqual(executor.method_calls, [
                mock.call.write_file('build/url-to-post.txt',
                    'URL_TO_POST = http://jenkins.gromacs.org/job/Test_Job/42/\n')
            ])

class TestPrepareBuildMatrix(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self, workspace='ws')

    def test_PrepareBuildMatrix(self):
        factory = self.helper.factory
        executor = self.helper.executor
        input_lines = [
                'gcc-4.6 gpu cuda-5.0 host=bs_nix1204',
                'clang-3.4 no-openmp asan host=bs_centos63',
                'msvc-2013 host=bs-win2012r2'
            ]
        self.helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        prepare_build_matrix(factory, 'pre-submit-matrix', 'matrix.txt')
        self.assertEqual(executor.method_calls, [
                mock.call.ensure_dir_exists('ws/build', ensure_empty=True),
                mock.call.read_file('ws/gromacs/admin/builds/pre-submit-matrix.txt'),
                mock.call.write_file('ws/build/matrix.txt',
                    'OPTIONS "{0}" "{1}" "{2}"\n'.format(*[x.strip() for x in input_lines]))
            ])

if __name__ == '__main__':
    unittest.main()