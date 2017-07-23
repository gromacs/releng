"""
Interfacing with other systems (Gerrit, Jenkins)

This module should contain all code related to interacting with Gerrit
and as much as possible of the code related to interacting with the Jenkins job
configuration and passing information back to workflow Groovy scripts.
"""
from __future__ import print_function

import ast
import base64
import json
import os
import re
import traceback
import urllib

from common import AbortError, BuildError, ConfigurationError
from common import Project, System
import utils

class RefSpec(object):

    """Wraps handling of refspecs used to check out projects."""

    @staticmethod
    def is_tarball_refspec(value):
        if value is None:
            return False
        return value.startswith('tarballs/')

    def __init__(self, value, remote_hash=None, executor=None):
        self._value = value
        self._remote = value
        if remote_hash:
            self._remote = remote_hash
        self.branch = None
        self.change_number = None
        self._tar_props = None
        if self.is_tarball_refspec(value):
            assert executor is not None
            prop_path = os.path.join(self._value, 'package-info.log')
            self._tar_props = utils.read_property_file(executor, prop_path)
            self._remote = self._tar_props['HEAD_HASH']
        elif value.startswith('refs/changes/'):
            self.change_number = value.split('/')[3]
        elif value.startswith('refs/heads/'):
            self.branch = value.split('/')[2]

    @property
    def is_no_op(self):
        """Whether this refspec is a magic no-op refspec used for testing."""
        return self._value == 'HEAD'

    @property
    def is_static(self):
        """Whether this refspec specifies a static commit at the remote side."""
        return self._value.startswith('refs/changes/')

    @property
    def fetch(self):
        """Git refspec used to fetch the corresponding commit."""
        return self._value

    @property
    def checkout(self):
        """Git refspec used for checkout after git fetch."""
        if self._remote == self._value:
            return 'FETCH_HEAD'
        return self._remote

    @property
    def is_tarball(self):
        return self._tar_props is not None

    @property
    def tarball_props(self):
        assert self.is_tarball
        return self._tar_props

    @property
    def tarball_path(self):
        assert self.is_tarball
        return os.path.join(self._value, self._tar_props['PACKAGE_FILE_NAME'])

    def __str__(self):
        """Value of this refspec in human-friendly format."""
        return self._value


class GerritChange(object):

    def __init__(self, json_data):
        self.project = Project.parse(json_data['project'])
        self.branch = json_data['branch']
        self.number = int(json_data['number'])
        self.title = json_data['subject']
        self.url = json_data['url']
        self.is_open = json_data['open']
        patchset = json_data['currentPatchSet']
        self.patchnumber = int(patchset['number'])
        self.refspec = RefSpec(patchset['ref'], patchset['revision'])


