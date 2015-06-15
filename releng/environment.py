"""
Build and Jenkins environment handling

This file contains all the code that hardcodes details about the Jenkins build
slave environment, such as paths to various executables.
"""

from distutils.spawn import find_executable
import os
import platform

from common import ConfigurationError
from common import Compiler,System

# TODO: Check that the paths returned/used actually exists and raise nice
# errors instead of mysteriously breaking builds if the node configuration is
# not right.
# TODO: Clean up the different mechanisms used here; even for the ~same thing,
# different approaches may be used (some might set an environment variable,
# others use an absolute path, or set a CMake option).

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

    def __init__(self, system):
        if system is None:
            system = platform.system()
        self.system = System.parse(system)
        self.compiler = None
        self.shell_call_opts = dict()
        self.env_cmd = None
        self.c_compiler = None
        self.cxx_compiler = None
        self.cmake_command = 'cmake'
        self.ctest_command = 'ctest'
        self.cmake_generator = None
        self.cuda_root = None
        self.cuda_host_compiler = None
        self.extra_cmake_options = dict()

        self._build_jobs = 1
        self._build_prefix_cmd = None

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

    def _get_build_cmd(self, target=None, parallel=True):
        cmd = []
        if self._build_prefix_cmd is not None:
            cmd.extend(self._build_prefix_cmd)
        cmd.extend([self.cmake_command, '--build', '.'])
        if target is not None:
            cmd.extend(['--target', target])
        jobs = self._build_jobs if parallel else 1
        cmd.extend(['--', '-j{0}'.format(jobs)])
        return cmd

    def _add_env_var(self, variable, value):
        os.environ[variable] = value

    def _prepend_path_env(self, path):
        os.environ['PATH'] = os.pathsep.join(os.path.expanduser(path), os.environ['PATH'])

    def _append_path_env(self, path):
        os.environ['PATH'] += os.pathsep + os.path.expanduser(path)

    def _init_system(self):
        if self.system == System.WINDOWS:
            self.cmake_generator = 'NMake Makefiles JOM'
            self._build_jobs = 4
        else:
            self.shell_call_opts['executable'] = '/bin/bash'
            self._build_jobs = 2
            self._append_path_env('~/bin')
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
        self._prepend_path_env('~/tools/cmake-{0}/bin'.format(version))

    def _init_gcc(self, version):
        self.compiler = Compiler.GCC
        self.c_compiler = 'gcc-' + version
        self.cxx_compiler = 'g++-' + version

    def _init_clang(self, version):
        self.compiler = Compiler.CLANG
        self.c_compiler = 'clang-' + version
        self.cxx_compiler = 'clang++-' + version
        if os.getenv('NODE_NAME') in ('bs_centos63', 'bs_mic'):
            os.environ['CFLAGS'] = os.environ['CXXFLAGS'] = '--gcc-toolchain=/opt/rh/devtoolset-1.1/root/usr'

    def _init_icc(self, version):
        # TODO: The version is ignored; this can be very misleading if the tag
        # in Jenkins does not actually match the version of icc installed on
        # the node.
        # If it is not possible to install multiple icc versions, then the code
        # here should check that the installed icc actually has the correct
        # version.
        self.compiler = Compiler.INTEL
        if self.system == System.WINDOWS:
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64 && "C:\Program Files (x86)\Intel\Composer XE\bin\compilervars.bat" intel64 vs2010'
            self.c_compiler = 'icl'
            self.cxx_compiler = 'icl'
            # Remove incremental which is added by CMake to avoid warnings.
            self.extra_cmake_options['CMAKE_EXE_LINKER_FLAGS'] = '"/STACK:10000000 /machine:x64"'
        else:
            self.env_cmd = '. /opt/intel/bin/iccvars.sh intel64'
            self.c_compiler = 'icc'
            self.cxx_compiler = 'icpc'

    def _init_msvc(self, version):
        self.compiler = Compiler.MSVC
        if version == '2010':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\vcvarsall.bat" amd64'
        elif version == '2013':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC\vcvarsall.bat" amd64'
        elif version == '2015':
            self.env_cmd = r'"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat" amd64'
        else:
            raise ConfigurationError('only Visual Studio 2010, 2013, and 2013 are supported, got msvc-' + version)

    def init_clang_analyzer(self, clang_version, html_output_dir):
        self._init_clang(clang_version)
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
