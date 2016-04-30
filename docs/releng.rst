Jenkins scripts (releng Python module)
======================================

The main scripts used for Jenkins build are collected into a ``releng`` Python
package in the ``releng`` repository.

.. TODO: Some more introductory text.

Build overview
--------------

Python build script
^^^^^^^^^^^^^^^^^^^

Builds using the releng Python scripts use the following sequence:

1. Jenkins (or the workflow script) does some preparatory steps (see
   :doc:`jenkins-config`), including checking out the ``releng`` repo.
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
   See :doc:`releng-api` for details on the API available to the build script.
8. The build script provides the steps to do the actual build, typically
   calling methods in the build context to interact with the CMake build system
   or Jenkins where required.
9. When the build script returns, or raises a BuildError exception to indicate
   a build failure, the releng script does some final processing to handle
   reason reporting for unsuccessful (unstable or failed) builds.
10. Jenkins does various post-build actions, such as publishing or parsing logs
    from the common log location, and using the unsuccessful reason reported
    from the script as the failure message to report back to Gerrit.

Workflow builds
^^^^^^^^^^^^^^^

The subdirectory :file:`workflow/` contains Groovy scripts for use with the
Jenkins Pipeline plugin.  The general sequence for these builds is as follows:

1. Jenkins allocates a node for loading the Groovy script.
2. Jenkins checks out the ``releng`` repo using a shell script.
   We do not use an SCM step here to avoid showing this checkout on the build
   summary page.  The summary page only works reasonably with at most one Git
   checkout within the workflow, and the workflow script should be in control
   of what this checkout is.
3. Jenkins loads the desired workflow script.
4. Typically, the workflow script further loads ``utils.groovy`` as its first
   statement. Any other statements at the top level of the workflow script are
   also executed in the context of the node/workspace where the script is being
   loaded.
   The workflow script should do a ``return this`` as its last statement.
5. Depending on the workflow script, Jenkins may also call other functions
   defined in the workflow script in this node/workspace context.  This is
   necessary if some values need to be passed from Jenkins configuration to the
   workflow script for code that runs in this context.
6. Jenkins calls ``doBuild()`` defined by the workflow script outside of any
   node/workspace context.  Depending on the workflow script, some parameters
   may be passed.
7. The workflow script has full control over the build from now on, until the
   end.

See :doc:`jenkins-config` for more details on the configuration.

See :doc:`workflow` for more details on what kinds of builds the workflow
scripts are currently used for.

Matrix builds
^^^^^^^^^^^^^

The releng scripts also support creating Jenkins matrix builds that load
the configuration matrix from the ``gromacs`` repository.  These files are
located under :file:`admin/builds/`.  The format of such matrix files is one
configuration per line.  Empty lines are ignored, and comments can be started
with ``#``.

The build host assignment happens through a set of labels: build options that affect
the possible host for building the configuration map to labels (the mapping is
defined in :file:`options.py`), and the set of labels supported by each build
slave is defined in :file:`slaves.py`.

The building is orchestrated by a workflow build that loads and preprocesses
the configuration matrix, and then triggers a matrix build that takes the
configuration axis values as a build parameter.  The matrix build uses the
standard sequence with releng Python scripts.

See :doc:`workflow` and :doc:`jenkins-config` for more details.

.. _releng-input-env-vars:

Input environment variables
---------------------------

The following environment variables are used by the releng scripts for input
from the Jenkins job (or from a workflow build script):

``GROMACS_REFSPEC`` ``REGRESSIONTESTS_REFSPEC`` ``RELENG_REFSPEC``
  Refspecs for the repositories used for fetching the change to build.
  Note that they will not always be used for an actual checkout; for example,
  Jenkins always needs to do the checkout for ``releng``.
``GROMACS_HASH`` ``REGRESSIONTESTS_HASH`` ``RELENG_HASH``
  If set, these provide hashes to check out, corresponding to the refspecs.
  Thees can be used to build a fixed commit from a refspec such as
  ``refs/heads/master``, even if multiple checkouts are done at different
  times.  It is assumed that fetching the corresponding refspec will make the
  commit with the provided hash available.
``CHECKOUT_PROJECT``
  Needs to be set to the project (``gromacs``, ``regressiontests``, or
  ``releng``) that Jenkins has checked out.  Needs to be set, unless
  ``GERRIT_PROJECT`` is set.
``CHECKOUT_REFSPEC``
  Refspec used to checkout ``CHECKOUT_PROJECT``.  This will override the
  project-specific refspec for that project.
``GERRIT_PROJECT`` ``GERRIT_REFSPEC``
  These are set by Gerrit Trigger, and can be used for simplicity instead of
  ``CHECKOUT_PROJECT`` and ``CHECKOUT_REFSPEC``.
``NODE_NAME``
  Name of the host where the build is running.  This is used for some
  host-specific logic in configuring the compilation.
  This is set by Jenkins automatically.
``WORKSPACE``
  Path to the root of the Jenkins workspace where the build is running.
  This is set by Jenkins automatically, except for workflow builds.