class GerritIntegration(object):

    """Provides access to Gerrit and Gerrit Trigger configuration.

    Methods encapsulate calls to Gerrit SSH commands (and possibly in the
    future, REST calls) and access to environment variables/build parameters
    set by Gerrit Trigger.
    """

    def __init__(self, factory, user=None):
        if user is None:
            user = 'jenkins'
        self._env = factory.env
        self._cmd_runner = factory.cmd_runner
        self._user = user
        self._is_windows = (factory.system == System.WINDOWS)

    def get_remote_hash(self, project, refspec):
        """Fetch hash of a refspec on the Gerrit server."""
        cmd = ['git', 'ls-remote', self.get_git_url(project), refspec.fetch]
        output = self._cmd_runner.check_output(cmd).split(None, 1)
        if len(output) < 2:
            return BuildError('failed to find refspec {0} for {1}'.format(refspec, project))
        return output[0].strip()

    def get_git_url(self, project):
        """Returns the URL for git to access the given project."""
        return 'ssh://{0}/{1}.git'.format(self._get_ssh_url(), project)

    def get_triggering_project(self):
        gerrit_project = self._env.get('GERRIT_PROJECT', None)
        if gerrit_project is None:
            return None
        return Project.parse(gerrit_project)

    def get_triggering_refspec(self):
        refspec = self._env.get('GERRIT_REFSPEC', None)
        if refspec is None:
            raise ConfigurationError('GERRIT_REFSPEC not set')
        return RefSpec(refspec)

    def get_triggering_branch(self):
        return self._env.get('GERRIT_BRANCH', None)

    def get_triggering_comment(self):
        text = self._env.get('GERRIT_EVENT_COMMENT_TEXT', None)
        if text:
            text = base64.b64decode(text)
            match = re.search(r'(?:^|\n\n)\[JENKINS\]\s*((?:.+\n)*(?:.+))(?:\n\n|\n?$)', text)
            if not match:
                return None
            return match.group(1).strip()
        text = self._env.get('MANUAL_COMMENT_TEXT', None)
        return text

    def query_change(self, query, expect_unique=True):
        if self._is_windows:
            return None
        cmd = self._get_ssh_query_cmd()
        cmd.extend(['--current-patch-set', '--', query])
        lines = self._cmd_runner.check_output(cmd).splitlines()
        if len(lines) < 2:
            raise BuildError(query + ' does not match any change')
        if len(lines) > 2 and expect_unique:
            raise BuildError(query + ' does not identify a unique change')
        return GerritChange(json.loads(lines[0]))

    def post_cross_verify_start(self, change, patchset):
        message = 'Cross-verify with {0} (patch set {1}) running at {2}'.format(
                self._env['GERRIT_CHANGE_URL'], self._env['GERRIT_PATCHSET_NUMBER'],
                self._env['BUILD_URL'])
        cmd = self._get_ssh_review_cmd(change, patchset, message)
        self._cmd_runner.check_call(cmd)

    def post_cross_verify_finish(self, change, patchset, build_messages):
        message = 'Cross-verify with {0} (patch set {1}) finished'.format(
                self._env['GERRIT_CHANGE_URL'], self._env['GERRIT_PATCHSET_NUMBER'])
        message += '\n\n' + '\n\n'.join(build_messages)
        cmd = self._get_ssh_review_cmd(change, patchset, message)
        self._cmd_runner.check_call(cmd)

    def _get_ssh_url(self):
        return self._user + '@gerrit.gromacs.org'

    def _get_ssh_gerrit_cmd(self, cmdname):
        return ['ssh', '-p', '29418', self._get_ssh_url(), 'gerrit', cmdname]

    def _get_ssh_query_cmd(self):
        return self._get_ssh_gerrit_cmd('query') + ['--format=JSON']

    def _get_ssh_review_cmd(self, change, patchset, message):
        changeref = '{0},{1}'.format(change, patchset)
        return self._get_ssh_gerrit_cmd('review') + [changeref, '-m', '"' + message + '"']


class ProjectInfo(object):
    """Information about a checked-out project.

    Attributes:
        project (str): Name of the git project (e.g. gromacs, regressiontests, releng)
        refspec (RefSpec): Refspec from which the project has been checked out.
        head_hash (str): SHA1 of HEAD.
        head_title (str): Title of the HEAD commit.
        remote_hash (str): SHA1 of the refspec at the remote repository.
    """

    def __init__(self, project, branch, refspec, head_hash, head_title, remote_hash):
        self.project = project
        self.branch = branch
        self.refspec = refspec
        self.head_hash = head_hash
        self.head_title = head_title
        self.remote_hash = remote_hash

    @property
    def is_tarball(self):
        return self.refspec.is_tarball

    def has_correct_hash(self):
        return self.head_hash == self.remote_hash

    def to_dict(self):
        return {
                'project': self.project,
                'branch': self.branch,
                'refspec': str(self.refspec),
                'hash': self.head_hash,
                'title': self.head_title,
                'refspec_env': '{0}_REFSPEC'.format(self.project.upper()),
                'hash_env': '{0}_HASH'.format(self.project.upper())
            }


