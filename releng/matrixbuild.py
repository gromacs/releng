"""
Utilities for handling matrix builds

See __init__.py for documentation (the functions are called essentially
directly from there).
"""

import json
import os.path
import pipes
import shlex

from common import Project
from options import select_build_hosts
import slaves

class MatrixConfig(object):
    def __init__(self, opts):
        self.opts = opts
        self.host = None
        self.labels = None

    def to_dict(self):
        return {
                'opts': self.opts,
                'host': self.host,
                'labels': ' && '.join(self.labels)
            }

def prepare_build_matrix(factory, configfile, outputfile):
    executor = factory.executor
    workspace = factory.workspace
    workspace._checkout_project(Project.GROMACS)
    workspace._print_project_info()
    workspace._check_projects()
    workspace._init_build_dir(out_of_source=True)

    inputpath = workspace._resolve_build_input_file(configfile, '.txt')
    outputpath = os.path.join(workspace.build_dir, outputfile)

    configs = _read_matrix_configs(executor, inputpath)
    configs = select_build_hosts(factory, configs)
    _write_matrix_configs(executor, outputpath, configs)

def _read_matrix_configs(executor, path):
    configs = []
    for line in executor.read_file(path):
        comment_start = line.find('#')
        if comment_start >= 0:
            line = line[:comment_start]
        line = line.strip()
        if line:
            opts = shlex.split(line)
            configs.append(MatrixConfig(opts))
    return configs

def _write_matrix_configs(executor, path, configs):
    ext = os.path.splitext(path)[1]
    if ext == '.json':
        contents = json.dumps([config.to_dict() for config in configs])
    else:
        contents = 'OPTIONS'
        for config in configs:
            opts = list(config.opts)
            if slaves.is_label(config.host):
                opts.append('label=' + config.host)
            else:
                opts.append('host=' + config.host)
            quoted_opts = [pipes.quote(x) for x in opts]
            contents += ' "{0}"'.format(' '.join(quoted_opts))
    contents += '\n'
    executor.write_file(path, contents)

def write_triggered_build_url_file(factory, varname, filename):
    url = _get_last_triggered_build_url(factory.env)
    factory.executor.write_file(filename, '{0} = {1}\n'.format(varname, url))

def _get_last_triggered_build_url(env):
    job = env['LAST_TRIGGERED_JOB_NAME']
    number = env['TRIGGERED_BUILD_NUMBER_' + job]
    jenkins_url = env['JENKINS_URL']
    return '{0}job/{1}/{2}/'.format(jenkins_url, job, number)
