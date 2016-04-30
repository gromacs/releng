releng repository
=================

.. toctree::
   :maxdepth: 2

   releng
   workflow
   releng-api
   jenkins-config
   jenkins-ui
   jenkins-howto

Separate ``releng`` repository hosts various development-time scripts for
|Gromacs|.  Currently, this is used for build scripts on the Jenkins CI system,
but in the future, other scripts that do not have a strong connection to a
particular code version could also live here, as well as documentation that can
evolve separately from the source code (if not on the wiki).

The ``releng`` repository currently contains two main parts:

* ``releng`` Python package contains Python scripts used for Jenkins
  builds.
* ``workflow`` subdirectory contains Groovy scripts for use with the Pipeline
  plugin (formerly Workflow plugin) for running jobs with more complicated
  control flow in Jenkins.

These are documented on separate pages above.

.. TODO: Some more introductory text.
