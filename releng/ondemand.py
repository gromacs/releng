"""
Utilities for handling on-demand builds (triggered from Gerrit comments)
"""
import json
import os.path

from common import BuildError, JobType, Project
from integration import RefSpec
from matrixbuild import get_build_configs, get_options_string
from script import BuildScript

def get_actions_from_triggering_comment(factory, outputfile):
    workspace = factory.workspace
    workspace._init_build_dir(out_of_source=True)

    outputpath = os.path.join(workspace.build_dir, outputfile)

    request = factory.gerrit.get_triggering_comment()
    parser = RequestParser(factory)
    parser.parse(request)
    actions = parser.get_actions()

    _write_actions(factory.executor, actions, outputpath)

class RequestParser(object):
    def __init__(self, factory):
        self._factory = factory
        self._workspace = factory.workspace
        self._gerrit = factory.gerrit
        self._branch = None
        self._branch_projects = { Project.GROMACS, Project.REGRESSIONTESTS }
        triggering_project = self._gerrit.get_triggering_project()
        if triggering_project and triggering_project in self._branch_projects:
            self._branch = self._gerrit.get_triggering_branch()
            self._branch_projects.remove(triggering_project)
        self._env = dict()
        self._cross_verify_info = None
        self._builds = []
        self._default_builds = []

    def parse(self, request):
        tokens = request.split()
        token = tokens[0].lower()
        if token == 'cross-verify':
            tokens.pop(0)
            self._parse_cross_verify(tokens)
        elif token == 'release-2016':
            tokens.pop(0)
            self._process_release_branch(token)
        while tokens:
            token = tokens.pop(0).lower()
            if token == 'quiet':
                self._cross_verify_info = None
            elif token == 'clang-analyzer':
                self._builds.append({ 'type': 'clang-analyzer' })
            elif token == 'coverage':
                self._builds.append({ 'type': 'coverage' })
            elif token == 'cppcheck':
                self._builds.append({ 'type': 'cppcheck' })
            elif token == 'documentation':
                self._builds.append({ 'type': 'documentation' })
            elif token == 'package':
                project = self._gerrit.get_triggering_project()
                if project is None:
                    project = Project.RELENG
                if project in (Project.GROMACS, Project.RELENG):
                    self._builds.append({ 'type': 'source-package' })
                if project in (Project.REGRESSIONTESTS, Project.RELENG):
                    self._builds.append({ 'type': 'regtest-package' })
            elif token == 'post-submit':
                self._builds.append({
                        'type': 'matrix',
                        'desc': 'post-submit',
                        'matrix-file': 'post-submit-matrix'
                    })
            elif token == 'pre-submit':
                self._builds.append({
                        'type': 'matrix',
                        'desc': 'pre-submit',
                        'matrix-file': 'pre-submit-matrix'
                    })
            elif token == 'release':
                build = { 'type': 'release', 'release_flag': False }
                if tokens and tokens[0].lower() == 'no-dev':
                    tokens.pop(0)
                    build['release_flag'] = True
                self._builds.append(build)
            elif token == 'uncrustify':
                self._builds.append({ 'type': 'uncrustify' })
            elif token == 'update':
                project = self._gerrit.get_triggering_project()
                # It can be useful to trigger these from releng for testing,
                # so we do not check for that.
                if project == Project.GROMACS:
                    raise BuildError('Update only makes sense for regressiontests changes')
                self._builds.append({ 'type': 'regressiontests-update' })
            elif token == 'update-regtest-hash':
                self._builds.append({ 'type': 'update-regtest-hash' })
            else:
                raise BuildError('Unknown request: ' + request)

    def _parse_cross_verify(self, tokens):
        triggering_project = self._gerrit.get_triggering_project()
        token = tokens.pop(0)
        change = self._gerrit.query_unique_change(token)
        project = change.project
        refspec = change.refspec
        if triggering_project and project == triggering_project:
            raise BuildError('Cross-verify is not possible with another change from the same repository')
        if project == Project.RELENG:
            raise BuildError('Cross-verify with releng changes should be initiated from the releng change in Gerrit')
        if self._branch is None:
            self._branch = change.branch
        if project in self._branch_projects:
            self._branch_projects.remove(project)
        self._gerrit.override_refspec(project, refspec)
        self._env['{0}_REFSPEC'.format(project.upper())] = refspec.fetch
        self._env['{0}_HASH'.format(project.upper())] = refspec.checkout
        self._default_builds = [{
                'type': 'matrix',
                'desc': 'cross-verify',
                'matrix-file': 'pre-submit-matrix'
            }]
        if not triggering_project or triggering_project == Project.RELENG:
            self._default_builds.extend([
                    { 'type': 'clang-analyzer', 'desc': 'cross-verify' },
                    { 'type': 'cppcheck', 'desc': 'cross-verify' },
                    { 'type': 'documentation', 'desc': 'cross-verify' },
                    { 'type': 'uncrustify', 'desc': 'cross-verify' }
                ])
        if triggering_project and change.is_open:
            self._cross_verify_info = {
                    'change': change.number,
                    'patchset': change.patchnumber
                }

    def _process_release_branch(self, branch):
        triggering_project = self._gerrit.get_triggering_project()
        if triggering_project and triggering_project != Project.RELENG:
            raise BuildError('Release branch verification only makes sense for releng changes')
        assert self._branch is None
        self._branch = branch
        spec = 'refs/heads/' + branch
        gromacs_refspec = RefSpec(spec)
        gromacs_hash = self._gerrit.get_remote_hash(Project.GROMACS, gromacs_refspec)
        gromacs_refspec = RefSpec(spec, gromacs_hash)
        self._gerrit.override_refspec(Project.GROMACS, gromacs_refspec)
        self._default_builds = [
                {
                    'type': 'matrix',
                    'desc': branch,
                    'matrix-file': 'pre-submit-matrix'
                },
                { 'type': 'clang-analyzer', 'desc': branch },
                { 'type': 'cppcheck', 'desc': branch },
                { 'type': 'documentation', 'desc': branch },
                { 'type': 'uncrustify', 'desc': branch }
            ]

    def get_actions(self):
        if self._branch and self._branch_projects:
            for project in sorted(self._branch_projects):
                spec = 'refs/heads/' + self._branch
                sha1 = self._gerrit.get_remote_hash(project, RefSpec(spec))
                self._env['{0}_REFSPEC'.format(project.upper())] = spec
                self._env['{0}_HASH'.format(project.upper())] = sha1
        if not self._builds:
            self._builds = self._default_builds
        for build in self._builds:
            build_type = build['type']
            if build_type == 'matrix':
                self._workspace._checkout_project(Project.GROMACS)
                configs = get_build_configs(self._factory, build['matrix-file'])
                del build['matrix-file']
                build['options'] = get_options_string(configs)
            elif build_type == 'update-regtest-hash':
                self._workspace._checkout_project(Project.GROMACS)
                build_script_path = self._workspace._resolve_build_input_file('get-version-info', '.py')
                script = BuildScript(self._factory.executor, build_script_path)
                context = self._factory.create_context(JobType.GERRIT, None, None)
                assert not script.build_opts
                assert not script.build_out_of_source
                assert not script.extra_options
                assert not script.extra_projects
                self._workspace._init_build_dir(False)
                script.do_build(context, self._factory.cwd)
                version, md5sum = context._get_version_info()
                build['version'] = version
                build['md5sum'] = md5sum
        result = { 'builds': self._builds }
        if self._env:
            result['env'] = self._env
        if self._cross_verify_info:
            result['gerrit_info'] = self._cross_verify_info
            number = self._cross_verify_info['change']
            patchnumber = self._cross_verify_info['patchset']
            self._gerrit.post_cross_verify_start(number, patchnumber)
        return result

