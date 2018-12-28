releng Python API
=================

Build script definition
-----------------------

The build script is required to provide one function:

.. py:function:: do_build(context)

   Called to run the actual build.  The context parameter is an instance of
   BuildContext, and can be used to access the build environment and to
   interact with Jenkins.  The function can signal fatal build errors by
   raising BuildError directly; typically, this is done by methods in
   BuildContext if they fail to execute the requested commands.

   When the function is called, the current working directory is set to the
   build directory (whether the build is in- or out-of-source).

The build script can also set a few global variables to influence the behavior
of the build:

.. py:data:: build_options

   If this list value is set to a non-empty list, then these build options are
   used to initialize the build environment.  Useful for non-matrix builds that
   want to, e.g., specify the compiler to use.

.. py:data:: build_out_of_source

   If this boolean value is set to ``True``, the build will be executed
   out-of-source.  By default, the build will be in-source.

.. py:data:: extra_options

   If this dictionary is set, it declares additional build options that the
   script understands.  This can be used to declare options that only influence
   the build script; releng declares only options that affect the build
   environment or the build host assignment.  Syntax is as follows::

     extra_options = {
         'opt': Option.simple,
         'opt-bool': Option.bool,
         'opt-str': Option.string
     }

   The values of the build options can be read from ``context.opts`` in
   do_build().  See ``OptionTypes`` documentation for the available option
   types: in the build script, ``Option`` is bound to ``OptionTypes``.

   Technically, the value in the dictionary is a callable that gets called
   with the name of the option to create an internal handler class for
   processing the option.

.. py:data:: extra_projects

   If this list value is set to a non-empty list, then these repositories are
   also checked out before executing the build.  ``releng`` and ``gromacs``
   repositories are always checked out.
   Currently, only ``Project.REGRESSIONTESTS`` makes sense to specify here.

When the build script is loaded, various enums from the releng package are
injected into the global scope to make them easy to access.

API for build scripts
---------------------

The build script gets input and perfoms most tasks by using data and methods in
a BuildContext instance:

.. py:currentmodule:: releng.context
.. autoclass:: BuildContext
   :members:

The build context contains attributes of the following classes to access
additional information:

.. py:currentmodule:: releng.environment
.. autoclass:: BuildEnvironment
   :members:

.. py:currentmodule:: releng.options
.. autoclass:: BuildOptions

.. py:currentmodule:: releng.integration
.. autoclass:: BuildParameters

.. py:currentmodule:: releng.workspace
.. autoclass:: Workspace
   :members:

API for Jenkins
---------------

The following functions from the ``releng`` package are intended to be called
from scripts in Jenkins build configuration or from pipeline scripts
(see :doc:`jenkins-config`).

.. py:currentmodule:: releng
.. autofunction:: run_build

.. autofunction:: read_build_script_config

.. autofunction:: prepare_multi_configuration_build

.. autofunction:: get_actions_from_triggering_comment

.. autofunction:: do_ondemand_post_build

.. autofunction:: get_build_revisions

.. autofunction:: read_source_version_info
