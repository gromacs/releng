"""
Jenkins build scripts

Jenkins uses the scripts in this package to do builds.
The main interface for Jenkins is to import the package and use run_build().
For testing, the package can also be executed as a command-line module.
"""

# Expose the JobType enum to make it simpler to import just the releng module
# and call run_build().
from common import JobType

def run_build(build, job_type, opts):
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
    from context import BuildContext, ContextFactory
    # Please ensure that __main__.py stays in sync.
    factory = ContextFactory()
    BuildContext._run_build(factory, build, job_type, opts)

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
    from context import ContextFactory
    from matrixbuild import prepare_build_matrix
    factory = ContextFactory()
    prepare_build_matrix(factory, configfile, outputfile)

def write_triggered_build_url_file(varname, filename):
    """Extracts the URL for a build triggered with Parameterized Trigger.

    Writes a Java properties file suitable for injecting an environment
    variable named ``varname`` into the build, containing the URL of the last
    job triggered with Parameterized Trigger (requires that the triggering
    build step was blocking).

    Args:
        varname (str): Variable to set.
        filename (str): File (including path) to write the properties to.
    """
    from context import ContextFactory
    from matrixbuild import write_triggered_build_url_file
    factory = ContextFactory()
    write_triggered_build_url_file(factory, varname, filename)
