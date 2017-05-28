"""
Utilities for handling matrix builds

See __init__.py for documentation (the functions are called essentially
directly from there).
"""

import json
import os.path
import pipes
import shlex

from common import ConfigurationError, Project
from options import BuildConfig, select_build_hosts
import slaves

def prepare_build_matrix(factory, configfile, outputfile):
    executor = factory.executor
    workspace = factory.workspace
    workspace._checkout_project(Project.GROMACS)
    workspace._print_project_info()
    workspace._check_projects()
    workspace._init_build_dir(out_of_source=True)

    configs = get_build_configs(factory, configfile)
    _check_matrix_configs(configs)

    outputpath = os.path.join(workspace.build_dir, outputfile)
    _write_matrix_configs(executor, outputpath, configs)

def get_build_configs(factory, configfile):
    executor = factory.executor
    workspace = factory.workspace
    inputpath = workspace._resolve_build_input_file(configfile, '.txt')

    configs = _read_matrix_configs(executor, inputpath)
    configs = select_build_hosts(factory, configs)
    return configs

def get_options_string(configs):
    contents = []
    for config in configs:
        opts = list(config.opts)
        if slaves.is_label(config.host):
            opts.append('label=' + config.host)
        else:
            opts.append('host=' + config.host)
        quoted_opts = [pipes.quote(x) for x in opts]
        contents.append('"{0}"'.format(' '.join(quoted_opts)))
    return ' '.join(contents)

def _read_matrix_configs(executor, path):
    configs = []
    for line in executor.read_file(path):
        comment_start = line.find('#')
        if comment_start >= 0:
            line = line[:comment_start]
        line = line.strip()
        if line:
            opts = shlex.split(line)
            configs.append(BuildConfig(opts))
    return configs

def _check_matrix_configs(configs):
    for config in configs:
        if not slaves.is_matrix_host(config.host):
            raise ConfigurationError('non-matrix slave would execute this combination: ' + ' '.join(config.opts))

def _write_matrix_configs(executor, path, configs):
    ext = os.path.splitext(path)[1]
    if ext == '.json':
        contents = json.dumps([config.to_dict() for config in configs])
    else:
        contents = 'OPTIONS ' + get_options_string(configs)
    contents += '\n'
    executor.write_file(path, contents)
