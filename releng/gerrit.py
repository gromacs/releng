"""
Gerrit interfacing

This module should contain all code related to interacting with Gerrit.
It also currently contains code to interact with the Jenkins configuration
related to what to check out.
"""

import os
import subprocess

from common import ConfigurationError
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

    def __init__(self, value, executor=None):
        self._value = value
        self._remote = value
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
    def remote(self):
        """Git refspec used to fetch/check out the corresponding commit."""
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
            return checkout_project, RefSpec(refspec)
        if gerrit_project is not None:
            gerrit_project = Project.parse(gerrit_project)
            refspec = self._env.get('GERRIT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('GERRIT_REFSPEC not set')
            return gerrit_project, RefSpec(refspec)
        raise ConfigurationError('Neither CHECKOUT_PROJECT nor GERRIT_PROJECT is set')

    def get_refspec(self, project):
        """Returns the refspec that is being built for the given project."""
        if self.checked_out_project == project:
            return self._checked_out_refspec
        if self.checked_out_project == Project.RELENG:
            if _OVERRIDES.get(project, None) is not None:
                return _OVERRIDES[project]
        env_name = '{0}_REFSPEC'.format(project.upper())
        refspec = self._env.get(env_name, None)
        if refspec is None:
            raise ConfigurationError(env_name + ' is not set')
        return RefSpec(refspec, self._executor)

    def get_remote_hash(self, project, refspec):
        """Fetch hash of a refspec on the Gerrit server."""
        cmd = ['git', 'ls-remote', self.get_git_url(project), refspec.remote]
        try:
            return subprocess.check_output(cmd).split(None, 1)[0].strip()
        except subprocess.CalledProcessError as e:
            raise BuildError('failed to execute: ' + ' '.join(e.cmd))

    def get_git_url(self, project):
        """Returns the URL for git to access the given project."""
        return 'ssh://{0}/{1}.git'.format(self._get_ssh_url(), project)

    def _get_ssh_url(self):
        return self._user + '@gerrit.gromacs.org'
