"""
Command-line interface to releng scripts for testing

This file provides a command-line interface that allows testing
the script more easily (some things are still difficult; refactoring is
needed).
Jenkins imports the module and uses run_build() from __init__.py
instead.
"""

import argparse
import os
import six

from common import Project
from context import BuildContext
from factory import ContextFactory
import matrixbuild

def run_build(args, factory):
    BuildContext._run_build(factory, args.script, args.job_type, args.opts)

def prepare_matrix(args, factory):
    status = factory.status_reporter
    status.return_value = matrixbuild.prepare_build_matrix(factory, args.matrix)

def process_matrix(args, factory):
    status = factory.status_reporter
    if args.input_file:
        status.return_value = matrixbuild.process_matrix_results(factory, args.input_file)
    else:
        factory.projects.checkout_project(Project.GROMACS)
        configs = matrixbuild.get_matrix_info(factory, args.matrix)['configs']
        build_url = 'http://jenkins.gromacs.org/job/{0}/{1}'.format(args.job_name, args.build_number)
        status.return_value = matrixbuild.process_matrix_failures(factory, configs, build_url)

parser = argparse.ArgumentParser(description="""\
        Test driver fof build scripts for GROMACS Jenkins CI builds
        """)
parser.add_argument('-U', '--user', help='User with ssh permissions to Gerrit')
parser.add_argument('--system', help='Override system for testing')
parser.add_argument('-N', '--node', default='unknown',
                    help='Override node name for testing')
parser.add_argument('-W', '--workspace', help='Workspace root directory')
parser.add_argument('-P', '--project', help='Project for the build')
parser.add_argument('--run', action='store_true', default=False,
                    help='Actually run the build, instead of only showing what would be done')
subparsers = parser.add_subparsers()

parser_run = subparsers.add_parser('run', help='Run a build script')
parser_run.add_argument('script', help='Build script to run')
parser_run.add_argument('-J', '--job-type', help='Job type')
parser_run.add_argument('-O', '--opts', nargs='*', help='Build options')
parser_run.set_defaults(func=run_build)

parser_prepare = subparsers.add_parser('prepare-matrix', help='Process matrix definitions')
parser_prepare.add_argument('matrix', help='Matrix to process')
parser_prepare.set_defaults(func=prepare_matrix)

parser_process = subparsers.add_parser('process-matrix', help='Process matrix results')
parser_process.add_argument('-I', '--input-file', help='Input file as used in Jenkins (if given, other arguments are ignored)')
parser_process.add_argument('-M', '--matrix', help='Matrix definition used to run the build')
parser_process.add_argument('-J', '--job-name', help='Matrix job name')
parser_process.add_argument('-n', '--build-number', help='Build number to process')
parser_process.set_defaults(func=process_matrix)

args = parser.parse_args()

workspace_root = args.workspace
if workspace_root is None:
    workspace_root = os.path.join(os.path.dirname(__file__), "..", "..")
workspace_root = os.path.abspath(workspace_root)

project = Project.GROMACS
if args.project is not None:
    project = Project.parse(args.project)

env = dict(os.environ)
env.update({
        'GROMACS_REFSPEC': 'HEAD',
        'RELENG_REFSPEC': 'HEAD',
        'REGRESSIONTESTS_REFSPEC': 'HEAD',
        'STATUS_FILE': 'logs/status.json',
        'WORKSPACE': workspace_root,
        'NODE_NAME': args.node
    })

# Please ensure that run_build() in __init__.py stays in sync.
factory = ContextFactory(default_project=project, system=args.system, env=env)
if not args.run:
    from executor import DryRunExecutor
    factory.init_executor(cls=DryRunExecutor)
factory.init_gerrit_integration(user=args.user)
with factory.status_reporter as status:
    args.func(args, factory)
