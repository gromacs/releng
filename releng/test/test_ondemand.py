import base64
import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.ondemand import get_actions_from_triggering_comment
from releng.ondemand import do_post_build

from releng.test.utils import RepositoryTestState, TestHelper

class TestGetActionsFromTriggeringComment(unittest.TestCase):
    _MATRIX_INPUT_LINES = [
            'gcc-6 gpu cuda-9.0',
            'msvc-2013'
        ]
    _MATRIX_EXPECTED_RESULT = {
            'configs': [
                {
                    'host': 'bs_nix1310',
                    'labels': 'cuda-9.0 && gcc-6',
                    'opts': ['gcc-6', 'gpu', 'cuda-9.0']
                },
                {
                    'host': 'bs-win2012r2',
                    'labels': 'msvc-2013',
                    'opts': ['msvc-2013']
                }
            ],
            'as_axis': '"{0} host=bs_nix1310" "{1} host=bs-win2012r2"'.format(*[x.strip() for x in _MATRIX_INPUT_LINES])
        }

    def test_CoverageRequest(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Coverage')
            })
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'coverage'
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_PackageRequestForSource(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Package')
            })
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'source-package'
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_PackageRequestForReleng(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'GERRIT_PROJECT': 'releng',
                'GERRIT_REFSPEC': commits.releng.refspec,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Package')
            })
        helper.add_input_file('/ws/gromacs/admin/builds/get-version-info.py',
                'def do_build(context):\n    context.set_version_info("2017", "1234567890abcdef")\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'source-package'
                        },
                        {
                            'type': 'regtest-package',
                            'version': '2017',
                            'md5sum': '1234567890abcdef'
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_PostSubmitRequest(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Post-submit')
            })
        helper.add_input_file('/ws/gromacs/admin/builds/post-submit-matrix.txt',
                '\n'.join(self._MATRIX_INPUT_LINES) + '\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'post-submit',
                            'matrix': self._MATRIX_EXPECTED_RESULT
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_ReleaseBranchRequest(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, branch='release-2016')
        commits.set_commit(Project.REGRESSIONTESTS, branch='release-2016')
        commits.set_commit(Project.RELENG, change_number=1234)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'GERRIT_PROJECT': 'releng',
                'GERRIT_REFSPEC': commits.releng.refspec,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] release-2016'),
                'GROMACS_REFSPEC': 'refs/heads/master',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('/ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(self._MATRIX_INPUT_LINES) + '\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'release-2016',
                            'matrix': self._MATRIX_EXPECTED_RESULT
                        },
                        { 'type': 'clang-analyzer', 'desc': 'release-2016' },
                        { 'type': 'documentation', 'desc': 'release-2016' },
                        { 'type': 'uncrustify', 'desc': 'release-2016' }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_CrossVerifyRequest(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=3456, patch_number=3)
        commits.set_commit(Project.REGRESSIONTESTS, change_number=1234, patch_number=5)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': commits.gromacs.patch_number,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234'),
                'GROMACS_REFSPEC': 'refs/heads/master',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('/ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(self._MATRIX_INPUT_LINES) + '\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'matrix': self._MATRIX_EXPECTED_RESULT
                        }
                    ],
                'revisions': commits.expected_build_revisions,
                'gerrit_info': {
                        'change': commits.regressiontests.change_number,
                        'patchset': commits.regressiontests.patch_number
                    }
            })
        helper.assertCommandInvoked(['ssh', '-p', '29418', 'jenkins@gerrit.gromacs.org', 'gerrit', 'review', '1234,5', '-m', '"Cross-verify with http://gerrit (patch set 3) running at http://build"'])

    def test_CrossVerifyRequestQuiet(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=3456)
        commits.set_commit(Project.REGRESSIONTESTS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': commits.gromacs.patch_number,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet'),
                'GROMACS_REFSPEC': 'refs/heads/master',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('/ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(self._MATRIX_INPUT_LINES) + '\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'matrix': self._MATRIX_EXPECTED_RESULT
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_CrossVerifyRequestOneBuildOnly(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=3456)
        commits.set_commit(Project.REGRESSIONTESTS, change_number=1234)
        commits.set_commit(Project.RELENG)
        helper = TestHelper(self, commits=commits, env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'gromacs',
                'GERRIT_REFSPEC': commits.gromacs.refspec,
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': commits.gromacs.patch_number,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet coverage'),
                'GROMACS_REFSPEC': 'refs/heads/master',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master'
            })
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'coverage'
                        }
                    ],
                'revisions': commits.expected_build_revisions
            })

    def test_CrossVerifyRequestReleng(self):
        commits = RepositoryTestState()
        commits.set_commit(Project.GROMACS, change_number=1234)
        commits.set_commit(Project.REGRESSIONTESTS)
        commits.set_commit(Project.RELENG, change_number=3456)
        helper = TestHelper(self, commits=commits, workspace='/ws', env={
                'BUILD_URL': 'http://build',
                'GERRIT_PROJECT': 'releng',
                'GERRIT_REFSPEC': commits.releng.refspec,
                'GERRIT_CHANGE_URL': 'http://gerrit',
                'GERRIT_PATCHSET_NUMBER': commits.releng.patch_number,
                'GERRIT_EVENT_COMMENT_TEXT': base64.b64encode('[JENKINS] Cross-verify 1234 quiet'),
                'GROMACS_REFSPEC': 'refs/heads/master',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master'
            })
        helper.add_input_file('/ws/gromacs/admin/builds/pre-submit-matrix.txt',
                '\n'.join(self._MATRIX_INPUT_LINES) + '\n')
        factory = helper.factory
        result = get_actions_from_triggering_comment(factory)
        self.assertEqual(result, {
                'builds': [
                        {
                            'type': 'matrix',
                            'desc': 'cross-verify',
                            'matrix': self._MATRIX_EXPECTED_RESULT
                        },
                        { 'type': 'clang-analyzer', 'desc': 'cross-verify' },
                        { 'type': 'documentation', 'desc': 'cross-verify' },
                        { 'type': 'uncrustify', 'desc': 'cross-verify' }
                    ],
                'revisions': commits.expected_build_revisions
            })


