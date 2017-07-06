How to do common things with Jenkins builds
===========================================

See also :doc:`jenkins-ui`.

Add a new configuration to a build
----------------------------------

To add a new configuration to an existing matrix build, the required steps vary
a bit depending on how similar your configuration is to existing ones:

1. If the new configuration is just a new combination of existing options, it
   is sufficient to add the configuration to the respective file under
   :file:`admin/builds/`, and test that it works.  Changes to
   :file:`pre-submit-matrix.txt` will automatically get verified when you
   upload your changes to Gerrit.

   a. If your combination requires a specific combination of software that is
      not yet available, you will need to update :file:`releng/slaves.py` in
      the ``releng`` repo, and possibly install that combination of software on
      a slave.

2. If the new configuration requires new options, but those options do not
   affect where the configuration can be built (i.e., do not require special
   software on the build slaves), you need to update
   :file:`admin/builds/gromacs.py` to specify the options and how they affect
   the build, and then add the configurations to the matrix in
   :file:`admin/builds/`.

3. If the new configuration requires new options that affect job placement, you
   need to update

   * :file:`releng/options.py` to specify the new option and a label for it,
   * :file:`releng/slaves.py` to specify which build slaves support the option,
   * possibly :file:`releng/environment.py` to specify special CMake options or
     other configuration (e.g., changes to ``PATH``) that is required for the
     build to work with this option (if you need this, you also need to specify
     in :file:`releng/options.py` that your new function in
     :file:`releng/environment.py` should be called to process your new
     option),
   * possibly :file:`admin/builds/gromacs.py` if your new option affects the
     build beyond the changes above, and
   * finally add the configuration to the matrix and test it.

Add a new build slave
---------------------

To add a new slave to be used for builds, the steps are outlined below:

1. Install the slave so that Jenkins can connect to it and the slave can
   connect to Gerrit (this configuration is currently outside the scope of this
   documentation).
2. Install necessary software on the slave to be used in the builds (compilers
   and other tools).
   Please see :file:`releng/environment.py` for how various programs are
   located, and install them on the new slave to be found in the same way
   (if something seems awkward, the approach should be changed on all slaves,
   not by adding more variability).
3. Ensure that the slave is listed in :file:`releng/slaves.py` and has the
   correct labels and other constraints defined appropriately.
4. Ensure that the slave has relevant labels defined in Jenkins if it needs to
   run builds that rely on them (see :doc:`jenkins-config`).

If the slave does not get automatically used, follow steps above for adding a
new configuration to use the slave if it is intended for building one or more
matrix configurations.

Add builds for a new release branch
-----------------------------------

After creating a release branch (in both ``gromacs`` and ``regressiontests``
repositories; ``releng`` is only using a single branch (``master``)), the
following steps are needed to have full Jenkins builds running for it:

* Clone all per-branch jobs in Jenkins from those for ``master``.  Currently
  this includes pre- and post-submit matrix jobs, corresponding triggering
  pipelines, a nightly documentation build, and a release pipeline including
  two packaging builds.

  Adjust the Gerrit Trigger and/or SCM configuration and/or job parameter
  defaults for the cloned jobs to trigger from the correct branch.  Also adjust
  the job descriptions if they contain branch-specific information.

  Adjust the pipeline jobs to reference the correct per-branch jobs (the matrix
  jobs are referenced from the triggering pipelines, and the packaging jobs
  from the release pipeline).

  Note that Copy Project link in Jenkins is not visible for pipeline jobs; you
  can achieve the same effect by selecting New Item at the top level and
  copying from an existing item.

  TODO: The number of jobs required here could be reduced.

* Adjust the Gerrit Trigger configuration for jobs that are not
  branch-specific and add the new branches as appropriate.  Remove obsolete
  release branches from the triggering configuration.  This step impacts
  non-matrix pre-submit verification jobs, and an on-demand pipeline job.
  Note that Releng_PreSubmit is only triggered from ``releng`` and does not
  need to be considered here.

  TODO: Consider either reducing the number of jobs affected, or consider using
  dynamic triggering configuration to be able to specify the supported branches
  in a single location.
