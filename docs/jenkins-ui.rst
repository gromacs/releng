Interacting with builds in Jenkins
==================================

This page documents what kind of information |Gromacs| builds provide in
Jenkins, how to access it, and how to interact with the builds (e.g., trigger
new ones).

General
-------

* General information about what a build does and how is typically available on
  the project page in Jenkins (i.e., one level up from an individual build).
  Additional documentation is available at :doc:`../jenkins` (what the builds
  do), :doc:`workflow` (what the workflow builds do) and :doc:`jenkins-config`
  (on how Jenkins is configured).
* The Changes section on any build summary page typically shows the changes
  that the build contains.  For builds triggered from Gerrit, this is the title
  of the commit in Gerrit.  For manually triggered builds, this is generally
  the newest change from the ``gromacs`` repository that is included in the
  build.  To see the full list of changes across all repositories (across all
  three repositories), look at the console log.  For workflow jobs, some of
  this information is also available on the build summary page under Built
  revisions, but this does not always include the commit titles.
* Because of interplay between the three repositories and the Jenkins
  configuration, it is not always possible for old changes to get a green build
  from Jenkins.  A typical case is if change X has been merged to ``gromacs``,
  and change Y to ``regressiontests``, and tests added/changed in Y need X to
  pass.  In such a case, any changes whose git ancestry does not include change
  X will get an unstable vote, even if they earlier passed Jenkins
  verification.  So if you get seemingly unrelated errors when uploading new
  versions of old changes, please check whether rebasing solves the issue.

  Also, no particular effort is put into maintaining ``releng`` backwards
  compatibility over long periods of time if such a rebasing need already
  exists.  This means that your build may also fail with mysterious Python
  errors from ``releng`` if the API has changed, if such a rebasing need
  exists and your change is particularly old.

.. _releng-triggering-builds:

Triggering builds
^^^^^^^^^^^^^^^^^

Gerrit automatically triggers builds for any change uploaded.  This includes
changes uploaded to regressiontests and releng, but the set of builds triggered
depends on the repository.  For any change, the build will be done with the
change from Gerrit, combined with the latest merged change from the other
repositories.  For verifying simultaneous changes to more than one repository
(most commonly, ``gromacs`` and one of the others), see manual triggering
below.

For drafts, Jenkins has to be added manually as reviewer so that Jenkins sees
the change.  It will start reviewing from the next patch set you upload to the
draft, or you can trigger a build manually (see below).

If a change from Gerrit does not automatically trigger a build (e.g., because
Jenkins was down when you uploaded your change), you can manually recreate the
event using Query and Trigger Gerrit Patches on Jenkins main page.

If a change from Gerrit got built, but there was a technical/temporary problem
with the build, you can use Rebuild or Rebuild All links on the build summary
page.  This will do the build again and post the results again to Gerrit.
Rebuild builds only the build where it was clicked (it uses the results of the
other, already done builds when reporting back).  Rebuild All rebuilds all the
triggered builds, in case all or most of them had problems.
It is not possible to rebuild only a part of the matrix job.

Some types of builds are not automatically triggered from Gerrit when a patch
set is uploaded, but instead need to be requested with a specifically formatted
comment in Gerrit.  The general format for the comment is ``[JENKINS]``
followed by keywords for the build(s) requested.  Currently, the following
keywords are supported:

* ``Coverage``: Triggers a coverage build.
* ``Cross-verify`` NNNN: Triggers a cross-verification build using the
  pre-submit matrix, building the current change together with the latest patch
  set of change number NNNN from Gerrit (should be from another project).
  Results are posted back to both changes (the NNNN change only if it is still
  open), but the vote is not affected.  For cross-verification with releng
  changes, the ``[JENKINS]`` comment needs to be posted in the releng change
  to ensure that the correct releng scripts are used throughout the build.
* ``Package``: Triggers a packaging build.  When triggered from a source or a
  regression tests change, packages that repository.  When triggered from
  releng, packages both.
* ``Post-submit``: Triggers a matrix build with the post-submit matrix
  specified in the ``gromacs`` repository.
