"""
Handling of Jenkins build options

This module provides a method for processing build options to initialize
the build environment and options, and helper classes used by it.
BuildOptions and OptionTypes are exposed to build scripts, but other
code is internal to releng.
"""

import re
import shlex

from common import to_python_identifier
from common import ConfigurationError
from common import BuildType, FftLibrary, Simd, Gpuhw
from environment import BuildEnvironment
import agents

class BuildConfig(object):
    def __init__(self, opts):
        self.opts = opts
        self.host = None
        self.labels = None

    def to_dict(self):
        return {
                'opts': self.opts,
                'host': self.host,
                'labels': ' && '.join(sorted(self.labels))
            }

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
        self.__dict__[to_python_identifier(name)] = value

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
        value = handler.parse(opt)
        self._set_option(handler.name, value)
        handler.handle(value)

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
        return _StringOptionHandler(name)

    @staticmethod
    def enum(enum):
        """Creates an option that an enum value if set.

        Accepted syntax is ``opt=value``, with allowed values specified by
        the enum passed in.
        """
        return lambda name: _EnumOptionHandler(name, enum)


# Indicates that an option requires a label of the same name as the option.
OPT = lambda opt, value: opt

class _BuildOptionHandler(object):
    """Base class for build options.

    Concrete option classes implement matches() and parse() to identify and
    parse the option, and potentially override handle() and label() to
    customize the logic for processing the option.
    """

    def __init__(self, name, handler=None, label=None, allow_multiple=False):
        """Creates a handler for a specified option.

        Args:
            name (str): Name of the option.
            handler (function): Handler function to call when the option is set.
                Parameters may be passed to the handler to provide information
                parsed from the option string (e.g., a version number),
                depending on the subclass.  If None, only the value is stored
                in BuildOptions.
            label (function): Determines label that the host is required to
                have to build with this option.  Called with two parameters:
                full string of the option, and the option value parsed from it.
                Can be set to OPT to require a label with the same name as the
                option.  If None, this option does not restrict the build host.
            allow_multiple (bool): If not True, at most one option is allowed
                to match this handler.
        """
        self.name = name
        if handler is None:
            handler = self._null_handler
        if label is None:
            label = self._null_handler
        self._handler = handler
        self._label = label
        self.allow_multiple = allow_multiple

    def _null_handler(self, *args):
        """Dummy handler to avoid null checks in callers."""
        pass

    def matches(self, opt):
        """Checks whether this handler handles the provided option.

        If this method returns True, then parse() will be called to process
        the option.

        Args:
            opt (str): Option to match.

        Returns:
            bool: Whether this handler should handle opt.
        """
        return False

    def parse(self, opt):
        """Parses the option value from option string.

        This method is called for each option for which matches() returns True.

        Args:
            opt (str): Option to parse.

        Returns:
            variable: Value for this option.
        """
        return None

    def handle(self, value):
        """Handles the provided option.

        This method may be called after parse() to perform any build
        environment effects that the option should have.
        It calls the handler provided to the constructor.

        Args:
            value: Value of the option returned by parse().
        """
        self._handler(value)

    def label(self, opt, value):
        """Handles the provided option.

        This method may be called after parse() to determine which hosts can
        build with this option.
        It calls the label handler provided to the constructor.

        Args:
            opt (str): Original option string.
            value (variable): Value of the option returned by parse().

        Returns:
            str or None: Label required from the build host.
        """
        return self._label(opt, value)

class _SimpleOptionHandler(_BuildOptionHandler):
    """Handler for a simple flag option.

    This is provided for cases where the option just turns on or selects a
    specific feature and the negation would not make much sense, and so
    _BoolOptionHandler would not be appropriate.

    The value of the option will always be ``True``.
    """

    def matches(self, opt):
        return opt == self.name

    def parse(self, opt):
        return True

    def handle(self, value):
        self._handler()

class _StringOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt=VALUE'.

    The value of the option will be VALUE (a string).
    """

    def matches(self, opt):
        return opt.startswith(self.name + '=')

    def parse(self, opt):
        return opt[len(self.name)+1:]

class _IntOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt=VALUE'.

    The value of the option will be VALUE (an integer).
    """

    def matches(self, opt):
        return opt.startswith(self.name + '=')

    def parse(self, opt):
        return int(opt[len(self.name)+1:])

class _EnumOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt=VALUE' with enumerated values.

    The value of the option will be VALUE (an enum of type passed to constructor).
    """

    def __init__(self, name, enum, *args, **kwargs):
        _BuildOptionHandler.__init__(self, name, *args, **kwargs)
        self._enum = enum

    def matches(self, opt):
        return opt.startswith(self.name + '=')

    def parse(self, opt):
        return self._enum.parse(opt[len(self.name)+1:])

class _VersionOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax 'opt-X[.Y]*'.

    The value of the option will be the version number (a string).
    """

    def matches(self, opt):
        return bool(re.match(self.name + r'-\d+(\.\d+)*$', opt))

    def parse(self, opt):
        return opt[len(self.name)+1:]

class _BoolOptionHandler(_BuildOptionHandler):
    """Handler for an option with syntax '[no-]opt[=on/off]'.

    The value of the option will be ``True`` or ``False``.
    """

    def matches(self, opt):
        return opt in (self.name, 'no-' + self.name) \
                or opt.startswith(self.name + '=')

    def parse(self, opt):
        if opt == self.name:
            return True
        if opt == 'no-' + self.name:
            return False
        if opt.startswith(self.name + '='):
            value = opt[len(self.name)+1:].lower()
            if value in ('1', 'on', 'true'):
                return True
            if value in ('0', 'off', 'false'):
                return False
        raise ConfigurationError('invalid build option: ' + opt)

    def label(self, opt, value):
        if not value:
            return None
        return self._label(opt, value)

