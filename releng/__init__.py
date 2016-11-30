"""
Jenkins build scripts

Jenkins uses the scripts in this package to do builds.
The main interface for Jenkins is to import the package and use run_build().
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

def read_build_script_config(script_name, outputfile):
    """Reads build options specified in a build script.

    Args:
        script_name (str): Name of the build script (see run_build()).
        outputfile (str): File to write the configurations to, under build/.
    """
    from context import BuildContext
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter:
        BuildContext._read_build_script_config(factory, script_name, outputfile)

def prepare_multi_configuration_build(configfile, outputfile):
    """Main entry point for preparing matrix builds.

    Reads a file with configurations to use (one configuration per line,
    with a list of space-separated build options on each line; comments
    starting with # and empty lines ignored).
    Writes out a file with the provided name to build/, in a format suitable
    for passing to Parameterized Trigger as a build parameter that can be used
    as a dynamic axis in a matrix build to build the provided configurations.

    Args:
        configfile (str): File that contains the configurations to use.
            Names without directory separators are interpreted as
            :file:`gromacs/admin/builds/{configfile}.txt`.
        outputfile (str): File to write the configurations to, under build/.
    """
    from factory import ContextFactory
    from matrixbuild import prepare_build_matrix
    factory = ContextFactory()
    with factory.status_reporter:
        prepare_build_matrix(factory, configfile, outputfile)

def get_actions_from_triggering_comment(outputfile):
    """Processes Gerrit comment that triggered the build.

    Parses the comment that triggered an on-demand build and writes out a JSON
    file that tells the workflow build what it needs to do.

    Args:
        outputfile (str): File to write the information to, under builds/.
    """
    from factory import ContextFactory
    from ondemand import get_actions_from_triggering_comment
    factory = ContextFactory()
    with factory.status_reporter:
        get_actions_from_triggering_comment(factory, outputfile)

def do_ondemand_post_build(inputfile, outputfile):
    """Does processing after on-demand builds have finished.

    Reads a JSON file that provides information about the builds (and things
    forwarded from the output of get_actions_from_triggering_comment()), and
    writes a JSON file that specifies what to post back to Gerrit.

    Can also perform other actions related to processing the build results,
    such as posting cross-verify messages.

    Args:
        inputfile (str): File to read the input from, relative to working dir.
        outputfile (str): File to write the Gerrit message and URL to, under
            builds/.
    """
    from factory import ContextFactory
    from ondemand import do_post_build
    factory = ContextFactory()
    with factory.status_reporter:
        do_post_build(factory, inputfile, outputfile)

def get_build_revisions(outputfile):
    """Provides information about revisions used in the build.

    Information is written as a JSON file that can be read from a workflow
    script calling this (a temporary file is by far the simplest way to pass
    the information out).

    Args:
        outputfile (str): File to write the information to, under logs/.
    """
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter:
        workspace = factory.workspace
        workspace._clear_workspace_dirs()
        workspace._get_build_revisions(workspace.get_path_for_logfile(outputfile))

def read_source_version_info(outputfile):
    """Reads version info from the source repository.

    Information is written as a JSON file that can be read from a workflow
    script calling this (a temporary file is by far the simplest way to pass
    the information out).

    Args:
        outputfile (str): File to write the information to, under logs/.
    """
    from context import BuildContext
    from factory import ContextFactory
    import json
    factory = ContextFactory()
    with factory.status_reporter:
        context = BuildContext._run_build(factory, 'get-version-info', JobType.GERRIT, None)
        version, regtest_md5sum = context._get_version_info()
        contents = json.dumps({
                'version': version,
                'regressiontestsMd5sum': regtest_md5sum
            })
        path = factory.workspace.get_path_for_logfile(outputfile)
        factory.executor.write_file(path, contents)