class TestDoPostBuild(unittest.TestCase):
    def test_NoBuild(self):
        helper = TestHelper(self)
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': []
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': None
            })

    def test_SingleBuild(self):
        helper = TestHelper(self)
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
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': 'http://my_build',
                'message': None
            })

    def test_FailedSingleBuild(self):
        helper = TestHelper(self)
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': None,
                            'result': 'FAILURE',
                            'reason': 'Failure reason'
                        }
                    ]
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': 'http://my_build',
                'message': 'Failure reason'
            })

    def test_SingleBuildWithoutUrl(self):
        helper = TestHelper(self)
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'title': 'My title',
                            'url': None,
                            'desc': None,
                            'result': 'SUCCESS'
                        }
                    ]
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': None
            })

    def test_FailedSingleBuildWithoutUrl(self):
        helper = TestHelper(self)
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'title': 'My title',
                            'url': None,
                            'desc': None,
                            'result': 'FAILURE',
                            'reason': 'Failure reason'
                        }
                    ]
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': 'Failure reason'
            })

    def test_SingleBuildWithCrossVerify(self):
        helper = TestHelper(self, env={
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
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': 'http://my_build',
                'message': None
            })
        helper.assertCommandInvoked(['ssh', '-p', '29418', 'jenkins@gerrit.gromacs.org', 'gerrit', 'review', '1234,5', '-m', '"Cross-verify with http://gerrit (patch set 3) finished\n\nhttp://my_build: SUCCESS"'])

    def test_SingleBuildWithDescription(self):
        helper = TestHelper(self)
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
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': 'http://my_build (cross-verify)',
                'message': None
            })

    def test_TwoBuilds(self):
        helper = TestHelper(self)
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
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': 'http://my_build (cross-verify): SUCCESS\nhttp://my_build2: SUCCESS'
            })

    def test_TwoBuildsWithFailure(self):
        helper = TestHelper(self)
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
                            'result': 'FAILURE',
                            'reason': 'Failure reason'
                        }
                    ]
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': 'http://my_build (cross-verify): SUCCESS\nhttp://my_build2: FAILURE <<<\nFailure reason\n>>>'
            })

    def test_TwoBuildsWithoutUrl(self):
        helper = TestHelper(self)
        factory = helper.factory
        helper.add_input_json_file('actions.json', {
                'builds': [
                        {
                            'url': 'http://my_build',
                            'desc': 'cross-verify',
                            'result': 'SUCCESS'
                        },
                        {
                            'title': 'My title',
                            'url': None,
                            'desc': None,
                            'result': 'SUCCESS'
                        }
                    ]
            })
        result = do_post_build(factory, 'actions.json')
        self.assertEqual(result, {
                'url': None,
                'message': 'http://my_build (cross-verify): SUCCESS\nMy title: SUCCESS'
            })



if __name__ == '__main__':
    unittest.main()
