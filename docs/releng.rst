releng (Jenkins) scripts
========================

.. Formatting, cross-references, exact syntax for autodoc and similar techical
   details can be sorted out once this documentation actually gets included
   somewhere (not in the initial change).

Scripts used for Jenkins builds reside in a separate ``releng`` repository.

.. TODO: Some more introductory text.

Build overview
--------------

Builds using the releng scripts use the following sequence:

1. Jenkins does some preparatory steps (see :ref:`releng-jenkins-config`),
   including checking out the ``releng`` repo.
2. Jenkins imports the releng Python package, and calls run_build().
3. The releng script checks out the ``gromacs`` repo if not yet done by
   Jenkins.
4. The releng script locates a Python build script from the ``gromacs`` repo
   based on the build type given to run_build(), and loads the code.
   The build script provides some configuration settings as global variables, and
   a do_build() function that provides the actual build steps.
5. If the build script requires regression tests, the releng script now checks
   out the ``regressiontests`` repo.
6. The releng script prepares the build environment, such as initializing
   environment variables and generic CMake options such as the used compilers.
   The build environment can be influenced by build options passed to
   run_build().  Some build options passed to run_build() only set parameters
   that the build script can access to influence how to do the build (not all
   build scripts use these parameters).
   See :ref:`releng-jenkins-build-opts` for details on the supported build
   options.
   This step also includes setting up a separate build directory for
   out-of-source builds if so requested by the build script.
7. The releng script calls do_build() provided by the build script.
   do_build() receives a build context that it can use to access information
   about the build environment, build parameters, and the workspace.
   The context also provides methods to run CMake, to build targets, to copy
   logs to a common location in the workspace, to mark the build unstable, and
   other such helper functions to help interacting with Jenkins in an uniform
   manner.
   See :ref:`releng-jenkins-build-script` for details on the API available to
   the build script.
8. The build script provides the steps to do the actual build, typically
   calling methods in the build context to interact with the CMake build system
   or Jenkins where required.
9. When the build script returns, or raises a BuildError exception to indicate
   a build failure, the releng script does some final processing to handle
   reason reporting for unsuccessful (unstable or failed) builds.
10. Jenkins does various post-build actions, such as publishing or parsing logs
    from the common log location, and using the unsuccessful reason reported
    from the script as the failure message to report back to Gerrit.

.. _releng-jenkins-build-opts:

Build options
-------------

Currently, the following build options can be passed from Jenkins to
run_build() to influence the build environment.  These are typically used for
multi-configuration jobs; for jobs that only build a single configuration, the
configuration is typically hard-coded in the build script.  For boolean options,
multiple formats are accepted.  E.g., an OpenMP build can be specified as
``openmp`` or ``openmp=yes``, and no-OpenMP as ``no-openmp`` or ``openmp=no``.
The defaults that are used if a particular option is not specified are
determined by the build script.

build-jobs=N
  Use the specified number of parallel jobs for building.
cmake-X.Y.Z
  Use the specified CMake version to generate the build system.
gcc-X.Y
  Use the specified gcc version as the compiler.
clang-X.Y
  Use the specified clang version as the compiler.
icc-X.Y
  Use Intel compiler (version is currently ignored; it is for informational
  purposes only and should match whatever is installed on the build nodes).
msvc-YYYY
  Use the specified MSVC version as the compiler.
cuda-X.Y
  Use the specified CUDA version (only has effect in combination with ``gpu``).
phi
  Build for Xeon Phi.
mdrun-only
  Do an mdrun-only build.
reference
  Do a reference (``CMAKE_BUILD_TYPE=Reference``) build.
release
  Do a release (optimized) build.
asan
  Use address sanitizer for the build.
tsan
  Use thread sanitizer for the build.
atlas
  Use ATLAS as an external BLAS/LAPACK library.
mkl
  Use MKL as FFT and BLAS/LAPACK libraries.
fftpack
  Use FFTPACK as the FFT library.
double
  Do a double-precision build.
x11
  Build also ``gmx view`` (i.e., use ``GMX_X11=ON``).
simd=SIMD
  Use the specified SIMD instruction set.
  If not set, SIMD is not used.
no-thread-mpi
  Build without thread-MPI.
mpi
  Do an MPI build.
gpu
  Do a GPU-enabled build.
openmp[=on/off]
  Do a build with/without OpenMP.
valgrind
  Use valgrind for running (some of the) tests.

Additionally, the following options can be used to pass raw environment
variables and arguments to CMake and ``gmxtest.pl``.  These are included to
support quick testing of different setups, but as soon as things stabilize, a
proper build option should be added.  In particular when used to pass
|Gromacs|-specific options to CMake, these create unwanted coupling between
Jenkins and the build system, making it impossible for people without admin
access to Jenkins to change anything that is influenced by these options.

env+VAR=VALUE
  Set environment variable ``VAR`` to ``VALUE``.
