"""
Handling of Jenkins build options

This module provides a method for processing build options to initialize
the build environment and parameters, and helper classes used by it.
It is is only used internally within the releng package.
"""

import re
import shlex

from common import ConfigurationError
from common import BuildType, FftLibrary, Simd
from environment import BuildEnvironment
from parameters import BuildParameters

class BuildOptions(object):
    """Values for all build options.

    This class provides read-only access to the values of all build options.
    A build option named ``mdrun-only`` is accessible as ``opts.mdrun_only``
    and ``opts['mdrun-only']``, whichever is more convenient.
    The keys for all build options are always available.  If an option is not
    specified, the corresponding value is ``None``.

    For simple flag options that can only be set or unset, the stored value is
    ``True`` if the option is set.

    For boolean options, the stored value is ``False`` or ``True``.  For
    example, ``no-mpi`` and ``mpi=no`` are both stored as ``opts.mpi == True``.

    For options like ``gcc-4.8``, the value is stored as ``opts.gcc == '4.8'``.
    Similarly, ``build-jobs=2`` is stored as ``opts.build_jobs == '2'``.
    """
    def __init__(self, handlers, opts):
        self._opts = dict()
        for handler in handlers:
            name = handler.name
            self._opts[name] = None
            self._set_option(name, None)
        if opts:
            self._process_options(handlers, opts)

    def _set_option(self, name, value):
        assert name in self._opts
        self._opts[name] = value
        self.__dict__[self._option_var_name(name)] = value

    def _option_var_name(self, name):
        return re.sub(r'[^0-9a-zA-Z_]', '_', name)

    def _process_options(self, handlers, opts):
        opts = list(opts)
        for handler in handlers:
            found_opts = [x for x in opts if handler.matches(x)]
            if not handler.allow_multiple and len(found_opts) > 1:
                raise ConfigurationError('conflicting options found: ' + ' '.join(found_opts))
            for found_opt in found_opts:
                opts.remove(found_opt)
                self._handle_option(handler, found_opt)
        if opts:
            raise ConfigurationError('unknown options: ' + ' '.join(opts))

    def _handle_option(self, handler, opt):
        name = handler.name
        value = handler.handle(opt)
        self._set_option(name, value)

    def __getitem__(self, key):
        return self._opts[key]

    def __contains__(self, item):
        return item in self._opts

class OptionTypes(object):
    """Factories for declaring options in build scripts."""

    @staticmethod
    def simple(name):
        """Creates a simple option that stores ``True`` if set."""
        return _SimpleOptionHandler(name)

    @staticmethod
    def bool(name):
        """Creates a boolean option that stores ``True`` or ``False`` if set.

        Accepted syntax is ``[no-]opt[=on/off]``.
        """
        return _BoolOptionHandler(name)

    @staticmethod
    def string(name):
        """Creates an option that stores an arbitrary string value if set.

        Accepted syntax is ``opt=value``.
        """
        return _SuffixOptionHandler(name + '=')

