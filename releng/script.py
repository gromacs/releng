"""
Interaction with build scripts.

This module is only used internally within the releng package.
"""

import os.path

from common import BuildError, ConfigurationError
from common import Enum
from common import BuildType, Compiler, FftLibrary, JobType, Project, Simd, Gpuhw, System
from integration import ParameterTypes
from options import OptionTypes
import utils

class BuildScriptSettings(object):
    """
    Stores settings about the releng behavior expected by a build script.

    Attributes:
        build_opts (List[str]): List of build options specified by the script.
            Empty list if not specified in the build script.
        build_out_of_source (bool): Whether the build should occur
            out-of-source.  If the build script does not specify a value,
            defaults to ``False``.
        extra_options (Dict[str, handler]): Options that are defined and
             understood by the build script, but do not affect releng behavior.
        extra_projects (List[Project]): Additional projects that the build
            script requires to be checked out (in addition to releng and
            gromacs).  Currently only useful for regression tests.
        use_stdlib_through_env_vars (bool): Whether to use CFLAGS/CXXFLAGS
            environment variables to set the C++ standard library for
            compilation.
            Defaults to True, which is used by branches prior to GROMACS 2020.
    """
    def __init__(self):
        self.build_opts = []
        self.build_out_of_source = False
        self.extra_options = dict()
        self.extra_projects = []
        self.use_stdlib_through_env_vars = True

    def init_from_script_globals(self, script_globals):
        self.build_opts = script_globals.get('build_options', [])
        self.build_out_of_source = script_globals.get('build_out_of_source', False)
        self.extra_options = script_globals.get('extra_options', dict())
        self.extra_projects = script_globals.get('extra_projects', [])
        self.use_stdlib_through_env_vars = script_globals.get('use_stdlib_through_env_vars', True)

class BuildScript(object):
    """
    Handles build script loading and calls.

    Attributes:
        settings (BuildScriptSettings): Settings expected by this script.
    """
    def __init__(self, executor, path):
        """Loads build script from a given path.

        Args:
            executor (Executor): Executor for reading the build script.
            path (str): Path to the file from which the build script is loaded.
        """
        build_globals = dict()
        # Inject some globals to make the enums and exceptions easily usable in
        # the build script.
        build_globals['BuildError'] = BuildError
        build_globals['Enum'] = Enum
        build_globals['Option'] = OptionTypes
        build_globals['Parameter'] = ParameterTypes

        build_globals['BuildType'] = BuildType
        build_globals['Compiler'] = Compiler
        build_globals['FftLibrary'] = FftLibrary
        build_globals['JobType'] = JobType
        build_globals['Project'] = Project
        build_globals['Simd'] = Simd
        build_globals['Gpuhw'] = Gpuhw
        build_globals['System'] = System
        try:
            source = ''.join(executor.read_file(path))
        except IOError:
            raise ConfigurationError('error reading build script: ' + path)
        # TODO: Capture errors and try to report reasonably
        code = compile(source, path, 'exec')
        exec(code, build_globals)
        do_build = build_globals.get('do_build', None)
        if do_build is None or not callable(do_build):
            raise ConfigurationError('build script does not define do_build(): ' + path)
        self._do_build = do_build
        self.settings = BuildScriptSettings()
        self.settings.init_from_script_globals(build_globals)

    def do_build(self, context, cwd):
        """Calls do_build() in the build script.

        Args:
            context (BuildContext): Context to pass to the build script.
        """
        utils.flush_output()
        cwd.pushd(context.workspace.build_dir)
        self._do_build(context)
        cwd.popd()
