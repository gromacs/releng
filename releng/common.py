"""
Exceptions and enums used throughout the releng package

For simplicity and ease of use in certain contexts, the enum values are
represented as strings, where the strings may have special meaning in some
contexts.
"""

import re

def to_python_identifier(string):
    """Makes a valid Python identifier from a string."""
    return re.sub(r'[^0-9a-zA-Z_]', '_', string)

class BuildError(Exception):
    """Exception to signal build failure that immediately terminates the build

    Reason for termination is provided as the exception args."""

class CommandError(BuildError):
    """Exception to signal failure to execute an external command."""

    def __init__(self, cmd_string):
        BuildError.__init__(self, 'failed to execute: ' + cmd_string)
        self.cmd = cmd_string

class AbortError(Exception):
    """Exception to signal aborting the build"""

    def __init__(self, returncode):
        self.returncode = returncode

class ConfigurationError(Exception):
    """Exception to signal errors in the build configuration

    Reason for the error is provided as the exception args."""

class Enum(object):
    """Base class for handling enum values.

    Enumerations can be created with the create() static method,
    providing valid values as arguments.
    """

    @staticmethod
    def create(name, *args, **kwargs):
        """Creates a new enum type.

        The first argument is the name of the created type, and remaining
        string arguments provide the valid values for the enumeration.
        For each value, an upper-cased identifier is created from the value and
        provided as an attribute in the returned class.  If this identifier
        name is not appropriate, the value can be provided as a keyword
        argument, in which case the keyword becomes the identifier.  Example::

            MyEnum = Enum.create('MyEnum', 'value', 'other-value', EXTRA='xyz')

        creates an enum whose values can be accessed as ``MyEnum.VALUE``,
        ``MyEnum.OTHER_VALUE``, and ``MyEnum.EXTRA``, and that provides a
        ``MyEnum.parse()`` method that recognizes the provided strings.

        If a ``doc`` keyword argument is provided, it is used to set the
        docstring for the created type.

        Returns:
            class: Enum subclass that has requested enumeration values as class
                attributes.
        """
        attrs = dict()
        if 'doc' in kwargs:
            attrs['__doc__'] = kwargs['doc']
            del kwargs['doc']
        values = []
        for string in args:
            attr_name = to_python_identifier(string).upper()
            attrs[attr_name] = string
            values.append(attrs[attr_name])
        attrs.update(kwargs)
        values.extend(kwargs.itervalues())
        attrs['_values'] = tuple(values)
        return type(name, (Enum,), attrs)

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

# Currently, the string values should match the result of
# platform.system().lower(), which is used to simplify initialization.
System = Enum.create('System',
    'windows', 'linux', OSX='darwin',
    doc="""Enum to indicate the OS on which the build is running""")

# Currently, the string values should match the names of the repositories
# in Gerrit, so that git URLs and checkout paths can be constructed from
# these.
Project = Enum.create('Project',
    'gromacs', 'regressiontests', 'releng',
    doc="""Enum to identify a git repository/directory used in the build""")

# There is no special significance with these strings.
JobType = Enum.create('JobType',
    'gerrit', 'nightly', 'release',
    doc="""Enum to identify type/scope of the job

           This can be used in the build scripts to, e.g., decide on the
           scope of testing.""")

Compiler = Enum.create('Compiler',
    'gcc', 'clang', 'armclang', 'msvc', INTEL='icc',
    doc="""Enum to identify the compiler used in the build""")

BuildType = Enum.create('BuildType',
    'Debug', 'Reference', 'Optimized', 'Performance', 'ASan', 'TSan',
    doc="""Enum to identify the build type/configuration to use""")

# Currently, these strings should match with the expected values for
# GMX_SIMD.  While not ideal for decoupling the repositories, this
# simplifies the gromacs.py build script significantly.
Simd = Enum.create('Simd',
    'None', 'Reference', 'MIC', 'SSE2', 'SSE4.1',
    'AVX_128_FMA', 'AVX_256', 'AVX2_256',
    'ARM_NEON', 'ARM_NEON_ASIMD',
    doc="""Enum to identify the SIMD instruction set to use""")

# Currently we do not distinguish different hardware capability/generations
# for the same vendor, but we can later add such info here.
Gpuhw = Enum.create('Gpuhw',
    'None', 'amd', 'intel', 'nvidia',
    doc="""Enum to idetify GPU hardware by vendor""")

# There is no special significance with these strings.
FftLibrary = Enum.create('FftLibrary',
    'fftpack', 'fftw3', 'mkl',
    doc="""Enum to identify the FFT library to use""")
