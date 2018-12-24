import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.matrixbuild import prepare_build_matrix

from releng.test.utils import TestHelper

class TestPrepareBuildMatrix(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self, workspace='ws')

    def test_PrepareBuildMatrix(self):
        factory = self.helper.factory
        executor = self.helper.executor
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        self.helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        result = prepare_build_matrix(factory, 'pre-submit-matrix')
        self.assertEqual(result, {
                "configs": [
                    {
                        "host": "bs_nix1310",
                        "labels": "cuda-5.0 && gcc-4.6",
                        "opts": ["gcc-4.6", "gpu", "cuda-5.0"]
                    },
                    {
                        "host": "bs-win2012r2",
                        "labels": "msvc-2013",
                        "opts": ["msvc-2013"]
                    }
                ],
                "as_axis": '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
            })

if __name__ == '__main__':
    unittest.main()