cmake+VAR=VALUE
  Set CMake variable ``VAR`` to ``VALUE``.
gmxtest+ARGS
  Pass ``ARGS`` as command-line arguments to gmxtest.pl.  ``ARGS`` can contain
  whitespace, which separates options (in such a case, it needs to be quoted).
  Quotes within ``ARGS`` are also allowed to pass arguments that contain
  whitespace.

.. _releng-jenkins-build-script:

Build script API
----------------

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

.. py:data:: build_out_of_source

   If this boolean value is set to ``True``, the build will be executed
   out-of-source.  By default, the build will be in-source.

.. py:data:: extra_projects

   If this list value is set to a non-empty list, then these repositories are
   also checked out before executing the build.  ``releng`` and ``gromacs``
   repositories are always checked out.
   Currently, only ``Project.REGRESSIONTESTS`` makes sense to specify here.

When the build script is loaded, various enums from the releng package are
injected into the global scope to make them easy to access.

The build script gets input and perfoms most tasks by using data and methods in
a BuildContext instance:

.. autoclass:: BuildContext
   :members:

The build context contains attributes of the following classes to access
additional information:

.. autoclass:: BuildEnvironment
   :members:

.. autoclass:: BuildParameters
   :members:

.. autoclass:: Workspace
   :members:

.. _releng-jenkins-config:

Jenkins project configuration
-----------------------------

Configuration for Jenkins projects that use the releng scripts are described here.

SCM checkout configuration and related environment variables:

* Jenkins SCM configuration is used to check out the repository from where the
  build is triggered as a subdirectory of the workspace, with the same name as
  the repository.  This is necessary for the Git Plugin to show reasonable
  change lists for the builds etc., although the build in reality always starts
  from the releng repository.
* The build script will then check out the :file:`releng` repository if it did
  not trigger the build, and start the build from there.
* The releng script will check out remaining repositories if necessary.
* The refspecs for repositories that did not cause the build to trigger should
  be specified in ``GROMACS_REFSPEC``, ``REGRESSIONTESTS_REFSPEC``, and
  ``RELENG_REFSPEC`` environment variables, respectively (whether regression
  tests will actually be checked out is determined by the build script; see
  below).
* The project that triggers the build (and the refspec) should be specified in
  ``CHECKOUT_PROJECT`` and ``CHECKOUT_REFSPEC`` environment variables (for
  simplicity, it is also posisble to use ``GERRIT_PROJECT`` and
  ``GERRIT_REFSPEC``).

To create a build that allows both intuitive parameterized builds with given
refspecs and Gerrit Trigger builds, the following configuration is recommended:

* Use ``GROMACS_REFSPEC``, ``RELENG_REFSPEC``, and ``REGRESSIONTESTS_REFSPEC``
  as build parameters.
* Use "Prepare environment for the run" and the following Groovy script::

    if (!binding.variables.containsKey('GERRIT_PROJECT')) {
      return [CHECKOUT_PROJECT: 'gromacs', CHECKOUT_REFSPEC: GROMACS_REFSPEC]
    } else {
      return [CHECKOUT_PROJECT: GERRIT_PROJECT, CHECKOUT_REFSPEC: GERRIT_REFSPEC]
    }

* Configure all SCM checkout behaviors to use ``CHECKOUT_PROJECT`` and
  ``CHECKOUT_REFSPEC``.

.. TODO: Describe configuration for SCM pull jobs (it should straightforwardly
   follow from the above).

Post-build steps:

* The job should check the console output for the string "FAILED" and mark the
  build unstable if this is found.
* The job should use :file:`logs/unsuccessful-reason.log` as the "Unsuccessful
  Message File" for the Gerrit Trigger plugin.
  TODO: How to best handle this for matrix builds (or other types of
  multi-configuration builds)
* The job should archive all :file:`.log` files from :file:`logs/`.  Note that
  the build should be configured not to fail if there is nothing to archive if
  all the logs are conditionally produced.
* The job can check various log files under :file:`logs/{category}/` for
  warnings; the general design is that all logs from a certain category are
  checked using the same warning parser.

The build script in Jenkins will look something like this::

  import os
  import shlex
  import subprocess
  import sys

  # For builds not triggered by Gerrit Trigger, the conditional is not
  # necessary.
  if os.environ['CHECKOUT_PROJECT'] != 'releng':
      if not os.path.isdir('releng'):
          os.makedirs('releng')
      os.chdir('releng')
      subprocess.check_call(['git', 'init'])
      subprocess.check_call(['git', 'fetch', 'ssh://jenkins@gerrit.gromacs.org/releng.git', os.environ['RELENG_REFSPEC']])
      subprocess.check_call(['git', 'checkout', '-qf', 'FETCH_HEAD'])
      subprocess.check_call(['git', 'clean', '-ffdxq'])
      subprocess.check_call(['git', 'gc'])
      os.chdir('..')

  sys.path.append(os.path.abspath('releng'))
  import releng

  # For non-matrix builds, opts can be a hard-coded list (or possibly None).
  opts = shlex.split(os.environ['OPTIONS'])
  opts = filter(lambda x: not x.lower().startswith('host='), opts)
  releng.run_build('gromacs', releng.JobType.GERRIT, opts)

