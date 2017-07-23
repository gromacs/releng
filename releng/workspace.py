"""
Build workspace handling

This module should contain most (if not all) raw file manipulation
commands related to setting up and inspecting the workspace.
"""
from __future__ import print_function

import os.path
import tarfile

from common import BuildError, CommandError, ConfigurationError
from common import Project

class CheckedOutProject(object):
    """Information about a checked-out project.

    Attributes:
        root (str): Root directory where the project has been checked out.
        tarball_path (str): Path to the tarball where the project has been
            extracted from (if it exists).
    """

    def __init__(self, root, tarball_path=None):
        self.root = root
        self.tarball_path = tarball_path

    @property
    def is_tarball(self):
        return self.tarball_path is not None

class Workspace(object):
    """Provides access to set up, query, and act within the build workspace,
    particularly involving operations on the git repositories associated
    with the projects.

    Methods are provided for accessing the build directory (whether in- or
    out-of-source), as well as the root directories of all checked-out
    projects.  Also, methods to access a common log directory (for logs that
    need to be post-processed in Jenkins) are provided. Implements
    functionality for updating commits with new files.

    Attributes:
        root (str): Root directory of the workspace.
        install_dir (str): Directory for test installation.
    """
    def __init__(self, factory):
        self.root = factory.jenkins.workspace_root
        self._executor = factory.executor
        self._cmd_runner = factory.cmd_runner
        self._gerrit = factory.gerrit
        self._default_project = factory.default_project
        self._checkouts = dict()
        self._build_dir = None
        self._out_of_source = None
        self._logs_dir = os.path.join(self.root, 'logs')
        self.install_dir = os.path.join(self.root, 'test-install')

    def _set_initial_checkouts(self, projects):
        """Sets projects checked out externally from Git.

        Called from ProjectsManager to initialize the Workspace with knowledge
        of projects that have been checked out outside the Python code.
        """
        for project in projects:
            self._checkouts[project] = CheckedOutProject(os.path.join(self.root, project))

    def _get_checkout_info(self, project):
        """Returns the project info for a project that has been checked
        out from git."""
        if project not in self._checkouts:
            raise ConfigurationError('accessing project {0} before checkout'.format(project))
        return self._checkouts[project]

    def _get_git_commit_info(self, project, commit, allow_none=False):
        """Returns the title and SHA1 for a project that has been checked
        out from git."""
        project_dir = os.path.join(self.root, project)
        cmd = ['git', 'rev-list', '-n1', '--format=oneline', commit, '--']
        try:
            sha1, title = self._cmd_runner.check_output(cmd, cwd=project_dir).strip().split(None, 1)
        except: # TODO: Do not eat unexpected exceptions
            if allow_none:
                return None, None
            raise
        return title, sha1

    def _ensure_empty_dir(self, path):
        """Ensures that the given directory exists and is empty."""
        self._executor.ensure_dir_exists(path, ensure_empty=True)

    def _init_build_dir(self, out_of_source):
        """Initializes the build directory."""
        self._out_of_source = out_of_source
        if out_of_source:
            self._build_dir = os.path.join(self.root, 'build')
            self._ensure_empty_dir(self._build_dir)
        else:
            self._build_dir = self.get_project_dir(self._default_project)

    def _clear_workspace_dirs(self):
        """Clears directories that get generated for each build."""
        self._executor.remove_path(self._logs_dir)
        self._executor.remove_path(self.install_dir)

    def clean_build_dir(self):
        """Ensures that the current build dir is in the initial state (empty)."""
        if self._out_of_source:
            self._ensure_empty_dir(self.build_dir)
        else:
            project_info = self._get_checkout_info(self._default_project)
            if project_info.is_tarball:
                self._executor.remove_path(project_info.root)
                self._extract_tarball(project_info.tarball_path)
            elif not project_info.refspec.is_no_op:
                self._run_git_clean(project_info.root)

    def _resolve_build_input_file(self, path, extension=None):
        """Resolves the name of a build input file.

        Args:
            path (str): Name/path to the input file.
                If only a name is provided, the name is converted
                into an absolute path in :file:`gromacs/admin/builds/`.
            extension (Optional[str]): Extension for the input file.
                If provided and not present in the input path, it is
                automatically appended.
        """
        if extension and not path.endswith(extension):
            path += extension
        if os.path.dirname(path):
            return path
        project_dir = self.get_project_dir(self._default_project)
        path = os.path.join(project_dir, 'admin', 'builds', path)
        return path

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
        return self._get_checkout_info(project).root

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
        self._executor.ensure_dir_exists(path)
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

    def _checkout_project(self, project, refspec):
        """Checks out the given project."""
        if refspec.is_tarball:
            props = refspec.tarball_props
            # TODO: Remove possible other directories from earlier extractions.
            project_dir = os.path.join(self.root, '{0}-{1}'.format(project, props['PACKAGE_VERSION']))
            self._executor.remove_path(project_dir)
            self._extract_tarball(refspec.tarball_path)
            project_info = CheckedOutProject(project_dir, refspec.tarball_path)
        else:
            if not refspec.is_no_op:
                self._do_git_checkout(project, refspec)
            project_dir = os.path.join(self.root, project)
            project_info = CheckedOutProject(project_dir)
        self._checkouts[project] = project_info

    def _extract_tarball(self, tarball_path):
        with tarfile.open(tarball_path) as tar:
            tar.extractall(self.root)

    def _do_git_checkout(self, project, refspec):
        project_dir = os.path.join(self.root, project)
        self._executor.ensure_dir_exists(project_dir)
        runner = self._cmd_runner
        if not os.path.isdir(os.path.join(project_dir, '.git')):
            runner.check_call(['git', 'init'], cwd=project_dir)
        runner.check_call(['git', 'fetch', self._gerrit.get_git_url(project), refspec.fetch], cwd=project_dir)
        runner.check_call(['git', 'checkout', '-qf', refspec.checkout], cwd=project_dir)
        runner.check_call(['git', 'gc'], cwd=project_dir)
        self._run_git_clean(project_dir)

    def _run_git_clean(self, project_dir):
        self._cmd_runner.check_call(['git', 'clean', '-ffdxq'], cwd=project_dir)

    def upload_revision(self, project, file_glob="*"):
        """Upload a new version of the patch that triggered this build, but
        only if files in the glob changed and it came from the
        specified project.

        Args:
            project (Project) : Enum value to choose which project might be updated
            file_glob (str) : glob describing the files to add to the patch
        """

        triggering_project = self._gerrit.get_triggering_project()
        triggering_branch = self._gerrit.get_triggering_branch()
        if triggering_project is None or triggering_branch is None:
            return

        # Add files to the index if they were updated by this job and match the glob.
        cwd = self.get_project_dir(project)
        cmd = ['git', 'add', '--', file_glob]
        try:
            self._cmd_runner.check_call(cmd, cwd=cwd)
        except CommandError as e:
            raise BuildError('Failed to add updated files running ' + e.cmd + ' in cwd ' + cwd)

        # Find out from git exit code whether there are any staged
        # changes, but don't show those changes.
        cmd = ['git', 'diff', '--cached', '--exit-code', '--no-patch']
        no_files_were_added = (0 == self._cmd_runner.call(cmd, cwd=cwd))
        if no_files_were_added:
            return

        # Reference files were added to the index, so amend the commit,
        # keeping the message from the old HEAD commit.
        cmd = ['git', 'commit', '--amend', '--reuse-message', 'HEAD']
        try:
            self._cmd_runner.check_call(cmd, cwd=cwd)
        except CommandError as e:
            raise BuildError('Failed to amend the commit when adding updated files running ' + e.cmd + ' in cwd ' + cwd)

        # If the triggering_project was in fact the project that the
        # caller expects to be updated, push the updated commit back
        # to gerrit for testing and review.
        if triggering_project == project:
            cmd = ['git', 'push', self._gerrit.get_git_url(project), 'HEAD:refs/for/{0}'.format(triggering_branch)]
            try:
                self._cmd_runner.check_call(cmd, cwd=cwd)
            except CommandError as e:
                raise BuildError('Failed to upload the commit with updated files running ' + e.cmd + ' in cwd ' + cwd)
