import unittest

from releng.common import ConfigurationError
from releng.common import System, Project, JobType, Compiler, BuildType, Simd, FftLibrary

class TestEnums(unittest.TestCase):
    def test_System(self):
        self.assertEqual(System.WINDOWS, System.parse('Windows'))
        self.assertEqual(System.OSX, System.parse('darwin'))
        with self.assertRaises(ConfigurationError):
            System.validate('foo')
        with self.assertRaises(ConfigurationError):
            System.validate('Windows')
        try:
            System.validate(System.WINDOWS)
        except ConfigurationError:
            self.fail('validate did not accept System.WINDOWS')

    def test_Project(self):
        self.assertEqual(Project.GROMACS, Project.parse('gromacs'))

    def test_JobType(self):
        self.assertEqual(JobType.GERRIT, JobType.parse('Gerrit'))

    def test_Compiler(self):
        self.assertEqual(Compiler.INTEL, Compiler.parse('icc'))

    def test_BuildType(self):
        self.assertEqual(BuildType.DEBUG, BuildType.parse('debug'))

    def test_Simd(self):
        self.assertEqual(Simd.NONE, Simd.parse('none'))
        self.assertEqual(Simd.REFERENCE, Simd.parse('Reference'))
        self.assertEqual(Simd.SSE41, Simd.parse('sse4.1'))

    def test_FftLibrary(self):
        self.assertEqual(FftLibrary.MKL, FftLibrary.parse('MKL'))

if __name__ == '__main__':
    unittest.main()
