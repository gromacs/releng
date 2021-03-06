Jenkins configuration
=====================

This page explains common Jenkins configuration used in |Gromacs| builds.
You may want to first read :doc:`releng` to understand how the actual builds
are done.

Job configuration for freestyle projects
----------------------------------------

Configuration for Jenkins projects that use the releng scripts are described here.
The description in this section applies directly to freestyle (non-pipeline) builds.
Pipeline builds also apply the same principles, but similarities and
differences are described in the next section.

SCM checkout configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Jenkins SCM configuration should be used to check out the repository from where the
  build is triggered as a subdirectory of the workspace, with the same name as
  the repository (this creates the layout described in :doc:`releng`).
  Using the triggering repository is necessary for the Git Plugin to show
  reasonable change lists for the builds etc., although the build in reality
  always starts from the :file:`releng` repository.
* The build script always needs to check out the :file:`releng` repository if it did
  not trigger the build, and start the build from there.
* The releng script will check out remaining repositories if necessary.

Build parameters and environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Various ``*_REFSPEC`` environment variables (see :ref:`releng-input-env-vars`)
need to be set in one way or another. The suggested approach is to use build
parameters as below:

To create a build that allows both intuitive parameterized builds with given
refspecs and Gerrit Trigger builds, the following configuration is recommended:

* Use ``GROMACS_REFSPEC``, ``RELENG_REFSPEC``, and ``REGRESSIONTESTS_REFSPEC``
  (if needed) as build parameters, with ``refs/heads/master`` (or another
  branch ref) as the default.
  With pipeline builds, it is possible to also set ``GROMACS_REFSPEC`` and
  ``REGRESSIONTESTS_REFSPEC`` to ``auto`` as the default.
* Use "Prepare environment for the run" and the following Groovy script::

    if (!binding.variables.containsKey('GERRIT_PROJECT')) {
      return [CHECKOUT_PROJECT: 'gromacs', CHECKOUT_REFSPEC: GROMACS_REFSPEC]
    } else {
      return [CHECKOUT_PROJECT: GERRIT_PROJECT, CHECKOUT_REFSPEC: GERRIT_REFSPEC]
    }

* Configure all SCM checkout behaviors to use ``CHECKOUT_PROJECT`` and
  ``CHECKOUT_REFSPEC``.

To create a build that works as expected in all corner cases when triggered
from a pipeline job, the following configuration is recommended:

* Create additional string parameters ``GROMACS_HASH``, ``RELENG_HASH``, and
  ``REGRESSIONTESTS_HASH`` with empty default values.
* Create a string parameter ``CHECKOUT_PROJECT``, with the default value
  ``gromacs`` (or another repository that you want to see in Changes section
  for manually triggered builds).
* Use the following Groovy script for injecting environment variables::

    return [CHECKOUT_REFSPEC: binding.variables."${CHECKOUT_PROJECT.toUpperCase()}_REFSPEC"]

  If you also need to support directly triggering the build with Gerrit
  Trigger, you need a slightly more complicated script, but in most cases, it
  should be the pipeline job that is triggered with Gerrit Trigger.

In SCM poll jobs it is possible to simply set the various environment variables
to static values using a properties file in "Prepare environment for the run"
(``CHECKOUT_PROJECT`` and the various ``*_REFSPEC`` variables).  Note that the
SCM checkout behavior cannot use ``CHECKOUT_PROJECT`` in the git address,
because the injected variables are not available for SCM polling.

Build steps
^^^^^^^^^^^

Builds that call run_build() should use the following post-build steps:

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
  releng.run_build('gromacs', releng.JobType.GERRIT, opts)

The script checks out the :file:`releng` repository to a :file:`releng/`
subdirectory of the workspace if not already checked out, imports the
:file:`releng` package and runs run_build() with arguments identifying which
build script to run, and options that affect how the build is done.
``shlex.split()`` is necessary to be able to pass quoted arguments with spaces
to options (not currently used).

Matrix builds are nowadays triggered through a pipeline build that chooses the
build hosts dynamically inside the releng Python scripts.
The scripts still support using with a ``host=`` or a ``label=`` option in the
options to select the host, and that option is automatically ignored by
run_build().

