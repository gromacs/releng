Pipeline build overview
=======================

This page documents specifics of different pipeline build scripts,
as well as giving an overview of common Groovy code used from different
pipeline scripts.  Behavior shared across all pipeline builds is described in
:doc:`releng` and :doc:`jenkins-config`.

.. _releng-workflow-matrix-launcher:

Matrix build launcher
---------------------

:file:`matrix-launcher.groovy` is a relatively simple pipeline script where the
actual build is performed by a normal matrix build.  The pipeline contains the
following steps:

1. In the initial node context, the bootstrap script calls
   ``loadMatrixConfigs()`` and passes the name of the matrix to use.  This
   calls ``releng.prepare_multi_configuration_build()``, and reads the build
   axis into a local variable.
2. The bootstrap script calls ``doBuild()`` with the name of the matrix job to
   trigger.  The pipeline triggers the matrix job, forwarding all relevant build
   parameters to it and adding the build configuration axis as an additional
   parameter.
3. After the matrix build finishes, the pipeline calls
   ``releng.process_multi_configuration_build_results()``, which uses the
   Jenkins REST API to get information about the results of the individual
   configurations.  The information is used to construct a failure message to
   Gerrit, as well as checking that all configurations were actually built.
4. The pipeline adds a link to the matrix build to the build summary page
   (while the build is running, the link can be found from the console log).
   The summary also includes the result of each configuration, and direct
   links to the build summary pages of each configuration.
   The build status of the matrix build is also propagated to the status of the
   pipeline job.
5. As the last step in the build, the pipeline sets the URL to post back to
   Gerrit to point to the matrix build.  This means that the presence of this
   launcher job is mostly invisible during normal usage.  Only if the pipeline
   itself fails before reaching this step, you actually see a link to the
   launcher job in Gerrit.

Gromacs pre-submit pipeline
---------------------------

For now, the :file:`gromacs-presubmit.groovy` is essentially the same as the
matrix launcher script, except that it supports multiple branches.  This is
done by receiving a prefix of the matrix jobs in ``doBuild()``, and appending
the name of the branch (deduced from the refspecs) in the pipeline.

The intention is for this pipeline to expand to cover also other pre-submit
verification, adding flexibility and reducing the need for separate builds for
different purposes.

Gromacs post-submit pipeline
----------------------------

For now, the :file:`gromacs-postsubmit.groovy` is essentially the same as the
matrix launcher script, except that it supports multiple branches like the
presubmit pipeline.

The intention is for this pipeline to expand to cover also other post-submit
verification if needed and add flexibility.

releng pre-submit pipeline
--------------------------

:file:`releng-presubmit.groovy` speficies steps to run to verify changes to
:file:`releng` repository in Gerrit.

As with :file:`gromacs-presubmit.groovy`, the intention is for this to assume
more responsibility for pre-submit verification.

Clang static analysis
---------------------

:file:`clang-analyzer.groovy` is a simple pipeline that performs static
analysis using Clang.  The main reason for using a pipeline build instead of a
freestyle job is to make it easy to dynamically decide the node where the
analysis runs, depending on which version of the analyzer should be used.
The sequence is:

1. In the initial node context, the pipeline calls
   ``utils.read_build_script_config()`` to get the build options defined in the
   :file:`clang-analyzer.py` build script in the source repo.
   This is stored in a local variable.
2. The bootstrap script calls ``doBuild()`` without parameters.
   The pipeline allocates a node based on the build options, and
   runs the :file:`clang-analyzer.py` build script there with releng.
3. After the releng script finishes, the pipeline publishes a HTML report
   produced by the analyzer (if it exists), and scans for compiler warnings
   from the console log to show them on the build page.

.. _releng-workflow-release:

Build & test release tarballs
-----------------------------

:file:`release.groovy` is a more complex pipeline that coordinates the building
and testing of the tarballs for a release.
The packaging of the tarballs is handled by two separate, non-pipeline Jenkins
jobs, one for the source code and one for the regressiontests.
The general sequence is:

1. In addition to common preparation, the pipeline reads a set of
   configurations to test from :file:`release-matrix.txt` in the source repo
   as with matrix builds.
   It also extracts version information from the source repository (using
   :file:`get-version-info.py` build script), since the regressiontests
   repository does not contain this.
2. The bootstrap script calls ``doBuild()`` with the names of the packaging
   jobs as parameters.
3. The pipeline checks the latest successful builds in the packaging builds,
   and if these are not built from the correct commit, it triggers new builds
   for them.  The regressiontests tarball is built first, and its MD5 sum is
   checked against the one specified in the source tarball.  For a `RELEASE`
   build, a mismatch fails the build, otherwise it only produces a note in the
   console output.
   The packaging builds also compute MD5 sums for the tarballs, and these are
   accessible from Jenkins.
4. After the tarballs are available, the pipeline runs each configuration
   from the test matrix in parallel, using ``run_build()``, and the standard
   :file:`gromacs.py` build script from the source tarball.
   A summary is posted to the build summary page (for each configuration, on
   which host it was built and whether it was successful, unstable, or failed),
   but compiler warnings etc. are currently only available from the console
   log (available for a single configuration with some browsing under "Pipeline
   Steps").
5. If all tests passed, the pipeline then does a final documentation build from
   the source tarball, which will produce the HTML pages for the documentation
   website.  The generated pages are available from the Jenkins project page,
   as well as from a link on the build summary page.
   If the `RELEASE` build parameter is set, a tarball containing all the
   documentation is also archived as an artifact.

In addition to the refspecs to build, the pipeline uses two additional build
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

The pipeline and the level of testing is still a work-in-progress, but it
already covers most of what the earlier builds did, and remaining content
should not be too hard to add.  Missing functionality is indicated with TODOs
in the pipeline script or in the build scripts in the source repo.

On-demand launcher
------------------

:file:`ondemand.groovy` handles builds that are triggered with a ``[JENKINS]``
comment from Gerrit.  For many cases, the actual builds are done using
separate, non-pipeline jobs triggered from the pipeline.
The general sequence is:

1. In the context of the initial checkout, the pipeline uses
   ``releng.get_actions_from_triggering_comment()`` to parse the comment from
   Gerrit, as well as the initial refspecs.  This replaces
   ``utils.initBuildRevisions()`` from other pipelines, but returns exactly the
   same information to the pipeline script (in addition to the information
   specific to the on-demand build).
   This function will also read information from the ``gromacs`` repository,
   e.g., to fill out the matrix options into the returned data structure.
   It also posts cross-verify messages to Gerrit if needed.
2. The bootstrap script calls ``doBuild()`` without parameters.  The pipeline
   runs the requested builds in parallel, based on the data structure it got in
   step 1.  All relevant build parameters are forwarded.  Some actions are
   handled directly within the pipeline instead of triggering a separate build.
3. After the builds finish, the pipeline adds links to the triggered builds
   to the build summary page (while the build is running, the link can be found
   from the console log).  The pipeline then uses ``releng.do_ondemand_post_build()``
   to construct the message to post back to Gerrit, as well as to perform other
   actions such as posting cross-verify messages.  The combined build status of
   the builds is also propagated to the status of the pipeline job.

Common Groovy scripts
---------------------

utils.groovy
^^^^^^^^^^^^

TODO

matrixbuild.groovy
^^^^^^^^^^^^^^^^^^

TODO

packaging.groovy
^^^^^^^^^^^^^^^^

TODO
