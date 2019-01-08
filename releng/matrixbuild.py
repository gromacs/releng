"""
Utilities for handling matrix builds

See __init__.py for documentation (the functions are called essentially
directly from there).
"""

import json
import os.path
import pipes
import shlex

from common import BuildError, ConfigurationError, Project
from options import BuildConfig, select_build_hosts
import agents

def prepare_build_matrix(factory, configfile):
    projects = factory.projects
    projects.checkout_project(Project.GROMACS)
    projects.print_project_info()
    projects.check_projects()
    return get_matrix_info(factory, configfile)

def get_matrix_info(factory, configfile):
    configs = _get_build_configs(factory, configfile)
    return _create_return_value(configs)

def process_matrix_results(factory, inputfile):
    data = json.loads(''.join(factory.executor.read_file(inputfile)))
    configs = data['matrix']['configs']
    build_url = data['build_url']
    return process_matrix_failures(factory, configs, build_url)

def process_matrix_failures(factory, configs, build_url):
    status = factory.status_reporter
    configs = [BuildConfig.from_dict(x) for x in configs]
    build_info = factory.jenkins.query_matrix_build(build_url)
    build_info.merge_known_configs(configs)
    for run in build_info.runs:
        if run.is_success:
            continue
        reason = '{0} ({1}): {2}'.format(' '.join(run.opts), run.host, run.result)
        if run.is_unstable:
            status.mark_unstable(reason)
        else:
            status.mark_failed(reason)
    if not build_info.is_aborted and any([x.is_not_built for x in build_info.runs]):
        status.mark_failed("Some matrix configurations were not built (likely matrix axis is missing build agents)")
    return [x.to_dict() for x in build_info.runs]

def _get_build_configs(factory, configfile):
    executor = factory.executor
    workspace = factory.workspace
    inputpath = workspace._resolve_build_input_file(configfile, '.txt')
    configs = _read_matrix_configs(executor, inputpath)
    configs = select_build_hosts(factory, configs)
    _check_matrix_configs(configs)
    return configs

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
        if config.host and not agents.is_matrix_host(config.host):
            raise ConfigurationError('non-matrix agent would execute this combination: ' + ' '.join(config.opts))

def _create_return_value(configs):
    configs_json = [config.to_dict() for config in configs]
    return { 'configs': configs_json, 'as_axis': _get_options_string(configs) }

def _get_options_string(configs):
    contents = []
    for config in configs:
        opts = list(config.opts)
        if config.host:
            if agents.is_label(config.host):
                opts.append('label=' + config.host)
            else:
                opts.append('host=' + config.host)
        quoted_opts = [pipes.quote(x) for x in opts]
        contents.append('"{0}"'.format(' '.join(quoted_opts)))
    return ' '.join(contents)
