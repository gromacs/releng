import base64
import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.ondemand import get_actions_from_triggering_comment
from releng.ondemand import do_post_build

from releng.test.utils import TestHelper

class TestGetActionsFromTriggeringComment(unittest.TestCase):
    def test_CoverageRequest(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage')
            })
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'coverage'
                        }
                    ]
            })

        self.assertEqual(executor.method_calls, [
                mock.call.ensure_dir_exists('ws/build', ensure_empty=True),
                mock.call.write_file('ws/build/actions.json', mock.ANY)
            ])

    def test_PackageRequestForSource(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': 'HEAD',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Package')
            })
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'source-package'
                        }
                    ]
            })

        self.assertEqual(executor.method_calls, [
                mock.call.ensure_dir_exists('ws/build', ensure_empty=True),
                mock.call.write_file('ws/build/actions.json', mock.ANY)
            ])

    def test_PackageRequestForReleng(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_PROJECT': 'releng',
                'GERRIT_REFSPEC': 'HEAD',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Package')
            })
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'source-package'
                        },
                        {
                            'type': 'regtest-package'
                        }
                    ]
            })

        self.assertEqual(executor.method_calls, [
                mock.call.ensure_dir_exists('ws/build', ensure_empty=True),
                mock.call.write_file('ws/build/actions.json', mock.ANY)
            ])

    def test_PostSubmitRequest(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Post-submit')
            })
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        helper.add_input_file('ws/gromacs/admin/builds/post-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'post-submit',
                            'options': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
                        }
                    ]
            })

    def test_ReleaseBranchRequest(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] release-2016')
            })
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        self.maxDiff = None
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'release-2016',
                            'options': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
                        },
                        { 'type': 'clang-analyzer', 'desc': 'release-2016' },
                        { 'type': 'cppcheck', 'desc': 'release-2016' },
                        { 'type': 'documentation', 'desc': 'release-2016' },
                        { 'type': 'uncrustify', 'desc': 'release-2016' }
                    ],
                'env': {
                        'GROMACS_REFSPEC': 'refs/heads/release-2016',
                        'GROMACS_HASH': '1234567890abcdef0123456789abcdef01234567',
                        'REGRESSIONTESTS_REFSPEC': 'refs/heads/release-2016',
                        'REGRESSIONTESTS_HASH': '1234567890abcdef0123456789abcdef01234567'
                    }
            })

    def test_CrossVerifyRequest(self):
        helper = TestHelper(self, workspace='ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': '3',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234')
            })
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'options': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
                        }
                    ],
                'env': {
                        'REGRESSIONTESTS_REFSPEC': 'refs/changes/34/1234/5',
                        'REGRESSIONTESTS_HASH': '1234567890abcdef0123456789abcdef01234567'
                    },
                'gerrit_info': {
                        'change': 1234,
                        'patchset': 5
                    }
            })
        helper.assertCommandInvoked(['ssh', '-p', '29418', 'jenkins@gerrit.gromacs.org', 'gerrit', 'review', '1234,5', '-m', '"Cross-verify with http://gerrit (patch set 3) running at http://build"'])

    def test_CrossVerifyRequestQuiet(self):
        helper = TestHelper(self, workspace='ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': '3',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet')
            })
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'options': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
                        }
                    ],
                'env': {
                        'REGRESSIONTESTS_REFSPEC': 'refs/changes/34/1234/5',
                        'REGRESSIONTESTS_HASH': '1234567890abcdef0123456789abcdef01234567'
                    }
            })

    def test_CrossVerifyRequestOneBuildOnly(self):
        helper = TestHelper(self, workspace='ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': '3',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet clang-analyzer')
            })
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'clang-analyzer'
                        }
                    ],
                'env': {
                        'REGRESSIONTESTS_REFSPEC': 'refs/changes/34/1234/5',
                        'REGRESSIONTESTS_HASH': '1234567890abcdef0123456789abcdef01234567'
                    }
            })

    def test_CrossVerifyRequestReleng(self):
        helper = TestHelper(self, workspace='ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'releng',
                'GERRIT_REFSPEC': 'refs/changes/12/3456/3',
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': '3',
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet')
            })
        input_lines = [
                'gcc-4.6 gpu cuda-5.0',
                'msvc-2013'
            ]
        helper.add_input_file('ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(input_lines) + '\n')
        factory = helper.factory
        executor = helper.executor
        get_actions_from_triggering_comment(factory, 'actions.json')
        helper.assertOutputJsonFile('ws/build/actions.json', {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'options': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in input_lines])
                        },
                        { 'type': 'clang-analyzer', 'desc': 'cross-verify' },
                        { 'type': 'cppcheck', 'desc': 'cross-verify' },
                        { 'type': 'documentation', 'desc': 'cross-verify' },
                        { 'type': 'uncrustify', 'desc': 'cross-verify' }
                    ],
                'env': {
                        'GROMACS_REFSPEC': 'refs/heads/master',
                        'GROMACS_HASH': '1234567890abcdef0123456789abcdef01234567',
                        'REGRESSIONTESTS_REFSPEC': 'refs/changes/34/1234/5',
                        'REGRESSIONTESTS_HASH': '1234567890abcdef0123456789abcdef01234567'
                    }
            })


class TestDoPostBuild(unittest.TestCase):
    def test_NoBuild(self):
        helper = TestHelper(self, workspace='ws')
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': []
            })
        do_post_build(factory, 'actions.json', 'message.json')
        helper.assertOutputJsonFile('ws/build/message.json', {
                'url': None,
                'message': ''
            })

    def test_SingleBuild(self):
        helper = TestHelper(self, workspace='ws')
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': None,
                            'result': 'SUCCESS'
                        }
                    ]
            })
        do_post_build(factory, 'actions.json', 'message.json')
        helper.assertOutputJsonFile('ws/build/message.json', {
                'url': 'http://my_build',
                'message': ''
            })

    def test_SingleBuildWithCrossVerify(self):
        helper = TestHelper(self, workspace='ws', env={
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': '3',
            })
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': None,
                            'result': 'SUCCESS'
                        }
                    ],
                'gerrit_info': {
                        'change': 1234,
                        'patchset': 5
                    }
            })
        do_post_build(factory, 'actions.json', 'message.json')
        helper.assertOutputJsonFile('ws/build/message.json', {
                'url': 'http://my_build',
                'message': ''
            })
        helper.assertCommandInvoked(['ssh', '-p', '29418', 'jenkins@gerrit.gromacs.org', 'gerrit', 'review', '1234,5', '-m', '"Cross-verify with http://gerrit (patch set 3) finished\n\nhttp://my_build: SUCCESS"'])

    def test_SingleBuildWithDescription(self):
        helper = TestHelper(self, workspace='ws')
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': 'cross-verify',
                            'result': 'SUCCESS'
                        }
                    ]
            })
        do_post_build(factory, 'actions.json', 'message.json')
        helper.assertOutputJsonFile('ws/build/message.json', {
                'url': 'http://my_build (cross-verify)',
                'message': ''
            })

    def test_TwoBuilds(self):
        helper = TestHelper(self, workspace='ws')
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': 'cross-verify',
                            'result': 'SUCCESS'
                        },
                        {
                            'url': 'http://my_build2',
                            'desc': None,
                            'result': 'SUCCESS'
                        }
                    ]
            })
        do_post_build(factory, 'actions.json', 'message.json')
        helper.assertOutputJsonFile('ws/build/message.json', {
                'url': None,
                'message': 'http://my_build (cross-verify): SUCCESS\nhttp://my_build2: SUCCESS'
            })


if __name__ == '__main__':
    unittest.main()
