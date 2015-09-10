"""
Utilities for handling matrix builds

See __init__.py for documentation (the functions are called essentially
directly from there).
"""

import os
import pipes
import shlex

from common import Project

def prepare_build_matrix(factory, configfile, outputfile):
    workspace = factory.workspace
    workspace._checkout_project(Project.GROMACS)
    workspace._check_projects()
    workspace._init_build_dir(out_of_source=True)

    inputpath = workspace._resolve_build_input_file(configfile, '.txt')
    outputpath = os.path.join(workspace.build_dir, outputfile)

    configs = _read_matrix_configs(inputpath)
    _write_matrix_configs(outputpath, configs)

def _read_matrix_configs(path):
    configs = []
    with open(path, 'r') as fp:
        for line in fp:
            comment_start = line.find('#')
            if comment_start >= 0:
                line = line[:comment_start]
            line = line.strip()
            if line:
                opts = shlex.split(line)
                configs.append(opts)
    return configs

def _write_matrix_configs(path, configs):
    with open(path, 'w') as fp:
        line = 'OPTIONS'
        for opts in configs:
            quoted_opts = [pipes.quote(x) for x in opts]
            line += ' "{0}"'.format(' '.join(quoted_opts))
        fp.write(line + '\n')

def write_triggered_build_url_file(varname, filename):
    url = _get_last_triggered_build_url()
    with open(filename, 'w') as fp:
        fp.write('{0} = {1}\n'.format(varname, url))

def _get_last_triggered_build_url():
    job = os.environ['LAST_TRIGGERED_JOB_NAME']
    number = os.environ['TRIGGERED_BUILD_NUMBER_' + job]
    jenkins_url = os.environ['JENKINS_URL']
    return '{0}job/{1}/{2}/'.format(jenkins_url, job, number)
