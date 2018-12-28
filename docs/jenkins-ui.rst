Interacting with builds in Jenkins
==================================

This page documents what kind of information |Gromacs| builds provide in
Jenkins, how to access it, and how to interact with the builds (e.g., trigger
new ones).  This also covers how the builds appear when reported back to Gerrit
for builds triggered from there.

General
-------

* General information about what a build does and how is typically available on
  the project page in Jenkins (i.e., one level up from an individual build).
  Additional documentation is available at :doc:`../jenkins` (what the builds
  do), :doc:`workflow` (what the pipeline builds do) and :doc:`jenkins-config`
  (on how Jenkins is configured).
* The Changes section on any build summary page typically shows the changes
  that the build contains.  For builds triggered from Gerrit, this is the title
  of the commit in Gerrit.  For manually triggered builds, this is generally
  the newest change from the ``gromacs`` repository that is included in the
  build.  To see the full list of changes across all repositories (across all
  three repositories), look at the console log.  For pipeline jobs, this
  information is also available on the build summary page under Built
  revisions.
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
(most commonly, ``gromacs`` and one of the others), see on-demand builds and
manual triggering below.

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

On-demand builds
................

Some types of builds are not automatically triggered from Gerrit when a patch
set is uploaded, but instead need to be requested with a specifically formatted
comment in Gerrit.  The general format for the comment is ``[JENKINS]``
followed by keywords for the build(s) requested.  This mechanism can also be
used for cross-verification, i.e., verifying a different combination of changes
than what is triggered by default.  The general format is:

    ``[JENKINS]`` [ ``Cross-verify`` <NNNN> [``quiet``] | ``release-<YYYY>`` ] [<builds>]

If ``Cross-verify`` is specified, it builds the current change together with
the latest patch set of change number NNNN from Gerrit (should be from another
project).  If ``quiet`` is not specified, results are posted back to both
changes (the NNNN change only if it is still open), but the vote is not
affected.  For cross-verification with releng changes, the ``[JENKINS]``
comment needs to be posted in the releng change to ensure that the correct
releng scripts are used throughout the build.

If ``release-<YYYY>`` (name of a release branch) is specified, it builds the
current change together with release branch HEADs from other repositories.
This only makes sense for releng changes, where it should be run at least once
before merging if there is a possibility that the changes impact builds in the
release branches.  These do not
run automatically (at least for now) to reduce peak load, and make testing
releng changes easier (since in many cases, the test builds that are actually
interesting will only run after the matrix builds have been cleared from the
queue).

If neither of the above is specified, then the requested builds are built for
this change.

With any of the above variants, possible builds are:

* ``Coverage``: Triggers a coverage build.
* ``clang-analyzer``: Triggers the per-patchset clang static analysis build.
* ``Documentation``: Triggers the per-patchset documentation build.
* ``Nightly``: Triggers a matrix build with the nightly matrix specified in the
  ``gromacs`` repository.
* ``Package``: Triggers a packaging build.  When triggered from a source or a
  regression tests change, packages that repository.  When triggered from
  releng, packages both.
* ``Pre-submit``: Triggers a matrix build with the pre-submit matrix
  specified in the ``gromacs`` repository.
* ``Post-submit``: Triggers a matrix build with the post-submit matrix
  specified in the ``gromacs`` repository.
* ``Regtest-package``: Triggers a packaging build of regression tests (mainly
  makes sense for releng changes).
* ``Release``: Triggers a release pipeline build for testing the release
  process.  If ``no-dev`` is also specified (as ``Release no-dev``), the
  pipeline builds the tarballs without -dev suffixes for actually doing a
  release.
* ``Uncrustify``: Triggers the per-patchset uncrustify code style checker build.
* ``Update``: When triggered from a regressiontests change, generates reference
  data for tests that are missing it, and uploads those back to Gerrit.
* ``Update-regtest-hash``: When triggered from a source change, generates the
  latest release-versioned regressiontests tarball for that branch, and updates
  the MD5 in the source repository to match this tarball.

More than one build can be requested with a single comment; the keywords should
be separated by whitespace.  When the requested builds complete, a link to the
build is posted back.  In case there is just a single build, the link points
directly to it.  If there are multiple, the link points to a pipeline build and
the individual builds can be accessed through links on the build summary page
(some types of builds execute directly as part of the pipeline, and all
information is accessible directly from the build summary page).

If no builds are specified, a default set of builds is triggered.  For
cross-verification (including the release branch variant) from releng, it
triggers all per-patchset builds.  Otherwise, only the pre-submit matrix build
is triggered.

There can be also other content in the Gerrit comment that requests a build.
The ``[JENKINS]`` tag must appear at the start of a paragraph, and that
paragraph as a whole will be interpreted as keywords intended for Jenkins.

Manual triggering
.................

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

