import unittest

from releng.options import process_build_options

class TestProcessBuildOptions(unittest.TestCase):
    def test_NoOptions(self):
        e, p, o = process_build_options(None, None)
        self.assertIs(o.gcc, None)
        self.assertIs(o.tsan, None)

    def test_BasicOptions(self):
        opts = ['gcc-4.8', 'build-jobs=3', 'no-openmp', 'double']
        e, p, o = process_build_options(None, opts)
        self.assertIs(o.tsan, None)
        self.assertEqual(o.gcc, '4.8')
        self.assertEqual(o.build_jobs, '3')
        self.assertEqual(o['build-jobs'], '3')
        self.assertEqual(o.openmp, False)
        self.assertEqual(o.double, True)