def simd_label(opt, value):
    """Determines the host label needed for selected SIMD option."""
    if value in (Simd.NONE, Simd.REFERENCE):
        return None
    return str(value).lower()

def gpuhw_label(opt, value):
    """Determines the host label needed for selected GPU hardware option."""
    if value in (Gpuhw.NONE,):
        return None
    return str(value).lower()

def _define_handlers(e, extra_options):
    """Defines the list of recognized build options."""
    # The options are processed in the order they are in the tuple, to support
    # cross-dependencies between the options (there are a few).
    # If you add options here, please also update the documentation for the
    # options in docs/releng.rst.
    # Labels need to be specified for options that require specific features
    # from the build host (e.g., required software versions or special
    # hardware support).  They need to match with the labels defined in
    # agents.py.
    handlers = [
            _IntOptionHandler('build-jobs', e._set_build_jobs),
            _SimpleOptionHandler('out-of-source'),
            _VersionOptionHandler('cmake', e._init_cmake, label=OPT),
            _VersionOptionHandler('gcc', e._init_gcc, label=OPT),
            _VersionOptionHandler('gcov', label=OPT),
            _VersionOptionHandler('armclang', e._init_armclang, label=OPT),
            _VersionOptionHandler('clang', e._init_clang, label=OPT),
            _VersionOptionHandler('libcxx', e._init_libcxx, label=OPT),
            _VersionOptionHandler('clang-static-analyzer', e._init_clang_static_analyzer, label=OPT),
            _VersionOptionHandler('msvc', e._init_msvc, label=OPT),
            _VersionOptionHandler('icc', e._init_icc, label=OPT),
            _VersionOptionHandler('cuda', e._init_cuda, label=OPT),
            _VersionOptionHandler('amdappsdk', e._init_amdappsdk, label=OPT), # TODO: remove
            _VersionOptionHandler('clFFT', e._init_clFFT, label=OPT),
            _VersionOptionHandler('armhpc', e._init_armhpc, label=OPT),
            _SimpleOptionHandler('phi', e._init_phi, label=OPT),
            _SimpleOptionHandler('tsan', label=OPT),
            _SimpleOptionHandler('atlas', e._init_atlas),
            _SimpleOptionHandler('x11', label=OPT),
            _EnumOptionHandler('simd', Simd, label=simd_label),
            _EnumOptionHandler('gpuhw', Gpuhw, label=gpuhw_label),
            _SimpleOptionHandler('mpi', e._init_mpi, label=OPT),
            _SimpleOptionHandler('armpl', e._init_armpl, label=OPT),
            _SimpleOptionHandler('tidy', label=OPT)
        ]
    if extra_options and "opencl" in extra_options:
        # This build is running an old script where opencl was a bool,
        # so we handle it like that using a handler that will set the
        # version to a suitable value.
        #
        # TODO Remove this when legacy matrices are no longer supported
        handlers.append(_BoolOptionHandler('opencl', e._init_opencl_legacy, label=OPT))
    else:
        # TODO Once the legacy matrices are no longer supported, move
        # this handler into the initialization of handlers above.
        handlers.append(_VersionOptionHandler('opencl', e._init_opencl, label=OPT))

    if extra_options:
        for name, builder in extra_options.iteritems():
            new_handler = builder(name)
            existing_handlers = [x for x in handlers if x.name == name]
            assert len(existing_handlers) <= 1
            if existing_handlers:
                if type(new_handler) != type(existing_handlers[0]):
                    raise ConfigurationError('Option {} redeclared with a different type'.format(name))
                continue
            handlers.append(new_handler)
    return handlers

def process_build_options(factory, opts, extra_options):
    """Initializes build environment and parameters from OS and build options.

    Creates the environment and options objects, and adjusts them
    based on the provided options.

    Args:
        factory (ContextFactory): Factory to access other objects.
        opts (List[str]): List of build options.
        extra_options (Dict[str, function]): Extra build options to accept.

    Returns:
        Tuple[BuildEnvironment, BuildParameters, BuildOptions]: Build
            environment and options initialized from the options.
    """
    e = BuildEnvironment(factory)
    handlers = _define_handlers(e, extra_options)
    if opts:
        opts = _remove_host_option(opts)
    o = BuildOptions(handlers, opts)
    return (e, o)

def _remove_host_option(opts):
    """Removes options that specify the execution host."""
    return list(filter(lambda x: not x.lower().startswith(('host=', 'label=')), opts))

def select_build_hosts(factory, configs):
    """Selects build host for each configuration.

    Args:
        factory (ContextFactory): Factory to access other objects.
        List[MatrixConfig]: List of build options for each configuration.

    Returns:
        List[MatrixConfig]: The input configurations with ``host=`` or ``label=``
            option added/replaced.
    """
    e = BuildEnvironment(factory)
    handlers = _define_handlers(e, None)
    result = []
    for config in configs:
        config.opts = _remove_host_option(config.opts)
        opts = config.opts
        labels = set()
        for handler in handlers:
            found_opts = [x for x in opts if handler.matches(x)]
            for found_opt in found_opts:
                value = handler.parse(found_opt)
                label = handler.label(found_opt, value)
                if label:
                    labels.add(label)
        config.labels = list(labels)
        config.host = agents.pick_host(labels, config.opts)
        result.append(config)
    return result
