"""
Interfacing with other systems (Gerrit, Jenkins)

This module should contain all code related to interacting with Gerrit
and as much as possible of the code related to interacting with the Jenkins job
configuration.
"""
from __future__ import print_function

import os
import traceback

from common import BuildError, ConfigurationError
from common import Project
import utils

def _ref(change, patchset):
    """Constructs a Gerrit refspec for given patchset in a change.

    Arguments:
        change (int): Number of the change.
        patchset (int): Patchset number.
    """
    value = 'refs/changes/{0}/{1}/{2}'.format(str(change)[-2:], change, patchset)
    return RefSpec(value)

# These variables can be used to trigger the builds from Gerrit against changes
# still in review, instead of the default branch head.
# They only take effect in builds triggered for releng changes.
# _ref() from above can be used.
_OVERRIDES = {
        Project.GROMACS: None,
        Project.REGRESSIONTESTS: None
    }

class RefSpec(object):

    """Wraps handling of refspecs used to check out projects."""

    def __init__(self, value, remote_hash=None, executor=None):
        self._value = value
        self._remote = value
        if remote_hash is not None:
            self._remote = remote_hash
        self._tar_props = None
        if value.startswith('tarballs/'):
            assert executor is not None
            prop_path = os.path.join(self._value, 'package-info.log')
            self._tar_props = utils.read_property_file(executor, prop_path)
            self._remote = self._tar_props['HEAD_HASH']

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


class GerritIntegration(object):

    """Provides access to Gerrit and Jenkins configuration related to checkouts.

    Attributes:
        checked_out_project (Project): Project initially checked out by Jenkins.
    """

    def __init__(self, factory, user=None):
        if user is None:
            user = 'jenkins'
        self._env = factory.env
        self._executor = factory.executor
        self._cmd_runner = factory.cmd_runner
        self._user = user
        self.checked_out_project, self._checked_out_refspec = self._get_checked_out_project()

    def _get_checked_out_project(self):
        """Determines the project initially checked out by Jenkins.

        If the build is triggered by Gerrit Trigger, then GERRIT_PROJECT
        environment variable exists, and the Jenkins build configuration needs
        to check out this project to properly integrate with different plugins.

        For other cases, CHECKOUT_PROJECT can also be used.

        Returns:
          Tuple[Project,RefSpec]: The checked out project and refspec.
        """
        checkout_project = self._env.get('CHECKOUT_PROJECT', None)
        gerrit_project = self._env.get('GERRIT_PROJECT', None)
        if checkout_project is not None:
            checkout_project = Project.parse(checkout_project)
            if gerrit_project is not None and gerrit_project != checkout_project:
                raise ConfigurationError('Inconsistent CHECKOUT_PROJECT and GERRIT_PROJECT')
            refspec = self._env.get('CHECKOUT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('CHECKOUT_REFSPEC not set')
            sha1 = self._env.get('{0}_HASH'.format(checkout_project.upper()), None)
            return checkout_project, RefSpec(refspec, sha1)
        if gerrit_project is not None:
            gerrit_project = Project.parse(gerrit_project)
            refspec = self._env.get('GERRIT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('GERRIT_REFSPEC not set')
            return gerrit_project, RefSpec(refspec)
        raise ConfigurationError('Neither CHECKOUT_PROJECT nor GERRIT_PROJECT is set')

    def get_refspec(self, project, allow_none=False):
        """Returns the refspec that is being built for the given project."""
        if self.checked_out_project == project:
            return self._checked_out_refspec
        if self.checked_out_project == Project.RELENG:
            if _OVERRIDES.get(project, None) is not None:
                return _OVERRIDES[project]
        env_name = '{0}_REFSPEC'.format(project.upper())
        refspec = self._env.get(env_name, None)
        if refspec is None:
            if allow_none:
                return None
            raise ConfigurationError(env_name + ' is not set')
        env_name = '{0}_HASH'.format(project.upper())
        sha1 = self._env.get(env_name, None)
        return RefSpec(refspec, sha1, executor=self._executor)

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

    def _get_ssh_url(self):
        return self._user + '@gerrit.gromacs.org'


class StatusReporter(object):
    """Handles tracking and reporting of failures during the build.

    Attributes:
        failed (bool): Whether the build has already failed.
    """

    def __init__(self, factory, tracebacks=True):
        self._executor = factory.executor
        self._workspace = factory.workspace
        self.failed = False
        self._unsuccessful_reason = []
        self._tracebacks = tracebacks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            console = self._executor.console
            if not self._tracebacks:
                tb = None
            if issubclass(exc_type, ConfigurationError):
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
        if self.failed:
            self._executor.exit(1)
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
        if self._unsuccessful_reason:
            if to_console:
                console = self._executor.console
                print('Build FAILED:', file=console)
                for line in self._unsuccessful_reason:
                    print('  ' + line, file=console)
            path = self._workspace.get_path_for_logfile('unsuccessful-reason.log')
            contents = '\n'.join(self._unsuccessful_reason) + '\n'
            self._executor.write_file(path, contents)
        if self.failed:
            assert self._unsuccessful_reason, "Failed build did not produce an unsuccessful reason"