run_build() will first check out the :file:`gromacs` repository to a
:file:`gromacs/` subdirectory of the workspace, and then execute a script from
:file:`gromacs/admin/builds/`, selected based on the first argument.
If necessary, it will also check out the regression tests repository.
If the script exits with a non-zero exit code, the build fails.

Job configuration for pipeline builds
-------------------------------------

For pipeline job configuration, the same principles apply as for freestyle
projects, but much more is handled in the pipeline Groovy script instead of in
job configuration.

* SCM checkout as described above is handled by ``utils.checkoutDefaultProject()``,
  called from the beginning of each pipeline script.  Jenkins only needs to
  checkout the :file:`releng` repository to load the Groovy script (see the
  bootstrap script below).
* Build parameters for ``GROMACS_REFSPEC``, ``RELENG_REFSPEC``, and
  ``REGRESSIONTESTS_REFSPEC`` (if needed) should be added as for freestyle
  projects.  There is no need to deal with ``CHECKOUT_PROJECT`` or with
  environment variables explicitly (the environment injection plugin does not
  work with pipeline builds, either).  All processing of the parameters is done
  by ``utils.initBuildRevisions()`` at the start of each Groovy script.

  For ``GROMACS_REFSPEC`` and ``REGRESSIONTESTS_REFSPEC``, it is possible to use
  ``auto`` as the default value to create jobs that can be triggered for
  multiple branches from Gerrit or manually by specifying only one refspec.

* ``CHECKOUT_PROJECT`` must not be used as a build parameter (would currently
  confuse the Python scripts launched from Groovy).
* ``*_HASH`` parameters can be used as with freestyle projects.  If not set,
  they are computed at the beginning in ``utils.initBuildRevisions()``.
* In freestyle jobs, build status handling required scanning the console log
  and using :file:`unsuccessful-reason.log`.  In pipeline builds, this is
  handled inside ``utils.groovy`` whenever Python scripts are invoked, and uses
  return status of Python and a :file:`.json` file created by the Python code.

Pipeline builds use a bootstrapping script like this::

  def script
  node('pipeline-general') {
      def checkout_refspec = params.RELENG_REFSPEC
      if (params.GERRIT_PROJECT == 'releng') {
          checkout_refspec = params.GERRIT_REFSPEC
      }
      sh """\
          set -e
          mkdir -p releng
          cd releng
          git init
          git fetch ssh://jenkins@gerrit.gromacs.org/releng.git ${checkout_refspec}
          git checkout -qf FETCH_HEAD
          git clean -ffdxq
          git gc
          """.stripIndent()
      script = load 'releng/workflow/<pipeline-name>.groovy'
      <possible additional calls as needed by the pipeline>
  }
  script.doBuild(<possible additional parameters>)

where expressions in angle brackets depend on the pipeline.
For pipeline that are never triggered by Gerrit Trigger from releng, the part
referencing ``GERRIT_PROJECT`` and ``GERRIT_REFSPEC`` can be omitted.

Jenkins plugins
---------------

The following Jenkins plugins are used in |Gromacs| builds:

TODO

Build agent labels
------------------

The following labels on the Jenkins build agents are currently used to allocate
builds to agents:

pipeline-master
  Used to run general steps in pipeline jobs that do not do any lengthy
  processing (except for source code checkouts).  These could in principle run
  anywhere, but limiting them to a subset of the nodes reduces the number of
  workspaces used.  This reduces disk space use, and each time a new workspace
  is created, the initial checkout takes quite a bit of time.
clang-static-analyzer-X.Y
  Used to run clang static analysis builds.  The build is dynamically allocated
  using a version-specific label, based on what is specified in the
  :file:`clang-analyzer.py` build script in the source repository.
cppcheck
  Used to run cppcheck builds for release-2018 and earlier. For now, there is
  no version specification: all used versions of cppcheck must be installed on
  each node.
doxygen
  Used to run documentation builds.  In addition to Doxygen, also other tools
  needed by the documentation build (Sphinx, Latex) need to be installed here.
  Also the source packaging builds use this label, since they need Sphinx.
linux
  Used for regression test packaging builds to get a uniform enough environment.
windows
  Should not be currently used, but has been used to restrict Unix-specific
  things in pipelines to not run on Windows agents.

In other cases, agents are explicitly assigned to a node.  Multi-configuration
builds are currently assigned to nodes based on information in
:file:`agents.py`, not on labels configured in Jenkins.
