"""
Build workspace handling

This module should contain most (if not all) raw file manipulation
commands related to setting up and inspecting the workspace.
"""
from __future__ import print_function

import os
import shutil
import subprocess

from common import BuildError, ConfigurationError
from common import Project

def _ref(change, patchset):
    """Constructs a Gerrit refspec for given patchset in a change.

    Arguments:
        change (int): Number of the change.
        patchset (int): Patchset number.
    """
    return 'refs/changes/{0}/{1}/{2}'.format(str(change)[-2:], change, patchset)

# TODO: These defaults are currently not used, except for interactive testing
# (in Jenkins, the *_REFSPEC environment variables should always be set to
# specify what changes to test).
# Consider better alternatives.
_DEFAULT = {
        Project.GROMACS: 'refs/heads/master',
        Project.REGRESSIONTESTS: 'refs/heads/master',
        Project.RELENG: 'refs/heads/master'
    }
# These variables can be used to trigger the builds from Gerrit against changes
# still in review, instead of the default branch head.
# They only take effect in builds triggered for releng changes.
# _ref() from above can be used.
_OVERRIDES = {
        Project.GROMACS: None,
        Project.REGRESSIONTESTS: None
    }

class Workspace(object):
    """Provides access to the build workspace.

    Methods are provided for accessing the build directory (whether in- or
    out-of-source), as well as the root directories of all checked-out
    projects.  Also, methods to access a common log directory (for logs that
    need to be post-processed in Jenkins) are provided.

    Internally, this class is also responsible of checking out the projects
    and for tasks related to it.

    Attributes:
        root (str): Root directory of the workspace.
    """
    def __init__(self, root=None, gerrit_user=None, dry_run=False, checkout=True):
        if root is None:
            root = os.getenv('WORKSPACE', os.getcwd())
        self.root = root
        self._is_dry_run = dry_run
        self._checked_out_project, self._checked_out_refspec = self._get_checked_out_project()
        # The releng project is always checked out, since we are already
        # executing code from there...
        self._projects = { Project.RELENG, self._checked_out_project }
        if gerrit_user is None:
            gerrit_user = 'jenkins'
        self._gerrit_user = gerrit_user
        self._checkout = checkout and not dry_run
        self._build_dir = None
        self._logs_dir = os.path.join(self.root, 'logs')

    def _get_checked_out_project(self):
        """Determines the project already checked out by Jenkins.

        If the build is triggered by Gerrit Trigger, then GERRIT_PROJECT
        environment variable exists, and the Jenkins build configuration needs
        to check out this project to properly integrate with different plugins.

        For other cases, CHECKOUT_PROJECT can also be used.

        Returns:
          Tuple[Project,str]: The checked out project and refspec.
        """
        checkout_project = os.getenv('CHECKOUT_PROJECT', None)
        gerrit_project = os.getenv('GERRIT_PROJECT', None)
        if checkout_project is not None:
            checkout_project = Project.parse(checkout_project)
            if gerrit_project is not None and gerrit_project != checkout_project:
                raise ConfigurationError('Inconsistent CHECKOUT_PROJECT and GERRIT_PROJECT')
            refspec = os.getenv('CHECKOUT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('CHECKOUT_REFSPEC not set')
            return checkout_project, refspec
        if gerrit_project is not None:
            gerrit_project = Project.parse(gerrit_project)
            refspec = os.getenv('GERRIT_REFSPEC', None)
            if refspec is None:
                raise ConfigurationError('GERRIT_REFSPEC not set')
            return gerrit_project, refspec
        raise ConfigurationError('Neither CHECKOUT_PROJECT nor GERRIT_PROJECT is set')

    def _ensure_empty_dir(self, path):
        """Ensures that the given directory exists and is empty."""
        if not self._is_dry_run:
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

    def _init_build_dir(self, out_of_source):
        """Initializes the build directory."""
        if out_of_source:
            self._build_dir = os.path.join(self.root, 'build')
            self._ensure_empty_dir(self._build_dir)
        else:
            self._build_dir = self.get_project_dir(Project.GROMACS)

    def _init_logs_dir(self):
        """Initializes the logs directory."""
        self._ensure_empty_dir(self._logs_dir)

    @property
    def build_dir(self):
        """Build directory for building gromacs.

        Returns either the gromacs project directory or a separate build
        directory, depending on whether the build is in- or out-of-source.
        """
        if self._build_dir is None:
            raise ConfigurationError('build directory not initialized before access')
        return self._build_dir

    def get_project_dir(self, project):
        """Returns project directory of a given project.

        Args:
            project (Project): Project whose directory should be returned.

        Returns:
            str: Absolute path to the project directory.
        """
        if project not in self._projects:
            raise ConfigurationError('accessing project {0} before checkout'.format(project))
        return os.path.join(self.root, project)

    def get_log_dir(self, category=None):
        """Returns directory for log files.

        The directory is created if necessary.

        Args:
            category (Optional[str]): Category for the log directory.
                Log files in the same category are put into a common
                subdirectory (with the name of the category), allowing Jenkins
                to glob them for, e.g., parsing warnings.

        Returns:
            str: Absolute path for the requested log directory.
        """
        path = self._logs_dir
        if category is not None:
            path = os.path.join(path, category)
        if not self._is_dry_run and not os.path.isdir(path):
            os.makedirs(path)
        return path

    def get_path_for_logfile(self, name, category=None):
        """Returns path for producing a log file in a common location.

        Directories are created as necessary, but the caller is responsible of
        creating the actual file.

        Args:
            name (str): Name for the log file without directory components, but
                with extension.
            category (Optional[str]): Category for the log file.  Log files in
                the same category are put into a common subdirectory (with the
                name of the category), allowing Jenkins to glob them for, e.g.,
                parsing warnings.

        Returns:
            str: Absolute path for the requested log.
        """
        path = self.get_log_dir(category=category)
        return os.path.join(path, name)

    def _get_git_url(self, project):
        """Returns the URL for git to access the given project."""
        return 'ssh://{0}@gerrit.gromacs.org/{1}.git'.format(self._gerrit_user, project)

    def _get_refspec(self, project):
        """Returns the refspec that is being built for the given project."""
        if self._checked_out_project == project:
            return self._checked_out_refspec
        if self._checked_out_project == Project.RELENG:
            if _OVERRIDES.get(project, None) is not None:
                return _OVERRIDES[project]
        refspec = os.getenv('{0}_REFSPEC'.format(project.upper()), None)
        if refspec is None:
            refspec = _DEFAULT[project]
        return refspec

    def _checkout_project(self, project):
        """Checks out the given project if not yet done for this build."""
        if project in self._projects:
            return
        self._projects.add(project)
        if not self._checkout:
            return
        project_dir = self.get_project_dir(project)
        refspec = self._get_refspec(project)
        if not os.path.isdir(project_dir):
            os.makedirs(project_dir)
        try:
            if not os.path.isdir(os.path.join(project_dir, '.git')):
                subprocess.check_call(['git', 'init'], cwd=project_dir)
            subprocess.check_call(['git', 'fetch', self._get_git_url(project), refspec], cwd=project_dir)
            subprocess.check_call(['git', 'checkout', '-qf', 'FETCH_HEAD'], cwd=project_dir)
            subprocess.check_call(['git', 'clean', '-ffdxq'], cwd=project_dir)
            subprocess.check_call(['git', 'gc'], cwd=project_dir)
        except subprocess.CalledProcessError as e:
            raise BuildError('failed to execute: ' + ' '.join(e.cmd))

    def _check_projects(self):
        """Checks that all checked-out projects are at correct revisions.

        In the past, there have been problems with not all projects getting
        correctly checked out.  It is unknown whether this was a Jenkins bug
        or something else, and whether the issue still exists.
        """
        # TODO: For dynamic refs like refs/heads/master, there is a race
        # condition that can cause spurious failures if the remote ref gets
        # updated between the checkout and this call.  Also, consider how
        # this should interact with --dry-run etc.
        project_info = []
        all_correct = True
        for project in sorted(self._projects):
            project_dir = self.get_project_dir(project)
            refspec = self._get_refspec(project)
            cmd = ['git', 'ls-remote', self._get_git_url(project), refspec]
            try:
                correct_sha1 = subprocess.check_output(cmd, cwd=project_dir).split(None, 1)[0].strip()
                current_sha1 = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project_dir).strip()
            except subprocess.CalledProcessError as e:
                raise BuildError('failed to execute: ' + e.cmd)
            if current_sha1 != correct_sha1:
                print('Checkout of {0} failed: HEAD is {1}, expected {2}'.format(
                    project, current_sha1, correct_sha1))
                all_correct = False
            project_info.append((project, refspec, current_sha1, current_sha1 == correct_sha1))
        print('-----------------------------------------------------------')
        print('Building using versions:')
        for project, refspec, sha1, correct in project_info:
            correct_info = ''
            if not correct:
                correct_info = ' (WRONG)'
            print('{0:20} {1:30} {2}{3}'.format(
                project + ':', refspec, sha1, correct_info))
        print('-----------------------------------------------------------')
        if not all_correct and self._checkout:
            raise BuildError('Checkout failed (Jenkins issue)')
