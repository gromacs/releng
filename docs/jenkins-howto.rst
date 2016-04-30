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