The script checks out the :file:`releng` repository to a :file:`releng/`
subdirectory of the workspace if not already checked out, imports the
:file:`releng` package and runs run_build() with arguments identifying which
build script to run, and options that affect how the build is done.
``shlex.split()`` is necessary to be able to pass quoted arguments with spaces
to options such as ``gmxtest+``.

run_build() will first check out the :file:`gromacs` repository to a
:file:`gromacs/` subdirectory of the workspace, and then execute a script from
:file:`gromacs/admin/builds/`, selected based on the first argument.
If necessary, it will also check out the regression tests.
If the script exits with a non-zero exit code, the build fails.

The folder structure in the build workspace looks like this::

  $WORKSPACE/
    releng/
    gromacs/
    [regressiontests/]
    logs/
      [unsuccessful-reason.log]
      [<category>/]*

Build system changes
--------------------

This section collects information on how different types of changes to the
|Gromacs| CMake build system, the releng scripts, and/or Jenkins configuration
are handled to keep the CI builds working.  Critical part in these changes is
to try to keep builds working for older changes still pending review in Gerrit.
However, the flipside is that if rebases are not forced, some problems may slip
past if some older change is not compatible with the new CI builds.

Different cases for changes are below.  The distinction may not always be
clear-cut, but the general approach should be well covered.

1. *Compatible change in main repo, no change in releng.*
   In this case, all changes are absorbed in the build script in the main repo.
   Old changes will build with the old build script, new changes with the new,
   and all builds will pass.
   Old changes do not trigger the new functionality, so if the new build script
   contains new tests or such, they may get silently broken by old changes if
   they are not rebased (in this respect, the case is similar to the third item
   below).

   An example of this type of change is reorganization or renaming of CMake
   cache variables or build targets, while still keeping the same or similar
   functionality.  Some types of tests can also be added with this approach.

2. *Compatible change in releng, no change in main repo.*
   In this case, all changes are absorbed in the releng script.  As soon as the
   releng change is merged, both old and new changes will build with the
   changed script, and all builds will pass.

   An example of this type of change is software updates or node
   reconfiguration in Jenkins that affects, e.g., paths to certain programs.
   Also many bug fixes to the releng scripts fall here.

3. *Breaking change in main repo, backwards-compatible change in releng.*
   In this case, changes in the main repo build scripts require changes in
   releng that do not break old builds.  The main repo change will not build
   until releng changes are merged; the releng change can be merged safely
   without breaking old builds.  To verify the releng change with its
   corresponding main repo change, the releng change can be uploaded to Gerrit
   with a suitable ``_OVERRIDES`` specified in :file:`workspace.py`.  This will
   build the combination and report the result in the releng change, allowing
   full integration testing and showing that the build passes.  Care should
   be taken to not merge a change with ``_OVERRIDES`` specified, but if it
   slips past, it will only affect future changes pushed to ``releng``, not any
   builds for the other repositories.
   After the releng change is merged, the main change build can be triggered
   and it will pass.

   Builds for old changes will continue to work throughout this process, but
   they will ignore possible new build parameters or such, potentially breaking
   the new change.

   An example of this type of change would be additional methods or parameters
   required in releng to be able to implement new build tasks.

4. *Breaking change in releng, compatible change in main repo.*
   In this case, changes or additional build configurations in the releng
   and/or Jenkins cause old builds to break.  As soon as the changes in releng
   are merged, all old changes in Gerrit need to be rebased.

   An example of this type of change would be introduction of a new build
   parameter that does not compile cleanly without a corresponding change in
   the main repo (e.g., introduction of a new compiler version that produces
   warnings).

   There is currently no special mechanism for this case.  Older builds in
   Gerrit will fail in unpredictable ways.

.. TODO: Identify possible cases that do not fall into any of the above
   categories, and/or that are distinct enough from the examples above to be
   worth mentioning.

.. TODO: Do we need some mechanism to detect rebasing needs for some of the
   above, and, e.g., have this indicated in the build failure message (or skip
   the build or something similar)?

Testing releng scripts
----------------------

Currently, the only way to fully test the releng script is to upload a change
to Gerrit and let Jenkins build it.  In principle, it is possible to run the
script in an environment that exactly matches a Jenkins node (including paths
to all required tools and all relevant environment variables that Jenkins
sets), but that can be tedious to set up.  The ``releng`` package can be
executed from the command-line using ::

    python releng <options>

and using the ``--dry-run`` option it may be possible to test some of the
build scripts and the releng code without actually having the environment.
But full support for this would require substantial refactoring in the way the
build environment, the workspace, and command execution is managed.
