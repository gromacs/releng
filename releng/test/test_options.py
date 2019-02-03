import unittest

from releng.test.utils import TestHelper

from releng.common import Enum, Simd
from releng.options import OptionTypes
from releng.options import process_build_options
from releng.script import BuildScriptSettings

class TestProcessBuildOptions(unittest.TestCase):
    def setUp(self):
        self.helper = TestHelper(self)
        self.settings = BuildScriptSettings()

    def test_NoOptions(self):
        e, o = process_build_options(self.helper.factory, None, self.settings)
        self.assertIs(o.gcc, None)
        self.assertIs(o.tsan, None)

    def test_BasicOptions(self):
        opts = ['gcc-4.8', 'build-jobs=3', 'simd=reference', 'x11']
        e, o = process_build_options(self.helper.factory, opts, self.settings)
        self.assertIs(o.tsan, None)
        self.assertEqual(o.gcc, '4.8')
        self.assertEqual(o.build_jobs, 3)
        self.assertEqual(o['build-jobs'], 3)
        self.assertEqual(o.simd, Simd.REFERENCE)
        self.assertEqual(o.x11, True)

    def test_ExtraOptions(self):
        TestEnum = Enum.create('TestEnum', 'foo', 'bar')
        self.settings.extra_options = {
            'extra': OptionTypes.simple,
            'ex-bool': OptionTypes.bool,
            'ex-string': OptionTypes.string,
            'ex-enum': OptionTypes.enum(TestEnum)
        }
        opts = ['gcc-4.8', 'extra', 'ex-bool=on', 'ex-string=foo', 'ex-enum=bar']
        e, o = process_build_options(self.helper.factory, opts, self.settings)
        self.assertEqual(o.extra, True)
        self.assertEqual(o.ex_bool, True)
        self.assertEqual(o.ex_string, 'foo')
        self.assertEqual(o.ex_enum, TestEnum.BAR)
