"""
Declares a factory class for wiring together all the other releng classes.
"""

import os
import platform

from common import Project, System
from context import BuildContext
from executor import CommandRunner, CurrentDirectoryTracker, Executor
from integration import GerritIntegration, FailureTracker
from workspace import Workspace

class ContextFactory(object):

    """Encapsulates construction of objects related to the build.

    This class provides a single place that is responsible of creating
    instances of different objects needed for creating a BuildContext.
    This makes it simpler to pass custom parameters to the various objects,
    while still providing default logic for constructing them in case the
    custom parameters are not needed.  This class reduces the need to pass
    objects or values needed to construct them through various layers.

    Typically, a Jenkins build will use all the objects with their default
    parameters, but testing (using the routines from __main__.py, or otherwise)
    generally needs to have more control.
    """

    def __init__(self, default_project=Project.GROMACS, system=None, env=None):
        if system is None:
            system = platform.system()
        if system is not None:
            system = System.parse(system)
        if env is None:
            env = dict(os.environ)
        self.system = system
        self.default_project = default_project
        self._env = env
        self._cwd = CurrentDirectoryTracker()
        self._executor = None
        self._cmd_runner = None
        self._failure_tracker = None
        self._gerrit = None
        self._workspace = None

    @property
    def env(self):
        """Returns the environment variables for the build.

        The caller should not modify the returned dictionary.
        """
        return self._env

    @property
    def cwd(self):
        """Returns a CurrentDirectoryTracker instance for the build."""
        return self._cwd

    @property
    def executor(self):
        """Returns an Executor instance for the build."""
        if self._executor is None:
            self.init_executor()
        return self._executor

    @property
    def cmd_runner(self):
        """Returns a CommandRunner instance for this build."""
        if self._cmd_runner is None:
            self._init_cmd_runner()
        return self._cmd_runner

    @property
    def failure_tracker(self):
        """Returns the FailureTracker instance for the build."""
        if self._failure_tracker is None:
            self._init_failure_tracker()
        return self._failure_tracker

    @property
    def gerrit(self):
        """Returns the GerritIntegration instance for the build."""
        if self._gerrit is None:
            self.init_gerrit_integration()
        return self._gerrit

    @property
    def workspace(self):
        """Returns the Workspace instance for the build."""
        if self._workspace is None:
            self.init_workspace()
        return self._workspace

    def init_executor(self, cls=None, instance=None):
        """Sets an executor instance/class to be used.

        If not called, a default instance of Executor is created.
        """
        assert self._executor is None
        if instance is None:
            if cls is None:
                instance = Executor(self)
            else:
                instance = cls(self)
        self._executor = instance

    def _init_cmd_runner(self):
        assert self._cmd_runner is None
        self._cmd_runner = CommandRunner(self)

    def _init_failure_tracker(self):
        assert self._failure_tracker is None
        self._failure_tracker = FailureTracker(self)

    def init_gerrit_integration(self, **kwargs):
        """Initializes GerritIntegration with given parameters.

        If not called, the object will be created with default parameters.
        """
        assert self._gerrit is None
        self._gerrit = GerritIntegration(factory=self, **kwargs)

    def init_workspace(self):
        """Initializes Workspace with given parameters.

        If not called, the object will be created with default parameters.
        """
        assert self._workspace is None
        self._workspace = Workspace(self)

    def create_context(self, *args):
        """Creates a BuildContext with given arguments."""
        return BuildContext(self, *args)
