"""
Command-line interface to releng scripts for testing

This file provides a command-line interface that allows testing
the script more easily (it is still difficult; refactoring is needed).
Jenkins imports the module and uses run_build() from __init__.py
instead.
"""

import argparse
import os

from context import BuildContext
from workspace import Workspace

parser = argparse.ArgumentParser(description="""\
        Build script for GROMACS Jenkins CI builds
        """)
parser.add_argument('--dry-run', action='store_true', default=False,
                    help='Show what would be done, but do not execute anything')
parser.add_argument('--checkout', action='store_true', default=False,
                    help='Perform git checkout and clean actions (beware that it can delete any local modifications in the repos in the workspace)')
parser.add_argument('-U', '--user', help='User with ssh permissions to Gerrit')
parser.add_argument('--system', help='Override system for testing')
parser.add_argument('-B', '--build', help='Build script to run')
parser.add_argument('-J', '--job-type', help='Job type')
parser.add_argument('-W', '--workspace', help='Workspace root directory')
parser.add_argument('-O', '--opts', nargs='*', help='Build options')
args = parser.parse_args()

workspace_root = args.workspace
if workspace_root is not None:
    workspace_root = os.path.abspath(workspace_root)

# Please ensure that run_build() in __init__.py stays in sync.
workspace = Workspace(root=workspace_root, gerrit_user=args.user,
    dry_run=args.dry_run, checkout=args.checkout)
BuildContext._run_build(args.build, args.job_type, args.opts,
        workspace=workspace, system=args.system, dry_run=args.dry_run)
