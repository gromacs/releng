"""
Jenkins build scripts

Jenkins uses the scripts in this package to do builds.
The main interface for Jenkins is to import the package and use run_build().
Other functions defined here are used from workflow builds, and typically
return values are passed through StatusReporter back to the workflow build
(using a temporary file, since that is by far the simplest way to pass
information back).
For testing, the package can also be executed as a command-line module.
"""

# Expose the JobType enum to make it simpler to import just the releng module
# and call run_build().
from common import JobType, Project

def run_build(build, job_type, opts, project=Project.GROMACS):
    """Main entry point for Jenkins builds.

    Runs the build with the given build script and build parameters.
    Before calling this script, the job should have checked out the releng
    repository to a :file:`releng/` subdirectory of the workspace, and
    the repository that triggered the build, similarly in a subdirectory of the
    workspace.

    See :doc:`releng` for more details on the general build organization.

    Args:
        build (str): Build type identifying the build script to use.
            Names without directory separators are interpreted as
            :file:`gromacs/admin/builds/{build}.py`, i.e., loaded from
            the main repository.
        job_type (JobType): Type/scope of the job that can, e.g.,
            influence the scope of testing.
            Not all build scripts use the value.
        opts (List[str]):
            This is mainly intended for multi-configuration builds.
            Build scripts not intended for such builds may simply ignore most
            of the parameters that can be influenced by these options.
    """
    from context import BuildContext
    from factory import ContextFactory
    # Please ensure that __main__.py stays in sync.
    factory = ContextFactory(default_project=project)
    with factory.status_reporter:
        BuildContext._run_build(factory, build, job_type, opts)

def read_build_script_config(script_name):
    """Reads build options specified in a build script.

    Args:
        script_name (str): Name of the build script (see run_build()).
    """
    from context import BuildContext
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter as status:
        config = BuildContext._read_build_script_config(factory, script_name)
        status.return_value = config

def prepare_multi_configuration_build(configfile):
    """Main entry point for preparing matrix builds.

    Reads a file with configurations to use (one configuration per line,
    with a list of space-separated build options on each line; comments
    starting with # and empty lines ignored).

    Args:
        configfile (str): File that contains the configurations to use.
            Names without directory separators are interpreted as
            :file:`gromacs/admin/builds/{configfile}.txt`.
    """
    from factory import ContextFactory
    from matrixbuild import prepare_build_matrix
    factory = ContextFactory()
    with factory.status_reporter:
        prepare_build_matrix(factory, configfile)

def process_multi_configuration_build_results(inputfile):
    """Processes results after a matrix build has been run.

    Reads a JSON file that provides information about the configurations
    (the output from prepare_multi_configuration_build()) and the URL of
    the finished Jenkins matrix build.
    Reads information about the executed build using Jenkins REST API and
    verifies that all configurations were built.

    Args:
        inputfile (str): File to read the input from, relative to working dir.
    """
    from factory import ContextFactory
    from matrixbuild import process_matrix_results
    factory = ContextFactory()
    with factory.status_reporter as status:
        status.return_value = process_matrix_results(factory, inputfile)

def get_actions_from_triggering_comment():
    """Processes Gerrit comment that triggered the build.

    Parses the comment that triggered an on-demand build and returns a
    structure that tells the workflow build what it needs to do.
    """
    from factory import ContextFactory
    from ondemand import get_actions_from_triggering_comment
    factory = ContextFactory()
    with factory.status_reporter as status:
        status.return_value = get_actions_from_triggering_comment(factory)

def do_ondemand_post_build(inputfile):
    """Does processing after on-demand builds have finished.

    Reads a JSON file that provides information about the builds (and things
    forwarded from the output of get_actions_from_triggering_comment()), and
    returns a structure that specifies what to post back to Gerrit.

    Can also perform other actions related to processing the build results,
    such as posting cross-verify messages.

    Args:
        inputfile (str): File to read the input from, relative to working dir.
    """
    from factory import ContextFactory
    from ondemand import do_post_build
    factory = ContextFactory()
    with factory.status_reporter as status:
        status.return_value = do_post_build(factory, inputfile)

def get_build_revisions():
    """Provides information about revisions used in the build.

    Returns a structure that provides a list of projects and their revisions
    used in this build.
    """
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter as status:
        status.return_value = factory.workspace._get_build_revisions()

def read_source_version_info():
    """Reads version info from the source repository.

    Returns a structure that provides version information from the source
    repository.
    """
    from context import BuildContext
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter as status:
        context = BuildContext._run_build(factory, 'get-version-info', JobType.GERRIT, None)
        version, regtest_md5sum = context._get_version_info()
        status.return_value = {
                'version': version,
                'regressiontestsMd5sum': regtest_md5sum
            }
