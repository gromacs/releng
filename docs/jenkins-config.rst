Jenkins job configuration
=========================

Configuration for Jenkins projects that use the releng scripts are described here.

General configuration
---------------------

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
  simplicity, it is also possible to use ``GERRIT_PROJECT`` and
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

SCM poll jobs are simpler, as it is possible to simply set the various
environment variables to static values using a properties file in "Prepare
environment for the run" (``CHECKOUT_PROJECT`` and the various ``*_REFSPEC``
variables).  Note that the SCM checkout behavior cannot use
``CHECKOUT_PROJECT`` in the git address, because the injected variables are not
available for SCM polling.

Normal builds
-------------

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

Matrix builds with dynamic matrix
---------------------------------

To set up a build that builds multiple configurations, with the configurations
read from the ``gromacs`` repository, two builds are needed.

The actual build is configured as a multi-configuration build, following the
guidelines listed above.  The only difference is that there should be an
additional ``OPTIONS`` parameter for the build, and this should be used as a
dynamic axis in the matrix (using Dynamic Axis plugin).  Also, in order to
support assignment of hosts from the releng script, the build should use the
host that is provided in a ``host=`` option that is at the end of each
``OPTIONS`` value.
This build is not triggered directly from Gerrit, and the same build can
potentially be used for multiple different branches/configuration setups.

The build that is triggered from Gerrit is configured slightly differently:

* The Groovy script that injects the environment variables should inject an
  additional ``URL_TO_POST`` environment variable, with the value taken from
  ``BUILD_URL``.
* Gerrit Trigger should be configured to use ``URL_TO_POST`` as a custom url
  to post back to Gerrit.
* The first build step is running a Python script from releng, but after
  importing ``releng``, the call is of the form ::

    releng.prepare_multi_configuration_build('pre-submit-matrix', 'matrix.txt')

  where ``'pre-submit-matrix'`` identifies the matrix input file to use (will
  be loaded from :file:`gromacs/admin/builds/`).
* The next step uses Parameterized Trigger to trigger the actual build, passing
  the current build parameters and the parameters from
  :file:`build/matrix.txt`, and blocking until the build completes.
  This step should be configured to propagate the build status back from the
  matrix build, but it should not fail the actual build step, so that the next
  build steps still get executed even if the matrix build fails.
* The next step again calls ``releng``, this time as ::

    import releng
    releng.write_triggered_build_url_file('URL_TO_POST', 'build/url-to-post.txt')

* The last step injects environment varibles from the file specified above.
  
The last two steps make it possible to post the link to the downstream build to
Gerrit, avoiding additional clicks to get to the actual build.  If the build
fails without actually triggering the downstream build, the initial value set
to ``URL_TO_POST`` is used, and the link in Gerrit will point to the launcher
build, allowing the failure to be diagnosed.
