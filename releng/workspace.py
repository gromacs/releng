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
    def __init__(self, factory, root=None):
        if root is None:
            root = os.getenv('WORKSPACE', os.getcwd())
        self.root = root
        self._gerrit = factory.gerrit
        self._is_dry_run = factory.dry_run
        # The releng project is always checked out, since we are already
        # executing code from there...
        self._projects = { Project.RELENG, self._gerrit.checked_out_project }
        self._build_dir = None
        self._logs_dir = os.path.join(self.root, 'logs')

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

    def _checkout_project(self, project):
        """Checks out the given project if not yet done for this build."""
        if project in self._projects:
            return
        self._projects.add(project)
        project_dir = self.get_project_dir(project)
        refspec = self._gerrit.get_refspec(project)
        if refspec == 'HEAD':
            return
        if not os.path.isdir(project_dir):
            os.makedirs(project_dir)
        try:
            if not os.path.isdir(os.path.join(project_dir, '.git')):
                subprocess.check_call(['git', 'init'], cwd=project_dir)
            subprocess.check_call(['git', 'fetch', self._gerrit.get_git_url(project), refspec], cwd=project_dir)
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
        project_info = []
        all_correct = True
        for project in sorted(self._projects):
            project_dir = self.get_project_dir(project)
            cmd = ['git', 'rev-list', '-n1', '--format=oneline', 'HEAD']
            try:
                sha1, title = subprocess.check_output(cmd, cwd=project_dir).strip().split(None, 1)
            except subprocess.CalledProcessError as e:
                raise BuildError('failed to execute: ' + ' '.join(e.cmd))
            refspec = self._gerrit.get_refspec(project)
            correct = True
            if refspec.startswith('refs/changes/'):
                correct_sha1 = self._gerrit.get_remote_hash(project, refspec)
                if sha1 != correct_sha1:
                    print('Checkout of {0} failed: HEAD is {1}, expected {2}'.format(
                        project, sha1, correct_sha1))
                    correct = False
                    all_correct = False
            project_info.append((project, refspec, sha1, title, correct))
        print('-----------------------------------------------------------')
        print('Building using versions:')
        for project, refspec, sha1, title, correct in project_info:
            correct_info = ''
            if not correct:
                correct_info = ' (WRONG)'
            print('{0:16} {1:26} {2}{3}\n{4:19}{5}'.format(
                project + ':', refspec, sha1, correct_info, '', title))
        print('-----------------------------------------------------------')
        if not all_correct:
            raise BuildError('Checkout failed (Jenkins issue)')
