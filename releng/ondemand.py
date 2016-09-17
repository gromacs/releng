"""
Utilities for handling on-demand builds (triggered from Gerrit comments)
"""
import json
import os.path

from common import BuildError, Project
from integration import RefSpec
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
    triggering_project = gerrit.get_triggering_project()
    branch = None
    branch_projects = { Project.GROMACS, Project.REGRESSIONTESTS }
    if triggering_project and triggering_project in branch_projects:
        branch = gerrit.get_triggering_branch()
        branch_projects.remove(triggering_project)
    env = dict()
    gerrit_info = None
    builds = []
    delayed_actions = []
    while tokens:
        token = tokens.pop(0).lower()
        if token == 'coverage':
            builds.append({ 'type': 'coverage' })
        elif token == 'cross-verify':
            quiet = False
            token = tokens.pop(0)
            if token.lower() == 'quiet':
                quiet = True
                token = tokens.pop(0)
            change = gerrit.query_unique_change(token)
            if not triggering_project or not change.is_open:
                quiet = True
            project = change.project
            refspec = change.refspec
            if triggering_project and project == triggering_project:
                raise BuildError('Cross-verify is not possible with another change from the same repository')
            if project == Project.RELENG:
                raise BuildError('Cross-verify with releng changes should be initiated from the releng change in Gerrit')
            if branch is None:
                branch = change.branch
            if project in branch_projects:
                branch_projects.remove(project)
            gerrit.override_refspec(project, refspec)
            env['{0}_REFSPEC'.format(project.upper())] = refspec.fetch
            env['{0}_HASH'.format(project.upper())] = refspec.checkout
            workspace._checkout_project(Project.GROMACS)
            configs = get_build_configs(factory, 'pre-submit-matrix')
            builds.append({
                    'type': 'matrix',
                    'desc': 'cross-verify',
                    'options': get_options_string(configs)
                })
            if not triggering_project or triggering_project == Project.RELENG:
                builds.extend([
                        { 'type': 'clang-analyzer', 'desc': 'cross-verify' },
                        { 'type': 'cppcheck', 'desc': 'cross-verify' },
                        { 'type': 'documentation', 'desc': 'cross-verify' },
                        { 'type': 'uncrustify', 'desc': 'cross-verify' }
                    ])
            if not quiet:
                gerrit_info = {
                        'change': change.number,
                        'patchset': change.patchnumber
                    }
                delayed_actions.append(lambda: gerrit.post_cross_verify_start(change.number, change.patchnumber))
        elif token == 'package':
            project = triggering_project
            if project is None:
                project = Project.RELENG
            if project in (Project.GROMACS, Project.RELENG):
                builds.append({ 'type': 'source-package' })
            if project in (Project.REGRESSIONTESTS, Project.RELENG):
                builds.append({ 'type': 'regtest-package' })
        elif token == 'post-submit':
            # TODO: If this occurs before 'cross-verify', the build matrix
            # may get read from an incorrect change.
            workspace._checkout_project(Project.GROMACS)
            configs = get_build_configs(factory, 'post-submit-matrix')
            builds.append({
                    'type': 'matrix',
                    'desc': 'post-submit',
                    'options': get_options_string(configs)
                })
        elif token == 'release':
            builds.append({ 'type': 'release' })
        # TODO: Make this generic so that it works for all future release
        # branches as well.
        elif token == 'release-2016':
            if triggering_project and triggering_project != Project.RELENG:
                raise BuildError('Release branch verification only makes sense for releng changes')
            assert branch is None
            branch = token
            spec = 'refs/heads/' + token
            gromacs_refspec = RefSpec(spec)
            gromacs_hash = gerrit.get_remote_hash(Project.GROMACS, gromacs_refspec)
            gromacs_refspec = RefSpec(spec, gromacs_hash)
            gerrit.override_refspec(Project.GROMACS, gromacs_refspec)
            workspace._checkout_project(Project.GROMACS)
            configs = get_build_configs(factory, 'pre-submit-matrix')
            builds.extend([
                    {
                        'type': 'matrix',
                        'desc': token,
                        'options': get_options_string(configs)
                    },
                    { 'type': 'clang-analyzer', 'desc': token },
                    { 'type': 'cppcheck', 'desc': token },
                    { 'type': 'documentation', 'desc': token },
                    { 'type': 'uncrustify', 'desc': token }
                ])
        else:
            raise BuildError('Unknown request: ' + request)
    if branch and branch_projects:
        for project in sorted(branch_projects):
            spec = 'refs/heads/' + branch
            sha1 = gerrit.get_remote_hash(project, RefSpec(spec))
            env['{0}_REFSPEC'.format(project.upper())] = spec
            env['{0}_HASH'.format(project.upper())] = sha1
    for action in delayed_actions:
        action()
    result = { 'builds': builds }
    if env:
        result['env'] = env
    if gerrit_info:
        result['gerrit_info'] = gerrit_info
    return result

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
    if data.has_key('gerrit_info') and data['gerrit_info']:
        gerrit_info = data['gerrit_info']
        change = gerrit_info['change']
        patchset = gerrit_info['patchset']
        factory.gerrit.post_cross_verify_finish(change, patchset, build_messages)

def _get_url_and_messages(data):
    builds = data['builds']
    build_messages = ['{0}: {1}'.format(_get_url(x), x['result']) for x in builds]
    url = None
    if len(builds) == 1:
        url = _get_url(builds[0])
    return url, build_messages

def _get_url(build):
    url = build['url']
    if build.has_key('desc') and build['desc']:
        url += ' ({0})'.format(build['desc'])
    return url

def _write_message_json(executor, path, url, build_messages):
    if len(build_messages) == 1:
        build_messages = ''
    data = {
            'url': url,
            'message': '\n'.join(build_messages)
        }
    executor.write_file(path, json.dumps(data))