class ProjectsManager(object):
    """Manages project refspecs and checkouts.

    This class is mainly responsible of managing the state related to project
    checkouts, including those checked out external to the Python code (in
    pipeline code, or in Jenkins job configuration).
    """

    def __init__(self, factory):
        self._cmd_runner = factory.cmd_runner
        self._env = factory.env
        self._executor = factory.executor
        self._gerrit = factory.gerrit
        self._workspace = factory.workspace
        self._refspecs, initial_projects = self._get_refspecs_and_initial_projects()
        self._projects = dict()
        for project in initial_projects:
            info = self._create_project_info(project)
            self._projects[project] = info

    def _get_refspecs_and_initial_projects(self):
        """Determines the refspecs to be used, and initially checked out projects.

        If the build is triggered by Gerrit Trigger, then GERRIT_PROJECT
        environment variable exists, and the Jenkins build configuration needs
        to check out this project to properly integrate with different plugins.

        For other cases, CHECKOUT_PROJECT can also be used.

        Returns:
          Tuple[Dict[Project,RefSpec],Set[Project]]: The refspecs and initial
            projects.
        """
        refspecs = dict()
        # The releng project is always checked out, since we are already
        # executing code from there...
        initial_projects = { Project.RELENG }
        for project in Project._values:
            refspec = self._parse_refspec(project)
            if refspec:
                refspecs[project] = refspec
        checkout_project = self._parse_checkout_project()
        gerrit_project = self._gerrit.get_triggering_project()
        if gerrit_project is not None and not refspecs[gerrit_project].is_tarball:
            refspec = self._gerrit.get_triggering_refspec()
            refspecs[gerrit_project] = refspec
        if checkout_project is not None:
            refspec = self._env.get('CHECKOUT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('CHECKOUT_REFSPEC not set')
            sha1 = self._env.get('{0}_HASH'.format(checkout_project.upper()), None)
            refspecs[checkout_project] = RefSpec(refspec, sha1)
            initial_projects.add(checkout_project)
        elif gerrit_project is not None:
            initial_projects.add(gerrit_project)
        else:
            raise ConfigurationError('Neither CHECKOUT_PROJECT nor GERRIT_PROJECT is set')
        return refspecs, initial_projects

    def _parse_refspec(self, project):
        env_name = '{0}_REFSPEC'.format(project.upper())
        refspec = self._env.get(env_name, None)
        if refspec:
            env_name = '{0}_HASH'.format(project.upper())
            sha1 = self._env.get(env_name, None)
            return RefSpec(refspec, sha1, executor=self._executor)
        return None

    def _parse_checkout_project(self):
        checkout_project = self._env.get('CHECKOUT_PROJECT', None)
        if checkout_project is None:
            return None
        return Project.parse(checkout_project)

    def _create_project_info(self, project, is_checked_out=True):
        refspec = self._get_refspec(project)
        if refspec.is_tarball:
            # TODO: Populate more useful information for print_project_info()
            return ProjectInfo(project, None, refspec, refspec.checkout, 'From tarball', refspec.checkout)
        if is_checked_out:
            title, sha1 = self._workspace._get_git_commit_info(project, 'HEAD')
            if refspec.is_static:
                remote_sha1 = self._gerrit.get_remote_hash(project, refspec)
            else:
                remote_sha1 = sha1
        else:
            sha1 = self._gerrit.get_remote_hash(project, refspec)
            remote_sha1 = sha1
            title, dummy = self._workspace._get_git_commit_info(project, sha1, allow_none=True)
        branch = refspec.branch
        change = None
        if refspec.change_number:
            change = self._gerrit.query_change(refspec.change_number)
        elif title is None or branch is None:
            change = self._gerrit.query_change('commit:' + sha1, expect_unique=False)
        if change:
            if title is None:
                title = change.title
            if branch is None:
                branch = change.branch
        return ProjectInfo(project, branch, refspec, sha1, title, remote_sha1)

    def _get_refspec(self, project, allow_none=False):
        """Returns the refspec that is being built for the given project."""
        refspec = self._refspecs.get(project, None)
        if refspec is None and not allow_none:
            raise ConfigurationError(project.upper() + '_REFSPEC is not set')
        return refspec

    def init_workspace(self):
        self._workspace._set_initial_checkouts(self._projects.keys())

    def checkout_project(self, project):
        """Checks out the given project if not yet done for this build."""
        if project in self._projects:
            return
        refspec = self._get_refspec(project)
        self._workspace._checkout_project(project, refspec)
        info = self._create_project_info(project)
        self._projects[project] = info

    def get_project_info(self, project):
        if project not in self._projects:
            raise ConfigurationError('accessing project {0} before checkout'.format(project))
        return self._projects[project]

    def print_project_info(self):
        """Prints information about the revisions used in this build."""
        console = self._executor.console
        projects = [self._projects[p] for p in sorted(self._projects.iterkeys())]
        print('-----------------------------------------------------------', file=console)
        print('Building using versions:', file=console)
        for project_info in projects:
            correct_info = ''
            if not project_info.has_correct_hash():
                correct_info = ' (WRONG)'
            print('{0:16} {1:26} {2}{3}'.format(
                project_info.project + ':', project_info.refspec, project_info.head_hash, correct_info),
                file=console)
            if project_info.head_title:
                print('{0:19}{1}'.format('', project_info.head_title), file=console)
        print('-----------------------------------------------------------', file=console)

    def check_projects(self):
        """Checks that all checked-out projects are at correct revisions.

        In the past, there have been problems with not all projects getting
        correctly checked out.  It is unknown whether this was a Jenkins bug
        or something else, and whether the issue still exists.
        """
        all_correct = True
        for project in sorted(self._projects.iterkeys()):
            project_info = self._projects[project]
            if not project_info.has_correct_hash():
                print('Checkout of {0} failed: HEAD is {1}, expected {2}'.format(
                    project, project_info.head_hash, project_info.remote_hash))
                all_correct = False
        if not all_correct:
            raise BuildError('Checkout failed (Jenkins issue)')

    def get_build_revisions(self):
        projects = []
        for project in Project._values:
            if project in self._projects:
                info = self._projects[project]
            else:
                refspec = self._get_refspec(project, allow_none=True)
                if refspec is None:
                    continue
                info = self._create_project_info(project, is_checked_out=False)
            projects.append(info)
        return [project.to_dict() for project in projects]

    def override_refspec(self, project, refspec):
        self._refspecs[project] = refspec


class BuildParameters(object):
    """Access to build parameters."""

    def __init__(self, factory):
        self._env = factory.env

    def get(self, name, handler):
        """Gets the value of a build parameter/environment variable.

        If the parameter/environment variable is not set, None is returned.

        Args:
            name (str): Name of the parameter/environment variable to read.
            handler (function): Handler function that parses/converts the value.
        """
        value = self._env.get(name, None)
        if value is not None:
            value = handler(value)
        return value


class ParameterTypes(object):
    """Methods to pass to BuildParameters.get() for parsing build parameters."""

    @staticmethod
    def bool(value):
        """Parses a Jenkins boolean build parameter."""
        return value.lower() == 'true'

    @staticmethod
    def string(value):
        return value


class JenkinsIntegration(object):
    """Access to Jenkins specifics such as build parameters."""

    def __init__(self, factory):
        self.workspace_root = factory.env['WORKSPACE']
        self.node_name = factory.env.get('NODE_NAME', None)
        if not self.node_name:
            self.node_name = 'unknown'
        self.params = BuildParameters(factory)

    def query_matrix_build(self, url):
        """Queries basic information about a matrix build from Jenkins REST API.

        Args:
            url (str): Base absolute URL of the Jenkins build to query.
        """
        result = self._query_build(url, 'number,runs[number,url]')
        # For some reason, Jenkins returns runs also for previous builds in case
        # those are no longer part of the current matrix.  Those that actually
        # belong to the queried run can be identified by matching build numbers.
        filtered_runs = [x for x in result['runs'] if x['number'] == result['number']]
        result['runs'] = filtered_runs
        return result

    def _query_build(self, url, tree):
        query_url = '{0}/api/python?tree={1}'.format(url, tree)
        return ast.literal_eval(urllib.urlopen(query_url).read())


class StatusReporter(object):
    """Handles tracking and reporting of failures during the build.

    Attributes:
        failed (bool): Whether the build has already failed.
    """

    def __init__(self, factory, tracebacks=True):
        self._status_file = factory.env.get('STATUS_FILE', 'logs/unsuccessful-reason.log')
        self._propagate_failure = not bool(factory.env.get('NO_PROPAGATE_FAILURE', False))
        self._executor = factory.executor
        self._executor.remove_path(self._status_file)
        self._workspace = factory.workspace
        if not os.path.isabs(self._status_file):
            self._status_file = os.path.join(self._workspace.root, self._status_file)
        self.failed = False
        self._aborted = False
        self._unsuccessful_reason = []
        self.return_value = None
        self._tracebacks = tracebacks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        returncode = 1
        if exc_type is not None:
            console = self._executor.console
            if not self._tracebacks:
                tb = None
            if issubclass(exc_type, AbortError):
                self._aborted = True
                returncode = exc_value.returncode
            elif issubclass(exc_type, ConfigurationError):
                traceback.print_exception(exc_type, exc_value, tb, file=console)
                self.mark_failed('Jenkins configuration error: ' + str(exc_value))
            elif issubclass(exc_type, BuildError):
                traceback.print_exception(exc_type, exc_value, tb, file=console)
                self.mark_failed(str(exc_value))
            else:
                lines = traceback.format_exception(exc_type, exc_value, tb)
                lines = [x.rstrip() for x in lines]
                self._unsuccessful_reason.extend(lines)
                self._report_on_exception()
                return False
        self._report()
        # Currently, we do not propagate even the aborted return value when
        # not requested to.  This means that the parent workflow build may
        # have a chance to write a summary to the build summary page before
        # exiting.  Not sure what Jenkins does if the workflow build takes
        # a long time afterwards to finish, though...
        if (self._aborted or self.failed) and self._propagate_failure:
            self._executor.exit(returncode)
        return True

    def mark_failed(self, reason):
        """Marks the build failed.

        Args:
            reason (str): Reason printed to the build log for the failure.
        """
        self.failed = True
        self._unsuccessful_reason.append(reason)

    def mark_unstable(self, reason, details=None):
        """Marks the build unstable.

        Args:
            reason (str): Reason printed to the build console log for the failure.
            details (Optional[List[str]]): Reason(s) reported back to Gerrit.
                If not provided, reason is used.
        """
        print('FAILED: ' + reason, file=self._executor.console)
        if details is None:
            self._unsuccessful_reason.append(reason)
        else:
            self._unsuccessful_reason.extend(details)

    def _report_on_exception(self):
        console = self._executor.console
        try:
            self._report(to_console=False)
        except:
            traceback.print_exc(file=console)

    def _report(self, to_console=True):
        """Reports possible failures at the end of the build."""
        result = 'SUCCESS'
        reason = None
        if self._aborted:
            result = 'ABORTED'
        elif self.failed:
            result = 'FAILURE'
        elif self._unsuccessful_reason:
            result = 'UNSTABLE'
        if not self._aborted and self._unsuccessful_reason:
            reason = '\n'.join(self._unsuccessful_reason)
        if reason and to_console:
            console = self._executor.console
            print('Build FAILED:', file=console)
            for line in self._unsuccessful_reason:
                print('  ' + line, file=console)
        contents = None
        ext = os.path.splitext(self._status_file)[1]
        if ext == '.json':
            output = {
                    'result': result,
                    'reason': reason
                }
            if self.return_value:
                output['return_value'] = self.return_value
            contents = json.dumps(output, indent=2)
        elif reason:
            contents = reason + '\n'
        if contents:
            self._executor.ensure_dir_exists(os.path.dirname(self._status_file))
            self._executor.write_file(self._status_file, contents)
        if self.failed:
            assert self._unsuccessful_reason, "Failed build did not produce an unsuccessful reason"