* ``Release``: Triggers a release workflow build for testing the release
  process.
* ``release-2016``: Triggers all per-patchset builds for the release branch.
  Only makes sense for releng changes, where it should be run at least once
  before merging if there is a possibility that the changes impact builds in
  the release branch.  These do not run automatically (at least for now) to
  reduce peak load, and make testing releng changes easier (since in many
  cases, the test builds that are actually interesting will only run after the
  matrix builds have been cleared from the queue).

More than one build can be requested with a single comment; the keywords should
be separated by whitespace.  When the requested builds complete, a link to the
build is posted back.  In case there is just a single build, the link points
directly to it.  If there are multiple, the link points to a workflow build and
the individual builds can be accessed through links on the build summary page.

There can be also other content in the Gerrit comment that requests a build.
The ``[JENKINS]`` tag must appear at the start of a paragraph, and that
paragraph as a whole will be interpreted as keywords intended for Jenkins.

To manually trigger a build (e.g., for testing job configuration changes), use
Build with Parameters on the project page, for the same builds that are
triggered from Gerrit.  Enter the refspecs (like ``refs/changes/53/2053/1``)
for the combination you want to build.  This will not report anything back to
Gerrit.  The refspec for changes in Gerrit is of the form
``refs/changes/MM/NNMM/PP``, where ``NNMM`` is the number of the change and
``PP`` is the patch set number.  You can see the refspec, e.g., in the download
links on the change page.  Depending on how the job does the checkout, Jenkins
may again need to be added as a reviewer for draft changes before manual
triggering is possible.

Matrix builds
-------------

Current matrix/multi-configuration builds are actually composed of two
different Jenkins jobs: a triggering workflow build (see
:ref:`releng-workflow-matrix-launcher`), and a child matrix build.
Normally, a link to the child matrix build gets posted to Gerrit, and it mostly
looks like a normal matrix build.  Only if the triggering workflow job fails,
you will get a link to it.

Failed tests and compiler errors/warnings are aggregated on the matrix build
summary page across all configurations, and you can navigate to individual
issues through these links.  If this is not sufficient to understand why the
build fails/is unstable, you can check the console output of individual
configuration builds by clicking on the build ball in the configuration matrix.
Note a few caveats:

* If the build was aborted, there is no visual cue in the configuration matrix
  for the configurations that were not yet finished by the time the build was
  aborted.  They look exactly like configurations that were not run at all.
* If the set of configurations has changed (in particular, if you are building
  a change in Gerrit that changes the configurations), the configuration matrix
  on the build summary page may not reflect the actual configurations used
  (see `JENKINS-30437`_).  You can see the actual configurations that were
  built and their results from the console log, and navigate to the individual
  configurations from there.  Note, however, that the links in the console log
  take you to the project page, not to the individual build, so you will need
  to click another time to get to the actual build.  The child configuration
  builds always have the same build number as the matrix parent.

.. _JENKINS-30437: https://issues.jenkins-ci.org/browse/JENKINS-30437

To retrigger a build triggered from Gerrit, you will need to navigate to the
parent workflow job.  You will find the link towards the top of the build
summary page, as "Started by upstream project ... build number NNN", and
clicking on the build number will take you to the parent build.  You can also
retrigger the job directly from the dropdown that is available next to the
build number link.

Similarly, to trigger a matrix build manually, you will need to do that for the
workflow job.

Documentation
-------------

TODO

clang static analyzer
---------------------

The build summary page shows the number of warnings/issues found in the console
output of the analyzer.  You can see the individual issues through the link.
Note that issues reported from code in the header are not handled well by the
tools we use, and we ignore those, but they are still shown in this list.

The build is unstable only if there are issues found from source files (not
headers).  Details on each issue is accessible through Analysis Report link on
the left.  This also includes the steps that the analyzer thinks leads to the
issue.

cppcheck
--------

Summary of the changes is visible on the build summary page, and individual
issues can be browsed by clicking on the links.  The build is unstable if any
issues are found.

uncrustify
----------

To see the full list of issues, look at the console log.

.. TODO: Other types
