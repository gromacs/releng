Jenkins configuration
=====================

Job configuration
-----------------

Configuration for Jenkins projects that use the releng scripts are described here.

General configuration
^^^^^^^^^^^^^^^^^^^^^

SCM checkout configuration:

* Jenkins SCM configuration should be used to check out the repository from where the
  build is triggered as a subdirectory of the workspace, with the same name as
  the repository.  This is necessary for the Git Plugin to show reasonable
  change lists for the builds etc., although the build in reality always starts
  from the releng repository.  In a workflow build, this checkout can be done
  in the workflow script.
* The build script always needs to check out the :file:`releng` repository if it did
  not trigger the build, and start the build from there.
* The releng script will check out remaining repositories if necessary.
* Various ``*_REFSPEC`` environment variables (see
  :ref:`releng-input-env-vars`) need to be set in one way or another (see below
  for the suggested approach).

To create a build that allows both intuitive parameterized builds with given
refspecs and Gerrit Trigger builds, the following configuration is recommended:

* Use ``GROMACS_REFSPEC``, ``RELENG_REFSPEC``, and ``REGRESSIONTESTS_REFSPEC``
  as build parameters, with ``refs/heads/master`` (or another branch ref) as
  the default.
* Use "Prepare environment for the run" and the following Groovy script::

    if (!binding.variables.containsKey('GERRIT_PROJECT')) {
      return [CHECKOUT_PROJECT: 'gromacs', CHECKOUT_REFSPEC: GROMACS_REFSPEC]
    } else {
      return [CHECKOUT_PROJECT: GERRIT_PROJECT, CHECKOUT_REFSPEC: GERRIT_REFSPEC]
    }

* Configure all SCM checkout behaviors to use ``CHECKOUT_PROJECT`` and
  ``CHECKOUT_REFSPEC``.

SCM poll jobs are simpler, as it is possible to simply set the various
environment variables to static values using a properties file in "Prepare
environment for the run" (``CHECKOUT_PROJECT`` and the various ``*_REFSPEC``
variables).  Note that the SCM checkout behavior cannot use
``CHECKOUT_PROJECT`` in the git address, because the injected variables are not
available for SCM polling.

Normal/matrix builds
^^^^^^^^^^^^^^^^^^^^

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
to options such as ``gmxtest+``.

For matrix builds not triggered with a dynamic matrix (see below), the build
host can be selected with a ``host=`` or a ``label=`` option that is
automatically ignored by run_build().

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

Workflow builds
^^^^^^^^^^^^^^^

Workflow builds should use a bootstrapping script like this::

  def script
  node('bs_nix-matrix_master') {
      def checkout_refspec = RELENG_REFSPEC
      if (binding.variables.containsKey('GERRIT_PROJECT')) {
          if (GERRIT_PROJECT == 'releng') {
              checkout_refspec = GERRIT_REFSPEC
          }
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
      script = load 'releng/workflow/<workflow-name>.groovy'
      <possible additional calls as needed by the workflow>
  }
  script.doBuild(<possible additional parameters>)

where expressions in angle brackets depend on the workflow.
The workflow script will take care of most other tasks; the Jenkins
configuration may only need to specify some build parameters (typically,
``GROMACS_REFSPEC`` etc., as for normal builds) and the possible build triggers.

Jenkins plugins
---------------

The following Jenkins plugins are used in |Gromacs| builds:

TODO

Build slave labels
------------------

TODO
