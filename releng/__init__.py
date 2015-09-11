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
