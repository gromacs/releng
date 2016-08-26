// TODO: Consider what's the best place to have knowledge of these build names.
clangAnalyzerJobName = 'clang-static-analyzer_Gerrit_master-workflow'
coverageJobName = 'Coverage_Gerrit_master-new-releng'
cppcheckJobName = 'cppcheck_Gerrit_master-new-releng'
documentationJobName = 'Documentation_Gerrit_master-new-releng'
matrixJobName = 'Gromacs_Gerrit_master_nrwpo'
regtestPackageJobName = 'Regressiontests_package_master'
releaseJobName = 'Release_workflow_master'
sourcePackageJobName = 'Source_package_master'
uncrustifyJobName = 'uncrustify_master-new-releng'

utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('releng')
actions = processTriggeringCommentAndGetActions()
setEnvFromActions(actions.env)
utils.checkoutDefaultProject()
utils.readBuildRevisions()

def processTriggeringCommentAndGetActions()
{
    env.MANUAL_COMMENT_TEXT = MANUAL_COMMENT_TEXT
    utils.runRelengScriptNoCheckout("""\
        releng.get_actions_from_triggering_comment('actions.json')
        """)
    return utils.readJsonFile('build/actions.json')
}

@NonCPS
def setEnvFromActions(overrides)
{
    if (!overrides) {
        return
    }
    overrides.each {
        key, value -> env."$key" = value
    }
}

def doBuild()
{
    def builds = actions.builds
    def tasks = [:]
    def builders = getBuildersMap()
    for (int i = 0; i != builds.size(); ++i) {
        def bld = builds[i]
        tasks[bld.type] = { builders[bld.type](bld) }
    }
    parallel tasks
    setBuildResult(builds)
    addSummaryForTriggeredBuilds(builds)
    setGerritOutput(builds, actions.gerrit_info)
}

@NonCPS
def getBuildersMap()
{
    return [
            'clang-analyzer': this.&doClangAnalyzer,
            'coverage': this.&doCoverage,
            'cppcheck': this.&doCppCheck,
            'documentation': this.&doDocumentation,
            'matrix': this.&doMatrix,
            'regtest-package': this.&doRegressionTestsPackage,
            'release': this.&doReleaseWorkflow,
            'source-package': this.&doSourcePackage,
            'uncrustify': this.&doUncrustify,
        ]
}

def doClangAnalyzer(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = clangAnalyzerJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doCoverage(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = coverageJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doCppCheck(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = cppcheckJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doDocumentation(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = documentationJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doMatrix(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'StringParameterValue', name: 'OPTIONS', value: bld.options]
    bld.jobName = matrixJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doRegressionTestsPackage(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'StringParameterValue', name: 'PACKAGE_VERSION_STRING', value: 'master']
    parameters += [$class: 'BooleanParameterValue', name: 'RELEASE', value: false]
    bld.jobName = regtestPackageJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doReleaseWorkflow(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'BooleanParameterValue', name: 'FORCE_REPACKAGING', value: false]
    parameters += [$class: 'BooleanParameterValue', name: 'RELEASE', value: false]
    bld.jobName = releaseJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doSourcePackage(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'BooleanParameterValue', name: 'RELEASE', value: false]
    bld.jobName = sourcePackageJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

def doUncrustify(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = uncrustifyJobName
    bld.build = build job: bld.jobName, parameters: parameters, propagate: false
}

@NonCPS
def setBuildResult(builds)
{
    utils.setCombinedBuildResult(builds.collect { it.build.result })
}

def addSummaryForTriggeredBuilds(builds)
{
    def text = """\
        Builds:
        <table>
        """.stripIndent()
    // TODO: Add handling for unsuccessful-reason.log from the child builds
    // (also for the message posted back to Gerrit below).
    for (int i = 0; i != builds.size(); ++i) {
        def bld = builds[i]
        text += """\
            <tr>
              <td>${bld.jobName}</td>
              <td><a href="${bld.build.absoluteUrl}">#${bld.build.number}</a></td>
            </tr>
            """.stripIndent()
    }
    text += "</table>"
    manager.createSummary('empty').appendText(text, false)
}

def setGerritOutput(builds, gerrit_info)
{
    def messages = doPostBuildActions(builds, gerrit_info)
    setGerritReview customUrl: messages.url, unsuccessfulMessage: messages.message
}

def doPostBuildActions(builds, gerrit_info)
{
    def data = [
            'builds': getBuildInfoForReleng(builds),
            'gerrit_info': gerrit_info
        ]
    def messages
    node('pipeline-general') {
        utils.writeJsonFile('build/actions.json', data)
        utils.runRelengScript("""\
            releng.do_ondemand_post_build('build/actions.json', 'message.json')
            """)
        messages = utils.readJsonFile('build/message.json')
    }
    return messages
}

@NonCPS
def getBuildInfoForReleng(builds)
{
    return builds.collect {
            [ 'url': it.build.absoluteUrl, 'desc': it.desc, 'result': it.build.result ]
        }
}

return this
