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

def get_build_revisions(filename):
    """Writes out information about revisions used in the build.

    Information is written as JSON.

    Args:
        filename (str): File to write the information, under logs/.
    """
    from factory import ContextFactory
    factory = ContextFactory()
    with factory.status_reporter:
        workspace = factory.workspace
        workspace._clear_workspace_dirs()
        workspace._get_build_revisions(workspace.get_path_for_logfile(filename))