class _OptionHandlerClosure(object):
    """Helper class for providing context for build option handler methods.

    This class provides methods that are used as build option handlers for
    cases that cannot be directly call methods in BuildEnvironment.
    It essentially just captures the environment and parameter objects from
    the scope that creates it, and provides methods that can then be called
    without explicitly passing these objects around to each.
    """

    def __init__(self, env, params):
        self._env = env
        self._params = params

    # Please keep the handlers in the same order as in process_build_options().

    def _init_build_jobs(self, value):
        self._env._build_jobs = int(value)

    def _init_phi(self):
        self._env._init_phi()
        self._params.phi = True

    def _init_mdrun_only(self):
        self._params.mdrun_only = True

    def _init_reference(self):
        self._params.build_type = BuildType.REFERENCE

    def _init_release(self):
        self._params.build_type = BuildType.OPTIMIZED

    def _init_asan(self):
        self._params.build_type = BuildType.ASAN

    def _init_tsan(self):
        self._env._init_tsan()
        self._params.build_type = BuildType.TSAN

    def _init_atlas(self):
        self._env._init_atlas()
        self._params.external_linalg = True

    def _init_mkl(self):
        self._params.fft_library = FftLibrary.MKL
        self._params.external_linalg = True

    def _init_fftpack(self):
        self._params.fft_library = FftLibrary.FFTPACK

    def _init_double(self):
        self._params.double = True

    def _init_x11(self):
        self._params.x11 = True

    def _init_simd(self, simd):
        self._params.simd = Simd.parse(simd)

    def _init_thread_mpi(self, value):
        self._params.thread_mpi = value

    def _init_gpu(self, value):
        self._params.gpu = value

    def _init_mpi(self, value):
        if value:
            self._env._init_mpi(self._params.gpu)
        self._params.mpi = value

    def _init_openmp(self, value):
        self._params.openmp = value

    def _init_valgrind(self):
        self._params.memcheck = True

    def _add_env_var(self, assignment):
        var, value = assignment.split('=', 1)
        self._env.add_env_var(var, value)

    def _add_cmake_option(self, assignment):
        var, value = assignment.split('=', 1)
        self._params.extra_cmake_options[var] = value

    def _add_gmxtest_args(self, args):
        self._params.extra_gmxtest_args.extend(shlex.split(args))

class _BuildOptionHandler(object):
    """Base class for build options.

    Concrete option classes implement matches() and handle() methods to
    identify and handle the option.
    """

    def __init__(self, name, handler=None, allow_multiple=False):
        """Creates a handler for a specified option.

        Args:
            name (str): Name of the option. Exact interpretation depends on the
                subclass.
            handler (function): Handler function to call when the option is set.
                Parameters may be passed to the handler to provide information
                parsed from the option string (e.g., a version number),
                depending on the subclass.
            allow_multiple (bool): If not True, at most one option is allowed
                to match this handler.
        """
        self._name = name
        if handler is None:
            handler = self._null_handler
        self._handler = handler
        self.allow_multiple = allow_multiple

    def _null_handler(self, *args):
        pass

    @property
    def name(self):
        """Name of the option (without any assignment suffixes etc.)."""
        return self._name

    def matches(self, opt):
        """Checks whether this handler handles the provided option.

        If this method returns True, then handle() will be called to process
        the option.

        Args:
            opt (str): Option to match.

        Returns:
            bool: Whether this handler should handle opt.
        """
        return False

    def handle(self, opt):
        """Handles the provided option.

        This method is called for each option for which matches() returns True.
        It calls the handler provided to the constructor, possibly after
        parsing information from the option name.

        Args:
            opt (str): Option to process.
        """
        return None

class _SimpleOptionHandler(_BuildOptionHandler):
    """Handler for a simple flag option.

    This is provided for cases where the option just turns on or selects a
    specific feature and the negation would not make much sense, and so
    _BoolOptionHandler would not be appropriate.

    The handler provided to the constructor is called without parameters.
    """

    def matches(self, opt):
        return opt == self._name

    def handle(self, opt):
        self._handler()
        return True

class _SuffixOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt-VALUE'.

    The handler provided to the constructor is called with a single string
    parameter that provides VALUE.
    """

    @property
    def name(self):
        return self._name[:-1]

    def matches(self, opt):
        return opt.startswith(self._name)

    def handle(self, opt):
        suffix = opt[len(self._name):]
        self._handler(suffix)
        return suffix

class _VersionOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt-X[.Y]*'.

    The handler provided to the constructor is called with a single string
    parameter that provides the version number.
    """

    def matches(self, opt):
        return bool(re.match(self._name + r'-\d+(\.\d+)*$', opt))

    def handle(self, opt):
        suffix = opt[len(self._name)+1:]
        self._handler(suffix)
        return suffix