def _write_actions(executor, actions, path):
    executor.write_file(path, json.dumps(actions))

def do_post_build(factory, inputfile, outputfile):
    executor = factory.executor
    data = json.loads(''.join(executor.read_file(inputfile)))

    workspace = factory.workspace
    workspace._init_build_dir(out_of_source=True)
    outputpath = os.path.join(workspace.build_dir, outputfile)

    build_messages = _get_build_messages(data)
    url, reason = None, None
    if len(data['builds']) == 1:
        url, reason = _get_single_url_and_reason(data)
    elif build_messages:
        reason = '\n'.join(build_messages)
    _write_message_json(executor, outputpath, url, reason)
    if data.has_key('gerrit_info') and data['gerrit_info']:
        gerrit_info = data['gerrit_info']
        change = gerrit_info['change']
        patchset = gerrit_info['patchset']
        factory.gerrit.post_cross_verify_finish(change, patchset, build_messages)

def _get_build_messages(data):
    builds = data['builds']
    return [_get_message(x) for x in builds]

def _get_message(build):
    message = '{0}: {1}'.format(_get_title(build), build['result'])
    if build.has_key('reason') and build['reason']:
        message += ' <<<\n' + build['reason'].rstrip() + '\n>>>'
    return message

def _get_title(build):
    title = _get_url(build)
    if not title:
        title = build['title']
    return _append_desc(title, build)

def _get_url(build):
    if build.has_key('url') and build['url']:
        return build['url']
    return None

def _append_desc(text, build):
    if text and build.has_key('desc') and build['desc']:
        text += ' ({0})'.format(build['desc'])
    return text

def _get_single_url_and_reason(data):
    build = data['builds'][0]
    url = _append_desc(_get_url(build), build)
    reason = None
    if build.has_key('reason') and build['reason']:
        reason = build['reason'].rstrip()
    return url, reason

def _write_message_json(executor, path, url, reason):
    data = {
            'url': url,
            'message': reason
        }
    executor.write_file(path, json.dumps(data))
