"""
Exceptions and enums used throughout the releng package

For simplicity and ease of use in certain contexts, the enum values are
represented as strings, where the strings may have special meaning in some
contexts.
"""

class BuildError(Exception):
    """Exception to signal build failure that immediately terminates the build

    Reason for termination is provided as the exception args."""

class ConfigurationError(Exception):
    """Exception to signal errors in the build configuration

    Reason for the error is provided as the exception args."""

class Enum(object):
    """Common methods to validate and convert enum values.

    Subclasses need to provide a tuple of valid values as a _values class
    attribute.
    """

    @classmethod
    def validate(cls, value):
        """Checks that a value is a valid enum value."""
        if value not in cls._values:
            raise ConfigurationError('unknown {0}: {1}'.format(cls.__name__, value))

    @classmethod
    def parse(cls, value):
        """Converts a string to an enum value.

        Args:
            value[str]: String to convert.
        """
        for allowed in cls._values:
            if value.lower() == allowed.lower():
                return allowed
        raise ConfigurationError('unknown {0}: {1}'.format(cls.__name__, value))

class System(Enum):
    """Enum to indicate the OS on which the build is running"""

    # Currently, the string values should match the result of
    # platform.system().lower(), which is used to simplify initialization.
    WINDOWS = 'windows'
    LINUX = 'linux'
    OSX = 'darwin'

    _values = (WINDOWS, LINUX, OSX)

class Project(Enum):
    """Enum to identify a git repository/directory used in the build"""

    # Currently, the string values should match the names of the repositories
    # in Gerrit, so that git URLs and checkout paths can be constructed from
    # these.
    GROMACS = 'gromacs'
    REGRESSIONTESTS = 'regressiontests'
    RELENG = 'releng'

    _values = (GROMACS, REGRESSIONTESTS, RELENG)

class JobType(Enum):
    """Enum to identify type/scope of the job

    This can be used in the build scripts to, e.g., decide on the scope of
    testing."""

    # There is no special significance with these strings.
    GERRIT = 'gerrit'
    NIGHTLY = 'nightly'

    _values = (GERRIT, NIGHTLY)

class Compiler(Enum):
    """Enum to identify the compiler used in the build"""

    # There is no special significance with these strings.
    GCC = 'gcc'
    CLANG = 'clang'
    INTEL = 'icc'
    MSVC = 'msvc'

    _values = (GCC, CLANG, INTEL, MSVC)

class BuildType(Enum):
    """Enum to identify the build type/configuration to use"""

    # There is no special significance with these strings.
    DEBUG = 'Debug'
    REFERENCE = 'Reference'
    OPTIMIZED = 'Optimized'
    PERFORMANCE = 'Performance'
    ASAN = 'ASan'
    TSAN = 'TSan'

    _values = (DEBUG, REFERENCE, OPTIMIZED, PERFORMANCE, ASAN, TSAN)

class Simd(Enum):
    """Enum to identify the SIMD instruction set to use"""

    # Currently, these strings should match with the expected values for
    # GMX_SIMD.  While not ideal for decoupling the repositories, this
    # simplifies the gromacs.py build script significantly.
    NONE = 'None'
    REFERENCE = 'Reference'
    SSE2 = 'SSE2'
    SSE41 = 'SSE4.1'
    AVX_128_FMA = 'AVX_128_FMA'
    AVX_256 = 'AVX_256'
    AVX2_256 = 'AVX2_256'

    _values = (NONE, REFERENCE, SSE2, SSE41, AVX_128_FMA, AVX_256, AVX2_256)

class FftLibrary(Enum):
    """Enum to identify the FFT library to use"""

    # There is no special significance with these strings.
    FFTPACK = 'fftpack'
    FFTW3 = 'fftw3'
    MKL = 'mkl'

    _values = (FFTPACK, FFTW3, MKL)