class _BoolOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax '[no-]opt[=on/off]'.

    The handler provided to the constructor is called with a single boolean
    parameter that identifies whether the option is on or off.
    """

    def matches(self, opt):
        return opt in (self._name, 'no-' + self._name) \
                or opt.startswith(self._name + '=')

    def handle(self, opt):
        value = self._parse(opt)
        self._handler(value)
        return value

    def _parse(self, opt):
        if opt == self._name:
            return True
        if opt == 'no-' + self._name:
            return False
        if opt.startswith(self._name + '='):
            value = opt[len(self._name)+1:].lower()
            if value in ('1', 'on', 'true'):
                return True
            if value in ('0', 'off', 'false'):
                return False
        raise ConfigurationError('invalid build option: ' + opt)

def process_build_options(factory, opts, extra_options):
    """Initializes build environment and parameters from OS and build options.

    Creates the environment and parameters objects, and adjusts them
    based on the provided options.

    Args:
        factory (ContextFactory): Factory to access other objects.
        opts (List[str]): List of build options.
        extra_options (Dict[str, function]): Extra build options to accept.

    Returns:
        Tuple[BuildEnvironment, BuildParameters]: Build environment and
            parameters initialized according to the options.
    """
    e = BuildEnvironment(factory)
    p = BuildParameters()
    h = _OptionHandlerClosure(e, p)
    # The options are processed in the order they are in the tuple, to support
    # cross-dependencies between the options (there are a few).
    # If you add options here, please also update the documentation for the
    # options in docs/releng.rst.
    handlers = [
            _SuffixOptionHandler('build-jobs=', h._init_build_jobs),
            _VersionOptionHandler('cmake', e._init_cmake),
            _VersionOptionHandler('gcc', e.init_gcc),
            _VersionOptionHandler('clang', e.init_clang),
            _SimpleOptionHandler('clang-analyzer', e.init_clang_analyzer),
            _VersionOptionHandler('icc', e._init_icc),
            _VersionOptionHandler('msvc', e._init_msvc),
            _VersionOptionHandler('cuda', e._init_cuda),
            _SimpleOptionHandler('phi', h._init_phi),
            _SimpleOptionHandler('mdrun-only', h._init_mdrun_only),
            _SimpleOptionHandler('reference', h._init_reference),
            _SimpleOptionHandler('release', h._init_release),
            _SimpleOptionHandler('asan', h._init_asan),
            _SimpleOptionHandler('tsan', h._init_tsan),
            _SimpleOptionHandler('atlas', h._init_atlas),
            _SimpleOptionHandler('mkl', h._init_mkl),
            _SimpleOptionHandler('fftpack', h._init_fftpack),
            _SimpleOptionHandler('double', h._init_double),
            _SimpleOptionHandler('x11', h._init_x11),
            _SuffixOptionHandler('simd=', h._init_simd),
            _BoolOptionHandler('thread-mpi', h._init_thread_mpi),
            _BoolOptionHandler('gpu', h._init_gpu),
            _BoolOptionHandler('mpi', h._init_mpi),
            _BoolOptionHandler('openmp', h._init_openmp),
            _SimpleOptionHandler('valgrind', h._init_valgrind),
            _SuffixOptionHandler('env+', h._add_env_var, allow_multiple=True),
            _SuffixOptionHandler('cmake+', h._add_cmake_option, allow_multiple=True),
            _SuffixOptionHandler('gmxtest+', h._add_gmxtest_args, allow_multiple=True),
        ]
    if extra_options:
        for name, builder in extra_options.iteritems():
            new_handler = builder(name)
            existing_handlers = [x for x in handlers if x.name == name]
            assert len(existing_handlers) <= 1
            if existing_handlers:
                if type(new_handler) != type(existing_handlers[0]):
                    raise ConfigurationError('Option {0} redeclared with a different type'.format(name))
                continue
            handlers.append(new_handler)
    o = BuildOptions(handlers, opts)
    return (e, p, o)
