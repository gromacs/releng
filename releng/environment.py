"""
Build and Jenkins environment handling

This file contains all the code that hardcodes details about the Jenkins build
slave environment, such as paths to various executables.
"""

from distutils.spawn import find_executable
import os

from common import ConfigurationError
from common import Compiler,System
import slaves

# TODO: Check that the paths returned/used actually exists and raise nice
# errors instead of mysteriously breaking builds if the node configuration is
# not right.
# TODO: Clean up the different mechanisms used here; even for the ~same thing,
# different approaches may be used (some might set an environment variable,
# others use an absolute path, or set a CMake option).

def append_to_env(var, string):
    if var in os.environ and os.environ[var]:
        os.environ[var] += ' ' + string
    else:
        os.environ[var] = string

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
       shell_call_opts (Dict[str, str]):
       env_cmd (str or None): Command that sets environment variables required
           by the compiler (Visual Studio and Intel uses this).
       c_compiler (str or None): Name of the C compiler executable.
       cxx_compiler (str or None): Name of the C++ compiler executable.
       cmake_command (str): Name of the CMake executable.
       ctest_command (str): Name of the CTest executable.
       cmake_generator (str or None): CMake generator being used.
       cuda_root (str or None): Root of the CUDA toolkit being used
           (for passing to CUDA_TOOLKIT_ROOT_DIR CMake option).
       cuda_host_compiler (str or None): Full path to the host compiler used
           with CUDA (for passing to CUDA_HOST_COMPILER CMake option).
       extra_cmake_options (Dict[str, str]): Additional options to pass to
           CMake.
    """

    def __init__(self, factory):
        self.system = factory.system
        self.compiler = None
        self.compiler_version = None
        self.shell_call_opts = dict()
        self.env_cmd = None
        self.c_compiler = None
        self.cxx_compiler = None
        self.cmake_command = 'cmake'
        self.ctest_command = 'ctest'
        self.cmake_generator = None
        self.cuda_root = None
        self.cuda_host_compiler = None
        self.clang_analyzer_output_dir = None
        self.extra_cmake_options = dict()

        self._build_jobs = 1
        self._build_prefix_cmd = None
        self._workspace = factory.workspace

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

    def add_env_var(self, variable, value):
        """Sets environment variable to be used for further commands.

        All subsequent commands run with BuildContext.run_cmd() etc. will use
        the environment variable.

        Args:
            variable (str): Name of environment variable to set.
            value (str): Value to set the variable to.
        """
        os.environ[variable] = value

    def prepend_path_env(self, path):
        """Prepends a path to the executable search path (PATH)."""
        os.environ['PATH'] = os.pathsep.join((os.path.expanduser(path), os.environ['PATH']))

    def append_path_env(self, path):
        """Appends a path to the executable search path (PATH)."""
        os.environ['PATH'] += os.pathsep + os.path.expanduser(path)

    def _init_system(self):
        if self.system == System.WINDOWS:
            self.cmake_generator = 'NMake Makefiles JOM'
            self._build_jobs = 4
        else:
            self.shell_call_opts['executable'] = '/bin/bash'
            self._build_jobs = 2
            self.prepend_path_env('~/bin')
            if self.system == System.OSX:
                os.environ['CMAKE_PREFIX_PATH'] = '/opt/local'
            self._init_core_dump()

    def _init_core_dump(self):
        import resource
        try:
            limits = (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
            resource.setrlimit(resource.RLIMIT_CORE, limits)
        except:
            pass

    # Methods from here down are used as build option handlers in options.py.
    # Please keep them in the same order as in process_build_options().

    def _init_cmake(self, version):
        self.prepend_path_env('~/tools/cmake-{0}/bin'.format(version))

    def init_gcc(self, version):
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

    def _manage_stdlib_from_gcc(self, format_for_stdlib_flag):
        """Manages using a C++ standard library from a particular gcc toolchain

        Use this function to configure compilers (e.g. icc or clang) to
        use the standard library from a particular gcc installation on the
        particular host in use, since the system gcc may be too old.
        """

        # TODO should setting gcctoolchain go in node-specific
        # setup somewhere? Or the C++ standard library become
        # a build option?
        gcctoolchainpath=None
        if os.getenv('NODE_NAME') == slaves.BS_CENTOS63:
            gcctoolchainpath='/opt/gcc/5.2.0'
        if os.getenv('NODE_NAME') == slaves.BS_MIC:
            # icc is used here, and is buggy with respect to libstdc++ in gcc-5
            gcctoolchainpath='/opt/gcc/4.9.3'

        if gcctoolchainpath:
            stdlibflag=format_for_stdlib_flag.format(gcctoolchain=gcctoolchainpath)
            append_to_env('CFLAGS', stdlibflag)
            append_to_env('CXXFLAGS', stdlibflag)
            format_for_linker_flags="-Wl,-rpath,{gcctoolchain}/lib64 -L{gcctoolchain}/lib64"
            self.extra_cmake_options['CMAKE_CXX_LINK_FLAGS'] = format_for_linker_flags.format(gcctoolchain=gcctoolchainpath)

    def init_clang(self, version):
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
        # Need a suitable standard library for C++11 support, so get
        # one from a gcc on the host.
        self._manage_stdlib_from_gcc('--gcc-toolchain={gcctoolchain}')

    def _init_icc(self, version):
        if self.system == System.WINDOWS:
            if self.compiler is None or self.compiler != Compiler.MSVC:
                raise ConfigurationError('need to specify msvc version for icc on Windows')
            if version == '16.0':
                # Note that installing icc 16 over icc 15 uninstalled
                # the latter, so it is likely not possible to have
                # multiple icc versions installed on Windows.
                self.env_cmd += r' && "C:\Program Files (x86)\Intel\Composer XE 2015\bin\compilervars.bat" intel64 vs' + self.compiler_version
                self.c_compiler = 'icl'
                self.cxx_compiler = 'icl'
                self.extra_cmake_options['CMAKE_EXE_LINKER_FLAGS'] = '"/machine:x64"'
            else:
                raise ConfigurationError('only icc 16.0 is supported for Windows builds with the Intel compiler')
        else:
            self.c_compiler = 'icc'
            self.cxx_compiler = 'icpc'
            if version == '16.0':
                self.env_cmd = '. /opt/intel/compilers_and_libraries_2016/linux/bin/compilervars.sh intel64'
            elif version == '15.0':
                self.env_cmd = '. /opt/intel/composer_xe_2015/bin/compilervars.sh intel64'
            elif version == '14.0':
                self.env_cmd = '. /opt/intel/composer_xe_2013_sp1/bin/compilervars.sh intel64'
            elif version == '13.0':
                self.env_cmd = '. /opt/intel/composer_xe_2013/bin/compilervars.sh intel64'
            elif version == '12.1':
                self.env_cmd = '. /opt/intel/composer_xe_2011_sp1/bin/compilervars.sh intel64'
            else:
                raise ConfigurationError('only icc 12.1, 13.0, 14.0, 15.0, 16.0 are supported, got icc-' + version)

            # Need a suitable standard library for C++11 support.
            # icc on Linux is required to use the C++ headers and
            # standard libraries from a gcc installation, and defaults
            # to that of the gcc it finds in the path.
            self._manage_stdlib_from_gcc('-gcc-name={gcctoolchain}/bin/gcc')
        self.compiler = Compiler.INTEL
        self.compiler_version = version

    def _init_msvc(self, version):
        self.compiler = Compiler.MSVC
        self.compiler_version = version
        if version == '2010':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64'
        elif version == '2013':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\vcvarsall.bat" amd64'
        elif version == '2015':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat" amd64'
        else:
            raise ConfigurationError('only Visual Studio 2010, 2013, and 2013 are supported, got msvc-' + version)

    def init_clang_analyzer(self, clang_version=None, html_output_dir=None):
        if clang_version is not None:
            self.init_clang(clang_version)
        if html_output_dir is None:
            html_output_dir = self._workspace.get_log_dir(category='scan_html')
        self.clang_analyzer_output_dir = html_output_dir
        analyzer = self._find_executable(self.c_compiler)
        os.environ['CCC_CC'] = self.c_compiler
        os.environ['CCC_CXX'] = self.cxx_compiler
        scan_build_path = os.path.expanduser('~/bin/scan-build-path')
        self.cxx_compiler = os.path.join(scan_build_path, 'c++-analyzer')
        self._build_prefix_cmd = [scan_build_path + '/scan-build',
                '--use-analyzer', analyzer, '-o', html_output_dir]

    def _find_executable(self, name):
        """Returns the full path to the given executable."""
        # If we at some point require Python 3.3, shutil.which() would be
        # more obvious.
        return find_executable(name)

    def _init_cuda(self, version):
        self.cuda_root = '/opt/cuda_' + version

    def _init_phi(self):
        self.extra_cmake_options['CMAKE_PREFIX_PATH'] = os.path.expanduser('~/utils/libxml2')

    def _init_tsan(self):
        os.environ['LD_LIBRARY_PATH'] = os.path.expanduser('~/tools/gcc-nofutex/lib64')

    def _init_atlas(self):
        os.environ['CMAKE_LIBRARY_PATH'] = '/usr/lib/atlas-base'

    def _init_mpi(self, use_gpu):
        # Set the host compiler to the underlying compiler.
        # Normally, C++ compiler should be used, but nvcc <=v5.0 does not
        # recognize icpc, only icc, so for simplicity the C compiler is used
        # for all cases, as it works as well.
        if use_gpu and self.compiler in (Compiler.GCC, Compiler.INTEL) and self.system != System.WINDOWS:
            c_compiler_path = self._find_executable(self.c_compiler)
            if not c_compiler_path:
                raise ConfigurationError("Could not determine the full path to the compiler ({0})".format(self.c_compiler))
            self.cuda_host_compiler = c_compiler_path
        os.environ['OMPI_CC'] = self.c_compiler
        os.environ['OMPI_CXX'] = self.cxx_compiler
        self.c_compiler = 'mpicc'
        self.cxx_compiler = 'mpic++'
