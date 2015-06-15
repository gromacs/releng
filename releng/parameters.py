"""
Parameters to pass to build scripts
"""

class BuildParameters(object):
    """Build parameters from build options.

    These parameters are not used by the releng package; they are set based on
    build options provided, and passed to the build script (accessible through
    the params attribute of the build context).
    The build script can do appropriate things with these values if it supports
    the option.

    Each attribute is either None or an empty container if the corresponding
    build option is not provided.  In such a case, it is up to the build script
    to determine the default, and either pass an appropriate option to the
    build system, or just let the build system use its own default.

    Attributes:
        build_type (BuildType): Build type to use.
        mdrun_only (bool): Whether to do an mdrun-only build.
        phi (bool): Whether to build for Xeon Phi.
        double (bool): Whether to do a double-precision build.
        simd (Simd): SIMD option to use.
        mpi (bool): Whether to do a build with an MPI library.
        thread_mpi (bool): Whether to do a build with thread-MPI.
        gpu (bool): Whether to do a GPU build.
        openmp (bool): Whether to do a build with OpenMP
        fft_library (FftLibrary): FFT library to use.
        external_linalg (bool): Whether to use external BLAS/LAPACK libraries.
        x11 (bool): Whether to build with X11 support.
        memcheck (bool): Whether to run some tests with memory checking.
            It is up to the build script to call BuildContext.run_ctest()
            to actually respect this option.
        extra_cmake_options (Dict[str,str]): Extra options to pass to CMake.
            These are passed automatically, without additional action from the
            build script.
        extra_gmxtest_args (List[str]): Extra command-line arguments to pass to
            gmxtest.pl.  The build script needs to use these if it calls
            gmxtest.pl to respect the gmxtest+ build options.
    """
    def __init__(self):
        self.build_type = None
        self.mdrun_only = None
        self.phi = None
        self.double = None
        self.simd = None
        self.mpi = None
        self.thread_mpi = None
        self.gpu = None
        self.openmp = None
        self.fft_library = None
        self.external_linalg = None
        self.x11 = None
        self.memcheck = None
        self.extra_cmake_options = dict()
        self.extra_gmxtest_args = []
