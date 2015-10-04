Jenkins job configuration
=========================

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
