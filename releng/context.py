"""
Top-level interface for build scripts to the releng package.
"""

from __future__ import print_function

import os
import glob
import hashlib
import pipes
import platform
import re
import shutil
import subprocess
import sys

from common import BuildError, ConfigurationError
from common import JobType, Project, System
from executor import CurrentDirectoryTracker, Executor
from gerrit import GerritIntegration
from options import process_build_options
from script import BuildScript
from workspace import Workspace
import utils

class FailureTracker(object):
    """Handles tracking and reporting of failures during the build.

    Attributes:
        failed (bool): Whether the build has already failed.
    """

    def __init__(self, factory):
        self._executor = factory.executor
        self.failed = False
        self._unsuccessful_reason = []

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

    def report(self, workspace):
        """Reports possible failures at the end of the build.

        Args:
            workspace (Workspace): Workspace to put the failure log into.
        """
        if self._unsuccessful_reason:
            console = self._executor.console
            print('Build FAILED:', file=console)
            for line in self._unsuccessful_reason:
                print('  ' + line, file=console)
            # Only severe configuration errors can cause workspace to be None,
            # so skip the log for simplicity.
            if workspace is not None:
                path = workspace.get_path_for_logfile('unsuccessful-reason.log')
                contents = '\n'.join(self._unsuccessful_reason) + '\n'
                self._executor.write_file(path, contents)
        if self.failed:
            assert self._unsuccessful_reason, "Failed build did not produce an unsuccessful reason"

class ContextFactory(object):

    """Encapsulates construction of objects related to the build.

    This class provides a single place that is responsible of creating
    instances of different objects needed for creating a BuildContext.
    This makes it simpler to pass custom parameters to the various objects,
    while still providing default logic for constructing them in case the
    custom parameters are not needed.  This class reduces the need to pass
    objects or values needed to construct them through various layers.

    Typically, a Jenkins build will use all the objects with their default
    parameters, but testing (using the routines from __main__.py, or otherwise)
    generally needs to have more control.
    """

    def __init__(self, default_project=Project.GROMACS, system=None, env=None, dry_run=False):
        if system is None:
            system = platform.system()
        if system is not None:
            system = System.parse(system)
        if env is None:
            env = dict(os.environ)
        self.system = system
        self.default_project = default_project
        self.dry_run = dry_run
        self._env = env
        self._cwd = CurrentDirectoryTracker()
        self._executor = None
        self._failure_tracker = None
        self._gerrit = None
        self._workspace = None

    @property
    def env(self):
        """Returns the environment variables for the build.

        The caller should not modify the returned dictionary.
        """
        return self._env

    @property
    def cwd(self):
        """Returns a CurrentDirectoryTracker instance for the build."""
        return self._cwd

    @property
    def executor(self):
        """Returns an Executor instance for the build."""
        if self._executor is None:
            self.init_executor()
        return self._executor

    @property
    def failure_tracker(self):
        """Returns the FailureTracker instance for the build."""
        if self._failure_tracker is None:
            self._init_failure_tracker()
        return self._failure_tracker

    @property
    def gerrit(self):
        """Returns the GerritIntegration instance for the build."""
        if self._gerrit is None:
            self.init_gerrit_integration()
        return self._gerrit

    @property
    def workspace(self):
        """Returns the Workspace instance for the build."""
        if self._workspace is None:
            self.init_workspace()
        return self._workspace

    def init_executor(self, cls=None, instance=None):
        """Sets an executor instance/class to be used.

        If not called, a default instance of Executor is created.
        """
        assert self._executor is None
        if instance is None:
            if cls is None:
                instance = Executor(self)
            else:
                instance = cls(self)
        self._executor = instance

    def _init_failure_tracker(self):
        assert self._failure_tracker is None
        self._failure_tracker = FailureTracker(self)

    def init_gerrit_integration(self, **kwargs):
        """Initializes GerritIntegration with given parameters.

        If not called, the object will be created with default parameters.
        """
        assert self._gerrit is None
        self._gerrit = GerritIntegration(factory=self, **kwargs)

    def init_workspace(self, **kwargs):
        """Initializes Workspace with given parameters.

        If not called, the object will be created with default parameters.
        """
        assert self._workspace is None
        self._workspace = Workspace(factory=self, **kwargs)

    def create_context(self, *args):
        """Creates a BuildContext with given arguments."""
        return BuildContext(self, *args)

