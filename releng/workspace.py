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

class ProjectInfo(object):
    """Information about a checked-out project.

    Attributes:
        project (str): Name of the git project (e.g. gromacs, regressiontests, releng)
        root (str): Root directory where the project has been checked out.
        refspec (RefSpec): Refspec from which the project has been checked out.
        head_hash (str): SHA1 of HEAD.
        head_title (str): Title of the HEAD commit.
        remote_hash (str): SHA1 of the refspec at the remote repository.
    """

    def __init__(self, project, root, refspec, head_hash, head_title, remote_hash):
        self.project = project
        self.root = root
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
                'refspec': str(self.refspec),
                'hash': self.head_hash,
                'title': self.head_title,
                'refspec_env': '{0}_REFSPEC'.format(self.project.upper()),
                'hash_env': '{0}_HASH'.format(self.project.upper())
            }


class Workspace(object):
    """Provides access to set up, query, and act within the build workspace,
    particularly involving operations on the git repositories associated
    with the projects.

    Methods are provided for accessing the build directory (whether in- or
    out-of-source), as well as the root directories of all checked-out
    projects.  Also, methods to access a common log directory (for logs that
    need to be post-processed in Jenkins) are provided. Implements
    functionality for updating commits with new files.

    Internally, this class is also responsible for checking out the projects
    and for tasks related to it.

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
        # The releng project is always checked out, since we are already
        # executing code from there...
        existing_projects = { Project.RELENG, self._gerrit.checked_out_project }
        self._projects = dict()
        for project in existing_projects:
            info = self._get_git_project_info(project)
            self._projects[project] = info
        self._build_dir = None
        self._out_of_source = None
        self._logs_dir = os.path.join(self.root, 'logs')
        self.install_dir = os.path.join(self.root, 'test-install')

    def _get_git_project_info(self, project):
        """Returns the project info for a project that has been checked
        out from git."""
        project_dir = os.path.join(self.root, project)
        cmd = ['git', 'rev-list', '-n1', '--format=oneline', 'HEAD']
        sha1, title = self._cmd_runner.check_output(cmd, cwd=project_dir).strip().split(None, 1)
        refspec = self._gerrit.get_refspec(project)
        if refspec.is_static:
            remote_sha1 = self._gerrit.get_remote_hash(project, refspec)
        else:
            remote_sha1 = sha1
        return ProjectInfo(project, project_dir, refspec, sha1, title, remote_sha1)

    def get_project_info(self, project):
        if project not in self._projects:
            raise ConfigurationError('accessing project {0} before checkout'.format(project))
        return self._projects[project]

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
            project_info = self.get_project_info(self._default_project)
            if project_info.is_tarball:
                self._executor.remove_path(project_info.project_dir)
                self._extract_tarball(project_info.refspec.tarball_path)
            elif not project_info.refspec.is_no_op:
                self._run_git_clean(project_info.project_dir)

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
        return self.get_project_info(project).root

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

    def _get_build_revisions(self):
        projects = []
        for project in Project._values:
            if project in self._projects:
                info = self._projects[project]
            else:
                refspec = self._gerrit.get_refspec(project, allow_none=True)
                if refspec is None:
                    continue
                # TODO: Get the commit title? That would make the build summary
                # page nicer, but can require some magic, or a real checkout...
                sha1 = self._gerrit.get_remote_hash(project, refspec)
                info = ProjectInfo(project, None, refspec, sha1, None, sha1)
            projects.append(info)
        return [project.to_dict() for project in projects]

    def _checkout_project(self, project):
        """Checks out the given project if not yet done for this build."""
        if project in self._projects:
            return
        refspec = self._gerrit.get_refspec(project)
        if refspec.is_tarball:
            props = refspec.tarball_props
            # TODO: Remove possible other directories from earlier extractions.
            project_dir = os.path.join(self.root, '{0}-{1}'.format(project, props['PACKAGE_VERSION']))
            self._executor.remove_path(project_dir)
            self._extract_tarball(refspec.tarball_path)
            # TODO: Populate more useful information for _print_project_info()
            info = ProjectInfo(project, project_dir, refspec, refspec.checkout, 'From tarball', refspec.checkout)
        else:
            if not refspec.is_no_op:
                self._do_git_checkout(project, refspec)
            info = self._get_git_project_info(project)
        self._projects[project] = info

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

    def _print_project_info(self):
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

    def _check_projects(self):
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
