"""
Build and Jenkins environment handling

This file contains all the code that hardcodes details about the Jenkins build
agent environment, such as paths to various executables.
"""

import os

from common import ConfigurationError
from common import Compiler,System
import cmake
import agents
import re

# TODO: Check that the paths returned/used actually exists and raise nice
# errors instead of mysteriously breaking builds if the node configuration is
# not right.
# TODO: Clean up the different mechanisms used here; even for the ~same thing,
# different approaches may be used (some might set an environment variable,
# others use an absolute path, or set a CMake option).

def _to_version_tuple(version_string):
    return [int(x) for x in version_string.split('.')]

def _is_older_version(older, newer):
    return _to_version_tuple(older) < _to_version_tuple(newer)

class BuildEnvironment(object):
    """Provides access to the build environment.

    Most details of the build environment are handled transparently based on
    the provided build options, and the build script does not need to consider
    this.  For build scripts, the main interface this class provides is to find
    locations of some special executables (such as cppcheck) that may be needed
    for the build.  Compiler selection is handled without special action from
    build scripts.

    In rare cases, the build scripts may benefit from inspecting the attributes
    in this class to determine, e.g., the operating system running the build or
    the compiler being used.

    Attributes:
       system (System): Operating system of the build node.
       compiler (Compiler or None): Selected compiler.
       compiler_version (string): Version number for the selected compiler.
       c_compiler (str or None): Name of the C compiler executable.
       cxx_compiler (str or None): Name of the C++ compiler executable.
       libcxx_version (str or None): Version of libc++ to use
       doxygen_command (str): Name of the doxygen executable.
       gcov_command (str): Name of the gcov executable.
       cmake_command (str): Name of the CMake executable.
       ctest_command (str): Name of the CTest executable.
       cmake_version (str): Version of the CMake executable.
       cmake_generator (str or None): CMake generator being used.
       armhpc_version (str or None): The version of the ARM HPC toolchain.
       armpl_dir (str or None): the ARM Perf Libraries directory
       cuda_root (str or None): Root of the CUDA toolkit being used
           (for passing to CUDA_TOOLKIT_ROOT_DIR CMake option).
       libhwloc_root (str or None): Root of the hwloc library being used
           (for adding to CMake search path).
       opencl_version (str or None): OpenCL API version expected to be detected.
       cuda_host_compiler (str or None): Full path to the host compiler used
           with CUDA (for passing to CUDA_HOST_COMPILER CMake option).
       amdappsdk_root (str or None): Root of the AMD SDK being used
           (for using as AMDAPPSDKROOT environment variable).
       extra_cmake_options (Dict[str, str]): Additional options to pass to
           CMake.
    """

    def __init__(self, factory):
        self.system = factory.system
        self.compiler = None
        self.compiler_version = None
        self.c_compiler = None
        self.cxx_compiler = None
        self.doxygen_command = None
        self.gcov_command = None
        self.cmake_command = 'cmake'
        self.ctest_command = 'ctest'
        self.cmake_version = None
        self.cmake_generator = None
        self.armhpc_version = None
        self.armpl_dir = None
        self.cuda_root = None
        self.opencl_version = None
        self.cuda_host_compiler = None
        self.amdappsdk_root = None
        self.clang_analyzer_output_dir = None
        self.libcxx_version = None
        self.extra_cmake_options = dict()
        self.gcc_exe = None

        self._build_prefix_cmd = None
        self._cmd_runner = factory.cmd_runner
        self._workspace = factory.workspace
        self._node_name = factory.jenkins.node_name
        self._cmake_base_dir = None

        self._build_jobs = agents.get_default_build_parallelism(self._node_name)

        environment_command = agents.get_environment_subshell(self._node_name)
        if environment_command:
            environment_dump_command = environment_command + ' -- {0} -E environment'.format(self.cmake_command)
            self._cmd_runner.import_env(environment_dump_command)

        if self.system is not None:
            self._init_system()

    def get_cppcheck_command(self, version):
        """Returns path to the cppcheck executable of given version.

        Args:
            version (str): cppcheck version to use.
        """
        return os.path.expanduser('~/bin/cppcheck-{0}'.format(version))

    def get_doxygen_command(self, version):
        """Returns path to the Doxygen executable of given version.

        Args:
            version (str): Doxygen version to use.
        """
        return os.path.expanduser('~/tools/doxygen-{0}/bin/doxygen'.format(version))

    def get_uncrustify_command(self):
        """Returns path to the uncrustify executable."""
        return os.path.expanduser('~/bin/uncrustify')

    def _get_build_cmd(self, target=None, parallel=True, keep_going=False):
        cmd = []
        if self._build_prefix_cmd is not None:
            cmd.extend(self._build_prefix_cmd)
        cmd.extend([self.cmake_command, '--build', '.'])
        if target is not None:
            cmd.extend(['--target', target])
        jobs = self._build_jobs if parallel else 1
        cmd.extend(['--', '-j{0}'.format(jobs)])
        if keep_going:
            cmd.append('-k')
        return cmd

    def _set_cmake_minimum_version(self, version):
        if self.cmake_version or not version:
            return
        current_version = cmake.get_cmake_version(self._cmd_runner, self.cmake_command)
        self.cmake_version = current_version
        if not _is_older_version(current_version, version):
            return
        available_versions = self._get_available_cmake_versions()
        for test_version in available_versions:
            if not _is_older_version(test_version, version):
                self._init_cmake(test_version)

    def _get_available_cmake_versions(self):
        versions = []
        for cmake_dir in os.listdir(self._cmake_base_dir):
            cmd = os.path.join(self._cmake_base_dir, cmake_dir, 'bin', 'cmake')
            if self.system == System.WINDOWS and not cmd.endswith('.exe'):
                cmd += '.exe'
            if os.path.isfile(cmd):
                versions.append(cmake_dir.split("-")[-1])
        versions.sort(key=_to_version_tuple)
        return versions

    def set_env_var(self, variable, value):
        """Sets environment variable to be used for further commands.

        All subsequent commands run with BuildContext.run_cmd() etc. will use
        the environment variable.

        Args:
            variable (str): Name of environment variable to set.
            value (str): Value to set the variable to.  As a convenience, if
                the value is None, nothing is done.
        """
        self._cmd_runner.set_env_var(variable, value)

    def append_to_env_var(self, variable, value):
        self._cmd_runner.append_to_env_var(variable, value)

    def prepend_path_env(self, path):
        """Prepends a path to the executable search path (PATH)."""
        self._cmd_runner.prepend_to_env_var('PATH', os.path.expanduser(path), sep=os.pathsep)

    def append_path_env(self, path):
        """Appends a path to the executable search path (PATH)."""
        self._cmd_runner.append_to_env_var('PATH', os.path.expanduser(path), sep=os.pathsep)

    def run_env_script(self, env_cmd):
        # Capture the environment created by sourcing env_cmd
        env_dump_cmd = env_cmd + ' && {0} -E environment'.format(self.cmake_command)
        self._cmd_runner.import_env(env_dump_cmd)

    def get_env_var(self, variable):
        return self._cmd_runner.get_env_var(variable)

    def _init_system(self):
        if self.system == System.WINDOWS:
            self.cmake_generator = 'NMake Makefiles JOM'
            self._cmake_base_dir = 'c:\\utils'
        else:
            self.prepend_path_env('~/bin')
            if self.system == System.OSX:
                self.set_env_var('CMAKE_PREFIX_PATH', '/opt/local')
            # If/when we want core dumps from builds, enable
            # the next line
            # self._init_core_dump()
            self._cmake_base_dir = ('/opt/cmake')

    def _init_core_dump(self):
        import resource
        try:
            limits = (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
            resource.setrlimit(resource.RLIMIT_CORE, limits)
        except:
            pass

    # Methods from here down are used as build option handlers in options.py.
    # Please keep them in the same order as in process_build_options().

    def _set_build_jobs(self, jobs):
        self._build_jobs = jobs

    def _init_cmake(self, version):
        cmake_bin_dir = os.path.join(self._cmake_base_dir, 'cmake-' + version, 'bin')
        if not os.path.exists(cmake_bin_dir):
            cmake_bin_dir = os.path.join(self._cmake_base_dir, version, 'bin')
        self.cmake_command = os.path.join(cmake_bin_dir, 'cmake')
        self.ctest_command = os.path.join(cmake_bin_dir, 'ctest')
        self.cmake_version = version

    def _init_gcc(self, version):
        """Initializes the build to use given gcc version as the compiler.

        This method is called internally if the build options set the compiler
        (with gcc-X.Y), but it can also be called directly from a build script
        if the build does not use options.

        Args:
            version (str): GCC version number (major.minor) to use.
        """
        self.compiler = Compiler.GCC
        self.compiler_version = version
        self.c_compiler = 'gcc-' + version
        self.cxx_compiler = 'g++-' + version
        self.gcov_command = 'gcov-' + version

    # TODO relocate this function to just above _manage_stdlib declaration.
    def _locate_gcc(self, format_for_stdlib_flag, use_stdlib_through_env_vars):
        """Locates a gcc toolchain to use with this build

        Use this function to prepare compilers (gcc, icc or clang) to
        use the standard library from a particular gcc installation on
        the particular agent in use, since the default system gcc may
        be too old.

        Requires that self.compiler describes the actual compiler to use.

        Once the oldest supported version is GROMACS 2020, the
        format_for_stdlib_flag and use_stdlib_through_env_vars
        arguments will no longer be required.

        Args:
        format_for_stdlib_flag(str): A format string expecting a named
           gcctoolchain parameter containing the base part of the path
           to an installed gcc (e.g. '/usr/local' for '/usr/local/bin/gcc')
           to pass to the compiler so that it finds the matching libstdc++
           to use when compiling.
        use_stdlib_through_env_vars(bool): Whether to use CFLAGS/CXXFLAGS
           environment variables to set the C++ standard library for
           compilation, as used before GROMACS 2020

        """

        # Artefacts built by all C++ compilers require link-time
        # access to a C++ standard library, and often other libraries
        # such as for OpenMP or sanitizers are typically installed
        # alongside that standard library. So for gcc, we ensure that
        # we link to components from the matching gcc version, rather
        # than the system default gcc. For clang and icc, we link to a
        # gcc specified for each build agent.
        gcc_name=None
        if self.compiler == Compiler.GCC:
            gcc_name = self.c_compiler
        elif self.compiler == Compiler.CLANG or self.compiler == Compiler.INTEL:
            gcc_name = agents.get_default_gcc_for_libstdcxx(self._node_name)

        gcc_toolchain_path=None
        if gcc_name:
            gcc_exe = self._cmd_runner.find_executable(gcc_name)
            if self.compiler != Compiler.GCC:
                self.gcc_exe = gcc_exe
            gcc_exe_dirname = os.path.dirname(gcc_exe)
            gcc_toolchain_path = os.path.join(gcc_exe_dirname, '..')

        if gcc_toolchain_path:
            if format_for_stdlib_flag and use_stdlib_through_env_vars:
                stdlibflag=format_for_stdlib_flag.format(gcctoolchain=gcc_toolchain_path)
                self.append_to_env_var('CFLAGS', stdlibflag)
                self.append_to_env_var('CXXFLAGS', stdlibflag)
            # Linker flag needed for all (#2846)
            format_for_linker_flags="-Wl,-rpath,{gcctoolchain}/lib64 -L{gcctoolchain}/lib64"
            self.extra_cmake_options['CMAKE_CXX_LINK_FLAGS'] = format_for_linker_flags.format(gcctoolchain=gcc_toolchain_path)

    def _init_clang(self, version):
        """Initializes the build to use given clang version as the compiler.

        This method is called internally if the build options set the compiler
        (with clang-X.Y), but it can also be called directly from a build
        script if the build does not use options.

        Args:
            version (str): clang version number (major.minor) to use.
        """
        self.compiler = Compiler.CLANG
        self.compiler_version = version
        self.c_compiler = 'clang-' + version
        self.cxx_compiler = 'clang++-' + version
        # Symbolizer is only required for ASAN builds, but should not do any
        # harm to always set it (and that is much simpler).
        clang_path = self._cmd_runner.find_executable(self.c_compiler)
        clang_path = os.path.dirname(clang_path)
        symbolizer_path = os.path.join(clang_path, 'llvm-symbolizer')
        self.set_env_var('ASAN_SYMBOLIZER_PATH', symbolizer_path)
        # Test binaries compiled with clang OpenMP support need to
        # find at run time the libomp.so that matches the compiler
        # (libgomp.so is not suitable).
        self.set_env_var('LD_LIBRARY_PATH', os.path.join(clang_path, '../lib'))

    def _init_armclang(self, version):
        """Initializes the build to use given armclang version as the compiler.

        This method is called internally if the build options set the compiler
        (with armclang-X.Y), but it can also be called directly from a build
        script if the build does not use options.

        Args:
            version (str): armclang version number (major.minor) to use.
        """
        self.compiler = Compiler.ARMCLANG
        self.compiler_version = version

        self.c_compiler   = 'armclang'
        self.cxx_compiler = 'armclang++'

    def _init_libcxx(self, version):
        """Initializes the build to use given libc++ (from LLVM project)

        This method is called internally if the build options specify it
        (with libcxx-X.Y), but it can also be called directly from a build
        script if the build does not use options.

        This option is only valid with clang, and only valid with a clang
        version of the same number

        Args:
            version (str): libcxx version number (major.minor) to use.
        """
        self.libcxx_version = version

    def _init_icc(self, version):
        if self.system == System.WINDOWS:
            if self.compiler is None or self.compiler != Compiler.MSVC:
                raise ConfigurationError('need to specify msvc version for icc on Windows')
            self.c_compiler = 'icl'
            self.cxx_compiler = 'icl'
            self.compiler = Compiler.INTEL
            self.extra_cmake_options['CMAKE_EXE_LINKER_FLAGS'] = '"/machine:x64"'
            if version == '15.0':
                self.run_env_script(r'"C:\Program Files (x86)\Intel\Composer XE 2015\bin\compilervars.bat" intel64 vs' + self.compiler_version)
            # TODO remove the next clause when no matrices use it any more
            elif version == '16.0':
                self.run_env_script(r'"C:\Program Files (x86)\IntelSWTools\compilers_and_libraries_2016\windows\bin\compilervars.bat" intel64 vs' + self.compiler_version)
            elif re.match('^(\d\d)$', version):
                self.run_env_script(r'"C:\Program Files (x86)\IntelSWTools\compilers_and_libraries_20{0}\windows\bin\compilervars.bat" intel64 vs{1}'.format(version, self.compiler_version))
            else:
                raise ConfigurationError('invalid icc version: got icc-{0}. Try a version with two digits, e.g. 18 for 2018 release.'.format(version))
        else:
            self.c_compiler = 'icc'
            self.cxx_compiler = 'icpc'
            self.compiler = Compiler.INTEL
            if re.match('^(\d\d)$', version):
                self.run_env_script('. /opt/intel/compilers_and_libraries_20{0}/linux/bin/compilervars.sh intel64'.format(version))
            # TODO remove the next clause when no matrices use it any more
            elif version == '16.0':
                self.run_env_script('. /opt/intel/compilers_and_libraries_2016/linux/bin/compilervars.sh intel64')
            elif version == '15.0':
                self.run_env_script('. /opt/intel/composer_xe_2015/bin/compilervars.sh intel64')
            elif version == '14.0':
                self.run_env_script('. /opt/intel/composer_xe_2013_sp1/bin/compilervars.sh intel64')
            elif version == '13.0':
                self.run_env_script('. /opt/intel/composer_xe_2013/bin/compilervars.sh intel64')
            elif version == '12.1':
                self.run_env_script('. /opt/intel/composer_xe_2011_sp1/bin/compilervars.sh intel64')
            else:
                raise ConfigurationError('invalid icc version: got icc-{0}. Try a version with two digits, e.g. 18 for 2018 release.'.format(version))

        self.compiler_version = version

    def _init_msvc(self, version):
        self.compiler = Compiler.MSVC
        self.compiler_version = version
        if version == '2010':
            self.run_env_script(r'"C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64')
        elif version == '2013':
            self.run_env_script(r'"C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\vcvarsall.bat" amd64')
        elif version == '2015':
            self.run_env_script(r'"C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" amd64 -vcvars_ver=14.0')
        elif version == '2017':
            self.run_env_script(r'"C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" amd64')
        else:
            raise ConfigurationError('only Visual Studio 2010, 2013, 2015, and 2017 are supported, got msvc-' + version)
        self._cmd_runner.copy_env_var("caexcludepath", "INCLUDE") #fragile because function is case sensitive

    def _init_clang_static_analyzer(self, version):
        scan_build = 'scan-build-' + version
        cxx_analyzer = 'c++-analyzer-' + version
        html_output_dir = self._workspace.get_log_dir(category='scan_html')
        self.clang_analyzer_output_dir = html_output_dir
        self.set_env_var('CCC_CC', self.c_compiler)
        self.set_env_var('CCC_CXX', self.cxx_compiler)
        self.cxx_compiler = cxx_analyzer
        self._build_prefix_cmd = [scan_build,
                '-o', html_output_dir]

    def _init_doxygen(self, version):
        self.doxygen_command = os.path.expanduser('~/tools/doxygen-{0}/bin/doxygen'.format(version))

    def _init_armhpc(self, version):
        self.armhpc_version = version
        module_load = '. /usr/share/modules/init/sh && module load '
        if version == '18.3' or version == '18.4':
            self.run_env_script(module_load + 'Generic-AArch64/Ubuntu/16.04/arm-hpc-compiler/' + version)
        else:
            raise ConfigurationError('Only the ARM HPC compiler 18.3 and 18.4 are supported, was passed ' + version)

    def _init_armpl(self):
        if not self.armhpc_version:
            raise ConfigurationError('ARM Perf Libs are only supported in conjunction with the ARM HPC compilers' + version)
        else:
            # ARMPL module name has the form
            # Generic-AArch64/Ubuntu/16.04/gcc-X.Y.Z/armpl/J.K.L, where we assume Z == L == 0
            # Generic-AArch64/Ubuntu/16.04/arm-hpc-compiler-J.K/armpl/J.K.L, where L == 0
            module_load = '. /usr/share/modules/init/sh && module load '
            if self.compiler == Compiler.ARMCLANG:
                self.run_env_script(module_load + 'Generic-AArch64/Ubuntu/16.04/arm-hpc-compiler-' + self.compiler_version + '/armpl/' + self.armhpc_version + '.0')
            elif self.compiler == Compiler.GCC:
                self.run_env_script(module_load + 'Generic-AArch64/Ubuntu/16.04/gcc-' + self.compiler_version + '.0/armpl/' + self.armhpc_version + '.0')
            else:
                raise ConfigurationError('ARM Perf Libs will only work with armclang or gcc, but the compiler in use is: ' + self.cxx_compiler)
            self.armpl_dir = self.get_env_var('ARMPL_DIR')

    def _init_cuda(self, version):
        self.cuda_root = '/opt/cuda_' + version

    def _init_libhwloc(self, version):
        self.libhwloc_root = '/opt/hwloc/' + version
        self._cmd_runner.prepend_to_env_var('HWLOC_DIR', self.libhwloc_root)

    # TODO: remove when no longer supporting legacy matrix formats
    def _init_opencl_legacy(self, version):
        self.opencl_version = '1.1'

    def _init_opencl(self, version):
        self.opencl_version = version

    # TODO: remove this (and its docs) when no longer supporting legacy matrix formats
    def _init_amdappsdk(self, version):
        self.amdappsdk_root = '/opt/AMDAPPSDK-' + version

    def _init_clFFT(self, version):
        self.clFFT_root = '/opt/clFFT/' + version

    def _init_phi(self):
        self.extra_cmake_options['CMAKE_PREFIX_PATH'] = os.path.expanduser('~/utils/libxml2')

    def _init_atlas(self):
        self.set_env_var('CMAKE_LIBRARY_PATH', '/usr/lib/atlas-base')

    def _init_mpi(self):
        pass

    def _manage_stdlib(self, use_stdlib_through_env_vars):
        """Coordinates the C++ standard library to use in the build

        Artefacts built by all C++ compilers require link-time access
        to a C++ standard library. This works differently for each
        compiler, and can be influenced by build options or the
        operating system.

        Often the standard library comes from an installation of gcc,
        and it is generally necessary to avoid the main compiler
        finding the system default gcc, which may be too old to be
        useful. A particular gcc installation is pre-specified for
        each agent to cater for this.

        Requires that self.compiler and self.system are specified
        accurately.

        Args:
        use_stdlib_through_env_vars(bool): Whether to use CFLAGS/CXXFLAGS
           environment variables to set the C++ standard library for
           compilation, as used before GROMACS 2020

        """
        if self.compiler == Compiler.CLANG:
            # The clang compiler can use either libstdc++ or libc++.
            if self.libcxx_version is None:
                # Use libstdc++ from the pre-specified gcc for this
                # agent.
                self._locate_gcc('--gcc-toolchain={gcctoolchain}', use_stdlib_through_env_vars)
                return
            else:
                # Use libc++ from this clang installation
                if self.compiler_version != self.libcxx_version:
                    raise ConfigurationError('libcxx version must match clang version')
                self.append_to_env_var('CXXFLAGS', '-stdlib=libc++')
                return
        else:
            if self.libcxx_version is not None:
                raise ConfigurationError('libcxx only supported with clang')

        if self.compiler == Compiler.INTEL and self.system != System.WINDOWS:
            # The Intel compiler on Linux must use a libstdc++ from
            # the pre-specified gcc for this agent.
            self._locate_gcc('-gcc-name={gcctoolchain}/bin/gcc', use_stdlib_through_env_vars)
            return

        if self.compiler == Compiler.GCC:
            # Newer gcc needs to be linked against compatible standard
            # libraries from the pre-specified gcc for this agent.
            self._locate_gcc(None, use_stdlib_through_env_vars)
            return

        # The remaining compilers run on Windows and organize these
        # details themselves.

    def _finalize(self, use_stdlib_through_env_vars):
        """Manages handling that has complex dependencies between inputs

        Args:
        use_stdlib_through_env_vars(bool): Whether to use CFLAGS/CXXFLAGS
           environment variables to set the C++ standard library for
           compilation.
           Defaults to True, which is used by branches prior to GROMACS 2020.

        """
        if use_stdlib_through_env_vars is None:
            use_stdlib_through_env_vars = True
        self._manage_stdlib(use_stdlib_through_env_vars)