class BuildContext(object):
    """Top-level interface for build scripts to the releng package.

    Attributes:
        job_type (JobType): Type/scope of the build job (e.g., per-patchset,
            nightly).
        is_dry_run (bool): Whether actual execution of commands should be
            skipped.
            Mainly for internal use, but if the build script executes some
            commands with large side effects directly, it may want to respect
            this.
        env (BuildEnvironment): Access to build environment details like
            paths to executables.  Many of the environment properties, such as
            selecting the compiler, are handled by the build context
            transparently, without the build script needing to access this.
        opts (BuildOptions): Access to all build options.
        workspace (Workspace): Access to the build workspace.
            Can be used to get paths to various parts in the workspace for
            changing directories and for producing log files.
    """

    def __init__(self, factory, job_type, opts, extra_options):
        if job_type is not None:
            JobType.validate(job_type)
        self.job_type = job_type
        self.is_dry_run = factory.dry_run
        self._failure_tracker = factory.failure_tracker
        self._cwd = factory.cwd
        self._executor = factory.executor
        self.workspace = factory.workspace
        self.env, self.opts = process_build_options(factory, opts, extra_options)

    def _flush_output(self):
        """Ensures all output is flushed before an external process is started.

        Without calls to this at appropriate places, it might happen that
        output from the external process comes before earlier output from this
        script in the Jenkins console log.
        """
        sys.stdout.flush()
        sys.stderr.flush()

    # TODO: Consider if these would be better set in the build script, and
    # just the values queried.
    def get_cuda_cmake_options(self):
        """Returns non-GROMACS-specific CMake options to set for CUDA native and OpenCL builds."""
        return {'CUDA_TOOLKIT_ROOT_DIR': self.env.cuda_root,
                'CUDA_HOST_COMPILER': self.env.cuda_host_compiler}

    def get_doc_cmake_options(self, doxygen_version, sphinx_version):
        """Returns non-GROMACS-specific CMake options to set for documentation builds."""
        return {'DOXYGEN_EXECUTABLE': self.env.get_doxygen_command(doxygen_version)}

    def chdir(self, path):
        """Changes the working directory for subsequent run_cmd() calls."""
        self._cwd.chdir(path)

    def _cmd_to_string(self, cmd, shell):
        """Converts a shell command from a string/list into properly escaped string."""
        if shell:
            return cmd
        elif self.env.system == System.WINDOWS:
            return subprocess.list2cmdline(cmd)
        else:
            return ' '.join([pipes.quote(x) for x in cmd])

    def run_cmd(self, cmd, shell=False, ignore_failure=False, use_return_code=False,
            failure_message=None, echo=True, **kwargs):
        """Runs a command.

        This wraps subprocess.call() and check_call() with error-handling code
        and other generic handling such as ensuring proper output flushing and
        using bash as the shell on Unix.

        Any arguments accepted by subprocess.check_call() and friends can also
        be passed.

        Args:
            cmd (str/list): Command to execute (as for subprocess.call()).
            shell (Optional[bool]): Whether cmd is a shell command as a string.
            ignore_failure (Optional[bool]): If ``True``, failure to run the
                command is ignored.
            use_return_code (Optional[bool]): If ``True``, exit code from the
                command is returned.  Otherwise, non-zero return code fails the
                build unless ignore_failure is set.
            failure_message (Optional[str]): If set, provides a friendly
                message about what in the build fails if this command fails.
                This will be reported back to Gerrit.
            echo (Optional[bool]): If ``True``, the command is echoed to stdout
                before executing.

        Returns:
            int: Command return code (if ``use_return_code=True``).
        """
        cmd_string = self._cmd_to_string(cmd, shell)
        if echo:
            print('+ ' + cmd_string)
        if self.is_dry_run:
            return 0
        if shell:
            kwargs.update(self.env.shell_call_opts)
            kwargs['shell'] = True
        if not 'cwd' in kwargs:
            kwargs['cwd'] = self._cwd.cwd
        self._flush_output()
        if use_return_code:
            return subprocess.call(cmd, **kwargs)
        try:
            subprocess.check_call(cmd, **kwargs)
        except subprocess.CalledProcessError as e:
            if not ignore_failure:
                if failure_message is None:
                    failure_message = 'failed to execute: ' + cmd_string
                raise BuildError(failure_message)

    def run_cmd_with_env(self, cmd, shell=False, **kwargs):
        """Runs a command that requires build environment variables.

        Works the same as run_cmd(), but additionally ensures that the
        compilation environment variables are set for compilers that need it.
        This method needs to be called for any command that deals with
        compilation or running the compiled binaries to ensure that the
        environment is set up properly for compilers that require scripts to be
        executed in the shell.
        """
        if self.env.env_cmd is None:
            return self.run_cmd(cmd, shell=shell, **kwargs)
        else:
            cmd_string = self._cmd_to_string(cmd, shell)
            print('+ ' + cmd_string)
            return self.run_cmd(self.env.env_cmd + ' && ' + cmd_string, shell=True, echo=False, **kwargs)

    def run_cmake(self, options):
        """Runs CMake with the provided options.

        Options from the environment, such as for selecting compilers, are
        added automatically.

        The working directory should be the build directory.
        Currently, does not support running CMake multiple times.

        Args:
            options (Dict[str,str]): Dictionary of macro definitions to pass to
                CMake using ``-D``.

        Raises:
            BuildError: If CMake fails to configure the build system.
        """
        options = options.copy()
        options['CMAKE_C_COMPILER'] = self.env.c_compiler
        options['CMAKE_CXX_COMPILER'] = self.env.cxx_compiler
        options['CMAKE_INSTALL_PREFIX'] = self.workspace.install_dir
        options.update(self.env.extra_cmake_options)
        cmake_args = [self.env.cmake_command, self.workspace.get_project_dir(Project.GROMACS)]
        if self.env.cmake_generator is not None:
            cmake_args.extend(['-G', self.env.cmake_generator])
        cmake_args.extend(
                ['-D{0}={1}'.format(key, value)
                    for key, value in sorted(options.iteritems())
                    if value is not None])
        self.run_cmd([self.env.cmake_command, '--version'])
        self.run_cmd_with_env(cmake_args,
                failure_message='CMake configuration failed')

    def build_target(self, target=None, parallel=True, keep_going=False,
            target_descr=None, failure_string=None, continue_on_failure=False):
        """Builds a given target.

        run_cmake() must have been called to generate the build system.

        Args:
            target (Optional[str]): Name of the target to build.
                If ``None``, the default (all) target is built.
            parallel (Optional[bool]): Whether parallel building is supported.
            keep_going (Optional[bool]): Whether to continue building after
                first error.
            target_descr (str or None): If given, customizes the error message
                when the target fails to build.  Should fit the initial part of
                the sentence "... failed to build".
                Ignored if ``failure_string`` is specified.
            failure_string (str or None): If given, this message is used as the
                failure message if the target fails to build.
            continue_on_failure (Optional[bool]): If ``True`` and the target
                fails to build, the failure is only reported and
                ``self.failed`` is set to ``True``.

        Raises:
            BuildError: If the target fails to build, and
                ``continue_on_failure`` is not specified.
        """
        cmd = self.env._get_build_cmd(target=target, parallel=parallel, keep_going=keep_going)
        try:
            self.run_cmd_with_env(cmd)
        except BuildError:
            if failure_string is None:
                if target_descr is not None:
                    what = target_descr
                elif target is None:
                    what = 'Default (all) target'
                else:
                    what = target + ' target'
                failure_string = '{0} failed to build'.format(what)
            if continue_on_failure:
                self._failure_tracker.mark_failed(failure_string)
            else:
                raise BuildError(failure_string)

    def run_ctest(self, args, memcheck=False, failure_string=None):
        """Runs tests using CTest.

        The build is marked unstable if any test fails.

        Args:
            args (List[str]): Additional arguments to pass to CTest.
            memcheck (Optional[bool]): If ``true``, run CTest with a memory checker.
            failure_string (Optional[str]): If give, this message is used as
                the failure message reported to Gerrit if the tests fail.
        """
        dtype = 'ExperimentalTest'
        if memcheck:
            dtype = 'ExperimentalMemCheck'
        cmd = [self.env.ctest_command, '-D', dtype]
        cmd.extend(args)
        try:
            self.run_cmd_with_env(cmd)
        except BuildError:
            if failure_string is None:
                failure_string = 'failed test: ' + self._cmd_to_string(cmd, shell=False)
            self.mark_unstable(failure_string)
        if memcheck:
            self.run_cmd('xsltproc -o Testing/Temporary/valgrind_unit.xml ../releng/ctest_valgrind_to_junit.xsl Testing/`head -n1 Testing/TAG`/DynamicAnalysis.xml', shell=True)

    def compute_md5(self, path):
        """Computes MD5 hash of a file.

        Args:
            path (str): Path to the file to compute the hash for.

        Returns:
            str: String with the computed hash in hexadecimal.
        """
        md5 = hashlib.md5()
        for block in self._executor.read_file(path, binary=True):
            md5.update(block)
        return md5.hexdigest()

    def read_cmake_variable_file(self, path):
        """Reads a file with CMake variable declarations (set commands).

        Args:
            path (str): Path to the file to read.

        Returns:
            Dict: variables found from the file, with their values.
        """
        values = dict()
        set_re = r'(?i)SET\((\w+)\s*"(.*)"\)\s*'
        for line in self._executor.read_file(path):
            match = re.match(set_re, line)
            if match:
                values[match.group(1)] = match.group(2)
        return values

    def write_package_info(self, project, file_name, version):
        """Writes an information file for a tar package.

        The file has a specific format that allows reading the information in a
        downstream build, and using the package instead of a git checkout.

        Args:
            project (Project): Project for which the package is done.
            file_name (str): Name of the package file (with extension, without
                any path).  Currently the file needs to be in the current
                working directory.
            version (str): Version for the package.
        """
        project_info = self.workspace.get_project_info(project)
        values = {
                'HEAD_HASH': project_info.head_hash,
                'BUILD_NUMBER': os.environ['BUILD_NUMBER'],
                'PACKAGE_FILE_NAME': file_name,
                'PACKAGE_VERSION': version,
                'MD5SUM': self.compute_md5(file_name)
            }
        path = self.workspace.get_path_for_logfile('package-info.log')
        self.write_property_file(path, values)

    def write_property_file(self, path, values):
        """Writes a property file at given path.

        Args:
            path (str): Path to the file to write.
            values (Dict): Dictionary of key/value pairs to write.
        """
        utils.write_property_file(self._executor, path, values)

    def make_archive(self, path, root_dir=None, use_git=False, prefix=None):
        """Creates a tar.gz archive.

        Args:
            path (str): Path to the archive to create without extension.
            root_dir (str): Root directory from which the archive should be
                created.
        """
        if prefix:
            prefix += '/'
        if use_git:
            if root_dir:
                raise ConfigurationError("archiving with root dir with git not implemented")
            cmd = ['git', 'archive', '-o', path + '.tar.gz']
            cmd.append('--prefix=' + prefix)
            cmd.extend(['-9', 'HEAD'])
            self.run_cmd(cmd)
        else:
            # TODO: Check that root_dir is a subdirectory of the workspace
            # (this all does not work if it is the workspace itself).
            if not os.path.isabs(root_dir):
                root_dir = os.path.join(self._cwd.cwd, root_dir)
            org_dir = root_dir
            root_dir, base_dir = os.path.split(root_dir)
            # TODO: Instead of renaming the directory twice, we could use
            # tarfile directly to create the archive.
            if prefix:
                base_dir = prefix
                shutil.move(org_dir, os.path.join(root_dir, prefix))
            if not base_dir:
                base_dir = '.'
            shutil.make_archive(path, 'gztar', root_dir, base_dir)
            if prefix:
                shutil.move(os.path.join(root_dir, prefix), org_dir)

    def publish_logs(self, logs, category=None):
        """Copies provided log(s) to Jenkins.

        This should be used for any files that are produced during the build
        and that need to be parsed by Jenkins (except for special cases where a
        separate method is provided, such as process_cppcheck_results()).
        This allows Jenkins configuration stay the same even if the files are
        relocated because of build system or repository reorganization.
        Alternatively, the build script can use workspace.get_path_for_logfile()
        to directly produce the log files into an invariant location.

        Args:
            logs (List[str]): Paths to files that need to be copied.
            category (Optional[str]): Category for the log file.  Log files in
                the same category are put into a common subdirectory (with the
                name of the category), allowing Jenkins to glob them for, e.g.,
                parsing warnings.
        """
        for log in logs:
            dest = self.workspace.get_path_for_logfile(os.path.basename(log), category=category)
            if self.is_dry_run:
                print('- publish {0} -> {1}'.format(log, dest))
            elif os.path.isfile(log):
                shutil.copy(log, dest)

    @property
    def failed(self):
        """Whether the build has already failed.

        This can be used in combination with build_target() argument
        continue_on_failure if the build script needs to test whether some
        previous target already has built.
        If the build script wants to stop the build in such a case, it can
        simply return; the build will always be marked failed if this
        property is ``True``.
        """
        return self._failure_tracker.failed

    def mark_unstable(self, reason, details=None):
        """Marks the build unstable.

        Args:
            reason (str): Reason printed to the build console log for the failure.
            details (Optional[List[str]]): Reason(s) reported back to Gerrit.
                If not provided, reason is used.
        """
        return self._failure_tracker.mark_unstable(reason, details)

    def process_cppcheck_results(self, xml_pattern):
        """Processes results from cppcheck.

        This method massages the XML output into a form the Jenkins
        CppCheck plugin can handle. It could also contain logic that
        would report additional information about the issues back to
        Jenkins.

        Args:
            xml_pattern (str): Pattern that matches all XML files produced by
            cppcheck.
        """

        # The Jenkins Cppcheck Plugin assumes cppcheck was run on in
        # the base folder of the slave workspace, but we run it from
        # the directory of the source repo. The docs for the plugin
        # recommend not doing that, or instead doing a sed-style
        # change on all the resulting .xml files to fix it so that the
        # plugin finds the file in the slave workspace. Thus:
        output_with_prefix = '\\1{dir}/'.format(dir=Project.GROMACS)
        for xml_filename in glob.glob(xml_pattern):
            with open(xml_filename, "r") as xml_file:
                lines = xml_file.read()
            with open(xml_filename, "w") as xml_file:
                xml_file.write(re.sub('(<location file=")', output_with_prefix, lines))

        # TODO: Consider providing an analysis/summary of the results.
        pass

    def process_clang_analyzer_results(self, html_dir=None):
        """Processes results from clang analyzer.

        Args:
            html_dir (str): Output directory to which scan-build wrote found issues.
        """
        if html_dir is None:
            html_dir = self.env.clang_analyzer_output_dir
        # The analyzer produces a subdirectory for each run with a dynamic name.
        # To make it easier to process in Jenkins, we rename it to a fixed name.
        subdirs = os.listdir(html_dir)
        output_dir = os.path.join(html_dir, 'final')
        if not subdirs:
            os.makedirs(output_dir)
            with open(os.path.join(output_dir, 'index.html'), 'w') as fp:
                fp.write("No errors\n")
            return
        if len(subdirs) > 1:
            raise ConfigurationError("unexpected multiple clang analyzer results in " + html_dir)
        # TODO: Count the issues and possibly report the files they are in etc.
        self.mark_unstable('analyzer found issues')
        shutil.move(os.path.join(html_dir, subdirs[0]), output_dir)

    def process_coverage_results(self, exclude=None):
        """Processes results from coverage runs.

        Uses gcovr to process all coverage files found in the workspace
        (from running a build compiled with --coverage).

        Args:
            exclude (List[str]): Exclusions to pass to gcovr -e (regexs).
        """
        releng_dir = self.workspace.get_project_dir(Project.RELENG)
        gromacs_dir = self.workspace.get_project_dir(Project.GROMACS)
        output_path = self.workspace.get_path_for_logfile('coverage.xml')
        self.chdir(self.workspace.build_dir)
        gcovr = os.path.join(releng_dir, 'scripts', 'gcovr-3.2')
        # TODO: This relies on gcov from the path being compatible with
        # whatever compiler was set in the build script, which is fragile.
        cmd = [gcovr, '--xml', '-r', gromacs_dir, '-o', output_path, '.']
        if exclude:
            for x in exclude:
                cmd.extend(['-e', x])
        self.run_cmd(cmd, failure_message='gcovr failed')

    @staticmethod
    def _run_build(factory, build, job_type, opts):
        """Runs the actual build.

        This method is the top-level driver for the build."""
        workspace = None
        failure_tracker = factory.failure_tracker
        executor = factory.executor
        try:
            workspace = factory.workspace
            workspace._clear_workspace_dirs()
            workspace._checkout_project(factory.default_project)
            build_script_path = workspace._resolve_build_input_file(build, '.py')
            script = BuildScript(factory.executor, build_script_path)
            if script.build_opts:
                if opts is None:
                    opts = []
                opts.extend(script.build_opts)
            context = factory.create_context(job_type, opts, script.extra_options)
            for project in script.extra_projects:
                workspace._checkout_project(project)
            workspace._print_project_info()
            workspace._check_projects()
            out_of_source = script.build_out_of_source or context.opts.out_of_source
            workspace._init_build_dir(out_of_source)
            context.chdir(workspace.build_dir)
            context._flush_output()
            script.do_build(context)
        except BuildError as e:
            failure_tracker.mark_failed(str(e))
        except ConfigurationError as e:
            failure_tracker.mark_failed('Jenkins configuration error: ' + str(e))
        failure_tracker.report(workspace)
        if failure_tracker.failed:
            executor.exit(1)
