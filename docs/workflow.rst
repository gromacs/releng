Workflow build overview
=======================

Matrix build launcher
---------------------

The workflow build in :file:`matrix-launcher.groovy` is a relatively simple
workflow where the actual build is performed by a normal matrix build.  The
workflow does these things:

1. The workflow does a normal git checkout to show Changes and other git data
   on the build page.  This happens in the initial node context where the
   workflow script is loaded.
2. Also in the initial node context, the Jenkins job calls
   ``loadMatrixConfigs()`` and passes the name of the matrix to use.  The
   workflow build calls ``prepare_multi_configuration_build()`` Python
   function, and reads the build axis into a local variable.
3. The Jenkins job calls ``doBuild()`` with the name of the matrix build to
   trigger.  The workflow triggers the matrix job, forwarding all relevant build
   parameters to it, and adding the build configuration axis as an additional
   parameter.
4. After the matrix build finishes, the workflow adds a link to the matrix
   build to the build summary page (while the build is running, the link can be
   found from the console log).

The workflow script sets an environment variable ``URL_TO_POST`` to be used
with Gerrit Trigger.  This will contain the URL of the matrix build, unless
there is a problem in the workflow itself, in which case it contains the URL of
the workflow build.  This makes it possible for the user to click on the link
in Gerrit and get directly to the build that caused the failure.
However, this does not currently work because of JENKINS-32692, so the workflow
is not used in production.

Build & test release tarballs
-----------------------------

The workflow build in :file:`release.groovy` is a more complex worflow that
coordinates the building and testing of the tarballs for a release.
The packaging of the tarballs is handled by two separate, non-workflow Jenkins
jobs, one for the source code and one for the regressiontests.
The general sequence is this:

1. The workflow reads the refspecs to use for the build from build parameters,
   and does some preparatory steps.  It also reads a set of configurations to
   test from :file:`release-matrix.txt` in the source repo, using
   ``prepare_multi_configuration_build()`` Python function, and reads the
   configuration into a data structure.
2. The workflow checks the latest successful builds in the packaging builds,
   and if these are not built from the correct commit, it triggers new builds
   for them.  The source tarball is built first, and its version extracted to
   be used in the regressiontests tarball (since the regressiontests repo does
   not contain version information).  The packaging builds also compute MD5
   sums for the tarballs, and these are accessible from Jenkins.
3. After the tarballs are available, the workflow runs each configuration
   from the test matrix in parallel, using ``run_build()``, and the standard
   :file:`gromacs.py` build script from the source tarball.
   A summary is posted to the build summary page (for each configuration, on
   which host it was built and whether it was successful, unstable, or failed),
   but compiler warnings etc.  are currently only available from the console
   log (available for a single configuration with some browsing under "Pipeline
   Steps").
4. If all tests passed, the workflow then does a final documentation build from
   the source tarball, which will produce the HTML pages for the documentation
   website.  The generated pages are available from the Jenkins project page,
   as well as from a link on the build summary page.
   If the RELEASE build parameter is set, a tarball containing all the
   documentation is also archived as an artifact.

In addition to the refspecs to build, the workflow uses two additional build
parameters:

RELEASE
  If set, the ``-dev`` suffix is stripped from all the tarballs, and from
  content within them.
  Note that currently, the ``-dev`` suffixes never appear in the generated
  website, irrespective of this
FORCE_REPACKAGING
  If set, the tarballs are rebuilt, even if ones built from the correct
  refspecs and with the same value of ``RELEASE`` is available.
  This is useful if only releng or Jenkins configuration has changed in a way
  that influences the tarballs.

The workflow and the level of testing is still a work-in-progress, but it
already covers most of what the earlier builds did, and remaining content
should not be too hard to add.  Missing functionality is indicated with TODOs
in the workflow script or in the build scripts in the source repo.
