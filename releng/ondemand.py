"""
Utilities for handling on-demand builds (triggered from Gerrit comments)
"""
import json
import os.path

from common import BuildError, Project
from matrixbuild import get_build_configs, get_options_string

def get_actions_from_triggering_comment(factory, outputfile):
    workspace = factory.workspace
    workspace._init_build_dir(out_of_source=True)

    outputpath = os.path.join(workspace.build_dir, outputfile)

    request = factory.gerrit.get_triggering_comment()
    actions = _parse_request(factory, request)

    _write_actions(factory.executor, actions, outputpath)

def _parse_request(factory, request):
    workspace = factory.workspace
    gerrit = factory.gerrit
    tokens = request.split()
    builds = []
    while tokens:
        token = tokens.pop(0).lower()
        if token == 'coverage':
            builds.append({ 'type': 'coverage' })
        elif token == 'package':
            project = gerrit.get_triggering_project()
            if project is None:
                project = Project.RELENG
            if project in (Project.GROMACS, Project.RELENG):
                builds.append({ 'type': 'source-package' })
            if project in (Project.REGRESSIONTESTS, Project.RELENG):
                builds.append({ 'type': 'regtest-package' })
        elif token == 'post-submit':
            workspace._checkout_project(Project.GROMACS)
            configs = get_build_configs(factory, 'post-submit-matrix')
            builds.append({
                    'type': 'matrix',
                    'desc': 'post-submit',
                    'options': get_options_string(configs)
                })
        elif token == 'release':
            builds.append({ 'type': 'release' })
        else:
            raise BuildError('Unknown request: ' + request)
    return { 'builds': builds }

def _write_actions(executor, actions, path):
    executor.write_file(path, json.dumps(actions))

def do_post_build(factory, inputfile, outputfile):
    executor = factory.executor
    data = json.loads(''.join(executor.read_file(inputfile)))

    workspace = factory.workspace
    workspace._init_build_dir(out_of_source=True)
    outputpath = os.path.join(workspace.build_dir, outputfile)

    url, build_messages = _get_url_and_messages(data)
    _write_message_json(executor, outputpath, url, build_messages)

def _get_url_and_messages(data):
    builds = data['builds']
    if len(builds) == 1:
        return _get_url(builds[0]), []
    else:
        build_messages = ['{0}: {1}'.format(_get_url(x), x['result']) for x in builds]
        return None, build_messages

def _get_url(build):
    url = build['url']
    if build.has_key('desc') and build['desc']:
        url += ' ({0})'.format(build['desc'])
    return url

def _write_message_json(executor, path, url, build_messages):
    data = {
            'url': url,
            'message': '\n'.join(build_messages)
        }
    executor.write_file(path, json.dumps(data))
