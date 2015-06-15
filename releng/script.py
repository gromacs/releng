"""
Interaction with build scripts.

This module is only used internally within the releng package.
"""

import os.path

from common import BuildError, ConfigurationError
from common import BuildType, Compiler, FftLibrary, JobType, Project, Simd, System

class BuildScript(object):
    """
    Handles build script loading and calls.

    Attributes:
        build_out_of_source (bool): Whether the build should occur
            out-of-source.  If the build script does not specify a value,
            defaults to ``False``.
        extra_projects (List[Project]): Additional projects that the build
            script requires to be checked out (in addition to releng and
            gromacs).  Currently only useful for regression tests.
    """
    def __init__(self, path):
        """Loads build script from a given path.

        Args:
            path (str): Path to the file from which the build script is loaded.
        """
        if not os.path.isfile(path):
            raise ConfigurationError('build script not found: ' + path)
        build_globals = dict()
        # Inject some globals to make the enums and exceptions easily usable in
        # the build script.
        build_globals['BuildError'] = BuildError
        build_globals['BuildType'] = BuildType
        build_globals['Compiler'] = Compiler
        build_globals['FftLibrary'] = FftLibrary
        build_globals['JobType'] = JobType
        build_globals['Project'] = Project
        build_globals['Simd'] = Simd
        build_globals['System'] = System
        # TODO: Capture errors and try to report reasonably
        with open(path, 'r') as f:
            source = f.read()
        code = compile(source, path, 'exec')
        exec(code, build_globals)
        do_build = build_globals.get('do_build', None)
        if do_build is None or not callable(do_build):
            raise ConfigurationError('build script does not define do_build(): ' + path)
        self._do_build = do_build
        self.build_out_of_source = build_globals.get('build_out_of_source', False)
        self.extra_projects = build_globals.get('extra_projects', [])

    def do_build(self, context):
        """Calls do_build() in the build script.

        Args:
            context (BuildContext): Context to pass to the build script.
        """
        self._do_build(context)
