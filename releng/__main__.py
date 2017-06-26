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

from common import Project
from context import BuildContext
from factory import ContextFactory
from matrixbuild import prepare_build_matrix

parser = argparse.ArgumentParser(description="""\
        Build script for GROMACS Jenkins CI builds
        """)
parser.add_argument('--run', action='store_true', default=False,
                    help='Actually run the build, instead of only showing what would be done')
parser.add_argument('-U', '--user', help='User with ssh permissions to Gerrit')
parser.add_argument('--system', help='Override system for testing')
parser.add_argument('-N', '--node', default='unknown',
                    help='Override node name for testing')
parser.add_argument('-W', '--workspace', help='Workspace root directory')
parser.add_argument('-B', '--build', help='Build script to run')
parser.add_argument('-P', '--project', help='Project for the build')
parser.add_argument('-J', '--job-type', help='Job type')
parser.add_argument('-O', '--opts', nargs='*', help='Build options')
parser.add_argument('-M', '--matrix', help='Matrix to process')
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
        'CHECKOUT_PROJECT': Project.RELENG,
        'CHECKOUT_REFSPEC': 'HEAD',
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
with factory.status_reporter:
    if args.matrix:
        prepare_build_matrix(factory, args.matrix)
    else:
        BuildContext._run_build(factory, args.build, args.job_type, args.opts)