``STATUS_FILE``
  Path to the file to write on completion of the build, containing the build
  status and the reason for failed builds.
  Defaults to :file:`logs/unsuccessful-reason.log`.
  If the extension is :file:`.json`, the file is written as JSON, which is
  useful for further use from a workflow build.
``NO_PROPAGATE_FAILURE``
  If set to a non-empty value, the build script will exit with a zero exit code
  even if the build fails because of a BuildError or ConfigurationError.
  Only unexpected exceptions will cause a non-zero exit code.
  The information in ``STATUS_FILE`` can be used to determine whether the build
  failed or not.

Output
------

To communicate back to the Jenkins job (or the workflow build script), the
releng scripts use the following mechanisms:

exit code
  The script exits with a non-zero exit code if the build fails, unless
  ``NO_PROPAGATE_FAILURE`` is set.  If it is set, only an unexpected exception
  will cause a non-zero exit code.
status file
  A file that contains the build result is written to ``STATUS_FILE`` (or to
  :file:`logs/unsuccessful-reason.log` if none is specified).
  A reasonable effort is done to try to delete this file at the start of the
  script, so that old versions would not be left if the script fails.
  Even on unexpected errors, a reasonable effort is made to produce the file
  and include the exception information in it.
  If producing this file fails, it is treated as an unexpected error.
console outout
  If the build is unstable, it also ensures that the word ``FAILED`` appears in
  the console log.  This can be used in non-workflow builds to mark the build
  unstable.
other files (specific to build scripts)
  The build script can produce other relevant output in :file:`logs/` folder
  and in the build folder (which is typically :file:`gromacs/` for in-source
  builds and :file:`build/` for out-of-source builds).

.. _releng-jenkins-build-opts:

Build options
-------------

Currently, the following build options can be passed from Jenkins to
run_build() to influence the build environment (and as part of a configuration
line in a matrix specification).  These are typically used for
multi-configuration jobs; for jobs that only build a single configuration, the
configuration is typically hard-coded in the build script.  For boolean options,
multiple formats are accepted.  E.g., an OpenMP build can be specified as
``openmp`` or ``openmp=yes``, and no-OpenMP as ``no-openmp`` or ``openmp=no``.
The defaults that are used if a particular option is not specified are
determined by the build script.

build-jobs=N
  Use the specified number of parallel jobs for building.
out-of-source
  Do the build out-of-source, even if an in-source build would be supported.
cmake-X.Y.Z
  Use the specified CMake version to generate the build system.
gcc-X.Y
  Use the specified gcc version as the compiler.
clang-X.Y
  Use the specified clang version as the compiler.
clang-analyzer
  Obsolete way of specifying the use of clang static analyzer (in combination
  with clang-X.Y).
clang-static-analyzer-X.Y
  Use the specified clang static analyzer as the compiler.
icc-X.Y
  Use Intel compiler (version is currently ignored; it is for informational
  purposes only and should match whatever is installed on the build nodes).
msvc-YYYY
  Use the specified MSVC version as the compiler.
cuda-X.Y
  Use the specified CUDA version.
amdappsdk-X.Y
  Use the specified AMD SDK version.
phi
  Build for Xeon Phi.
tsan
  Use thread sanitizer for the build.
atlas
  Use ATLAS as an external BLAS/LAPACK library.
x11
  Build also ``gmx view`` (i.e., use ``GMX_X11=ON``).
simd=SIMD
  Use the specified SIMD instruction set.
  If not set, SIMD is not used.
mpi
  Do an MPI build.

Build scripts can define additional options that only influence the behavior of
the build scripts.  This is used for matrix builds in :file:`gromacs.py` for
options that do not influence build the build environment or place requirements
on the build host.  This allows adding new options when the |Gromacs| build
system changes and new combinations need to be tested, without changing releng.

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
   with a suitable ``_OVERRIDES`` specified in :file:`gerrit.py`.  This will
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

.. TODO: The matrix-in-source-repo approach makes the example below incorrect,
   move it elsewhere and find a new one here.

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

Currently, there are limited unit tests for some parts of the Python scripts.
They require a backport of ``unittest.mock`` to be installed, and can be
executed with ::

    python -m releng.test

The only way to fully test the releng script is to upload a change
to Gerrit and let Jenkins build it.  In principle, it is possible to run the
script in an environment that exactly matches a Jenkins node (including paths
to all required tools and all relevant environment variables that Jenkins
sets), but that can be tedious to set up.  However, it is possible to execute
most of the code from the command line using ::

    python releng <options>

This requires that you have your projects checked out in the same layout as in
Jenkins: the gromacs, regressiontests, and releng repositories should be in
sibling directories, with directory names matching the repository names.

Please note that even though the command-line mode does not perform most of the
actions that the real build script does (unless you run it with ``--run``), it
can still write to some files etc.

Refactoring to better support mock execution is in progress, combined with
extending the scope of unit tests.
