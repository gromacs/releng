import os.path
import unittest
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import Project
from releng.test.utils import TestHelper

class TestWorkspace(unittest.TestCase):
    def test_GetBuildRevisions(self):
        helper = TestHelper(self, env={
                'WORKSPACE': 'ws',
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'refs/changes/34/1234/5',
                'REGRESSIONTESTS_REFSPEC': 'refs/heads/master',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        workspace = helper.factory.workspace
        workspace._get_build_revisions('build-revisions.json')
        helper.assertOutputJsonFile('build-revisions.json', [
                {
                    'project': 'gromacs',
                    'hash_env': 'GROMACS_HASH',
                    'refspec': 'refs/changes/34/1234/5',
                    'hash': '1234567890abcdef0123456789abcdef01234567',
                    'title': 'Mock title'
                },
                {
                    'project': 'regressiontests',
                    'hash_env': 'REGRESSIONTESTS_HASH',
                    'refspec': 'refs/heads/master',
                    'hash': '1234567890abcdef0123456789abcdef01234567',
                    'title': None
                },
                {
                    'project': 'releng',
                    'hash_env': 'RELENG_HASH',
                    'refspec': 'refs/heads/master',
                    'hash': '1234567890abcdef0123456789abcdef01234567',
                    'title': 'Mock title'
                }
            ])

    def test_GetBuildRevisionsNoRegressionTests(self):
        helper = TestHelper(self, env={
                'WORKSPACE': 'ws',
                'CHECKOUT_PROJECT': 'gromacs',
                'CHECKOUT_REFSPEC': 'refs/changes/34/1234/5',
                'GROMACS_REFSPEC': 'refs/changes/34/1234/5',
                'RELENG_REFSPEC': 'refs/heads/master'
            })
        workspace = helper.factory.workspace
        workspace._get_build_revisions('build-revisions.json')
        helper.assertOutputJsonFile('build-revisions.json', [
                {
                    'project': 'gromacs',
                    'hash_env': 'GROMACS_HASH',
                    'refspec': 'refs/changes/34/1234/5',
                    'hash': '1234567890abcdef0123456789abcdef01234567',
                    'title': 'Mock title'
                },
                {
                    'project': 'releng',
                    'hash_env': 'RELENG_HASH',
                    'refspec': 'refs/heads/master',
                    'hash': '1234567890abcdef0123456789abcdef01234567',
                    'title': 'Mock title'
                }
            ])
