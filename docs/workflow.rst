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