For some pipeline jobs, the default values for other refspecs than releng are
``auto``.  If left at that value, the value will be interpreted as the head of
the branch that matches the other refspecs.  For example, if
``REGRESSIONTESTS_REFSPEC`` is auto, and ``GROMACS_REFSPEC`` specifies a Gerrit
change from ``release-2019`` branch, then regression tests will be used from
the same branch.

Individual build types
----------------------

These sections specify details of particular build types.

Matrix builds
^^^^^^^^^^^^^

Current matrix/multi-configuration builds are actually composed of two
different Jenkins jobs: a triggering pipeline build (see
:ref:`releng-workflow-matrix-launcher`), and a child matrix build.
Normally, a link to the child matrix build gets posted to Gerrit, and it mostly
looks like a normal matrix build.  Only if the triggering pipeline job fails,
you will get a link to it.

Failed tests and compiler errors/warnings are aggregated on the matrix build
summary page across all configurations, and you can navigate to individual
issues through these links.  If this is not sufficient to understand why the
build fails/is unstable, you can check the console output of individual
configuration builds by clicking on the build ball in the configuration matrix.

To retrigger a build triggered from Gerrit, you will need to navigate to the
parent pipeline job.  You will find the link towards the top of the build
summary page, as "Started by upstream project ... build number NNN", and
clicking on the build number will take you to the parent build.  You can also
retrigger the job directly from the dropdown that is available next to the
build number link.

Similarly, to trigger a matrix build manually, you will need to do that for the
pipeline job.

Documentation
^^^^^^^^^^^^^

TODO

clang static analyzer
^^^^^^^^^^^^^^^^^^^^^

The build summary page shows the number of warnings/issues found in the console
output of the analyzer.  You can see the individual issues through the link.
Note that issues reported from code in the header are not handled well by the
tools we use, and we ignore those, but they are still shown in this list.

The build is unstable only if there are issues found from source files (not
headers).  Details on each issue is accessible through Analysis Report link on
the left.  This also includes the steps that the analyzer thinks leads to the
issue.

cppcheck
^^^^^^^^

Summary of the changes is visible on the build summary page, and individual
issues can be browsed by clicking on the links.  The build is unstable if any
issues are found.

uncrustify
^^^^^^^^^^

To see the full list of issues, look at the console log.

releng
^^^^^^

The build fails if any Python unit test in the releng repository fails.
The actual reason can be seen in the console log, but currently there are no
other indicators posted back to Gerrit or to the build summary page.

.. TODO: Other types

Known issues and limitations
----------------------------

The following issues, limitations, and potentially confusing behavior with the
current Jenkins setup are known:

* Post-submit builds are triggered by Gerrit Trigger, but the results are not
  posted back to Gerrit.  This is because new Gerrit versions are not
  compatible with the way the plugin posts the results (see `JENKINS-39132`_).
* If builds are aborted, some bogus errors can get reported back to Gerrit, but
  the build status should say ABORTED.  This is because there is no reasonable
  way to detect in all cases whether a build got aborted or failed because of
  other reasons.  This is related to `JENKINS-28822`_.
* If Jenkins gets restarted while builds triggered from Gerrit are running/queued,
  some of these builds may get resumed after the restart.  The in-memory state
  of Gerrit Trigger is not properly maintained, and the vote from Jenkins only
  reflects the results from a subset of the builds.  You can see this happening
  in Gerrit if there are less links to different builds than usual when Jenkins
  votes.

On-demand builds
^^^^^^^^^^^^^^^^

* Only one on-demand build can be run at a time for the same patch set.
  If you post another ``[JENKINS]`` comment to a patch set
  before the previous such build has finished, such a comment will get silently
  ignored.  This is how Gerrit Trigger plugin works.
* If an on-demand build is aborted (either manually, or because of a timeout),
  Jenkins votes -2 on the change in Gerrit.  For all other build results
  (either success or failure), Jenkins does not change its vote (the pre-submit
  verification vote stays).  This is a limitation in Gerrit Trigger (see
  `JENKINS-38743`_).

Matrix builds
^^^^^^^^^^^^^

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
* If a matrix build contains configurations that are assigned to build agents
  that are not part of the (static) matrix node axis, these are not built.
  The matrix build still passes, but the triggering pipeline build will detect
  this issue.  The matrix build still shows up as successful in such a
  scenario, but the link posted to Gerrit says it failed.

.. _JENKINS-28822: https://issues.jenkins-ci.org/browse/JENKINS-28822
.. _JENKINS-30437: https://issues.jenkins-ci.org/browse/JENKINS-30437
.. _JENKINS-38743: https://issues.jenkins-ci.org/browse/JENKINS-38743
.. _JENKINS-39132: https://issues.jenkins-ci.org/browse/JENKINS-39132
