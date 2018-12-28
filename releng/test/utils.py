import json
import os.path
from StringIO import StringIO
import textwrap
import urlparse
# With Python 2.7, this needs to be separately installed.
# With Python 3.3 and up, this should change to unittest.mock.
import mock

from releng.common import CommandError, Project
from releng.executor import Executor
from releng.factory import ContextFactory

class CommitInfo(object):
    def __init__(self, project, refspec, sha1, branch, change_number, patch_number):
        self.project = project
        self.sha1 = sha1
        self.title = project.upper() + ' commit'
        self.refspec = refspec
        self.branch = branch
        self.change_number = change_number
        self.patch_number = patch_number

class RepositoryTestState(object):
    @staticmethod
    def create_default():
        state = RepositoryTestState()
        state.set_commit(Project.GROMACS)
        state.set_commit(Project.RELENG)
        return state

    def __init__(self):
        self._commits = dict()

    def set_commit(self, project, sha1=None, branch='master', change_number=None, patch_number=None):
        assert project not in self._commits
        refspec = 'refs/heads/' + branch
        if not sha1:
            if project == Project.GROMACS:
                sha1 = '1234567890abcdef0123456789abcdef01234567'
            elif project == Project.REGRESSIONTESTS:
                sha1 = '234567890abcdef0123456789abcdef012345678'
            elif project == Project.RELENG:
                sha1 = '34567890abcdef0123456789abcdef0123456789'
        if not patch_number:
            patch_number = 4
        if change_number:
            refspec = 'refs/changes/{0:02}/{1}/{2}'.format(change_number%100, change_number, patch_number)
        else:
            if project == Project.GROMACS:
                change_number = 1111
                patch_number = 2
            elif project == Project.REGRESSIONTESTS:
                change_number = 2222
                patch_number = 3
            elif project == Project.RELENG:
                change_number = 3333
                patch_number = 4
        commit = CommitInfo(project, refspec, sha1, branch, change_number, patch_number)
        self._commits[project] = commit
        self.__dict__[project] = commit

    @property
    def projects(self):
        return self._commits.keys()

    def has_project(self, project):
        return project in self._commits

    def get_head(self, project):
        return self._commits[project]

    def find_commit(self, project=None, sha1=None, refspec=None, change_number=None):
        if project:
            return self._commits[project]
        if sha1:
            return filter(lambda x: x.sha1 == sha1, self._commits.itervalues())[0]
        if change_number:
            return filter(lambda x: x.change_number == change_number, self._commits.itervalues())[0]

    @property
    def expected_build_revisions(self):
        revisions = list()
        for project in Project._values:
            if project not in self._commits:
                continue
            info = self._commits[project]
            build_branch_label = info.branch
            if build_branch_label and build_branch_label.startswith('release-'):
                build_branch_label = info.branch[8:]
            revisions.append({
                    'project': project,
                    'refspec_env': project.upper() + '_REFSPEC',
                    'hash_env': project.upper() + '_HASH',
                    'refspec': info.refspec,
                    'branch': info.branch,
                    'build_branch_label': build_branch_label,
                    'hash': info.sha1,
                    'title': info.title
                })
        return revisions

class TestHelper(object):
    def __init__(self, test, commits=None, workspace=None, env=None):
        self._test = test
        self._console = None
        if commits is None:
            commits = RepositoryTestState.create_default()
        self._commits = commits
        self.executor = mock.create_autospec(Executor, spec_set=True, instance=True)
        self.executor.check_output.side_effect = self._check_output
        self.executor.read_file.side_effect = self._read_file
        self.executor.write_file.side_effect = self._write_file
        self.reset_console_output()

        if env is None:
            env = dict()
        if workspace:
            env['WORKSPACE'] = workspace
        else:
            env['WORKSPACE'] = '/ws'
        if 'GROMACS_REFSPEC' not in env:
            env['GROMACS_REFSPEC'] = commits.gromacs.refspec
        if 'RELENG_REFSPEC' not in env:
            env['RELENG_REFSPEC'] = commits.releng.refspec
        if 'REGRESSIONTESTS_REFSPEC' not in env \
                and commits.has_project(Project.REGRESSIONTESTS):
            env['REGRESSIONTESTS_REFSPEC'] = commits.regressiontests.refspec

        self.factory = ContextFactory(env=env)
        self.factory.init_executor(instance=self.executor)
        if workspace:
            self.factory.init_workspace_and_projects()
            self.executor.reset_mock()
            self.reset_console_output()
        self._input_files = dict()
        self._output_files = dict()

    def reset_console_output(self):
        self._console = StringIO()
        type(self.executor).console = mock.PropertyMock(return_value=self._console)

    def _check_output(self, cmd, **kwargs):
        if cmd[:4] == ['git', 'rev-list', '-n1', '--format=oneline']:
            project = Project.parse(os.path.basename(kwargs['cwd']))
            if cmd[4] == 'HEAD':
                commit = self._commits.get_head(project)
            else:
                commit = self._commits.find_commit(project, sha1=cmd[4])
            if not commit:
                raise CommandError('commit not found: ' + cmd[4])
            return '{0} {1}\n'.format(commit.sha1, commit.title)
        elif cmd[:2] == ['git', 'ls-remote']:
            git_url = urlparse.urlsplit(cmd[2])
            project = Project.parse(os.path.splitext(git_url.path[1:])[0])
            commit = self._commits.find_commit(project, refspec=cmd[3])
            return '{0} {1}\n'.format(commit.sha1, commit.refspec)
        elif cmd[0] == 'ssh' and cmd[4:6] == ['gerrit', 'query']:
            query = cmd[9]
            if query.startswith('commit:'):
                commit = self._commits.find_commit(sha1=query[7:])
            else:
                commit = self._commits.find_commit(change_number=int(query))
            data = {
                    'project': commit.project,
                    'branch': commit.branch,
                    'number': str(commit.change_number),
                    'subject': commit.title,
                    'url': 'URL',
                    'open': True,
                    'currentPatchSet': {
                            'number': str(commit.patch_number),
                            'revision': commit.sha1,
                            'ref': commit.refspec
                        }
                }
            return json.dumps(data) + '\nstats'
        return None

    def _read_file(self, path):
        if path not in self._input_files:
            raise IOError(path + ': not part of test')
        return self._input_files[path]

    def _write_file(self, path, contents):
        self._output_files[path] = contents

    def add_input_file(self, path, contents):
        lines = textwrap.dedent(contents).splitlines(True)
        self._input_files[path] = lines

    def add_input_json_file(self, path, contents):
        lines = json.dumps(contents).splitlines(True)
        self._input_files[path] = lines

    def assertConsoleOutput(self, expected):
        text = textwrap.dedent(expected)
        self._test.assertEqual(text, self._console.getvalue())

    def assertOutputFile(self, path, expected):
        if path not in self._output_files:
            self._test.fail('output file not produced: ' + path)
        text = textwrap.dedent(expected)
        self._test.assertEqual(text, self._output_files[path])

    def assertOutputJsonFile(self, path, expected):
        if path not in self._output_files:
            self._test.fail('output file not produced: ' + path)
        contents = json.loads(self._output_files[path])
        self._test.assertEqual(contents, expected)

    def assertCommandInvoked(self, cmd):
        self.executor.check_call.assert_any_call(cmd, cwd=mock.ANY, env=mock.ANY)
