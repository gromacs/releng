// TODO: Consider what's the best place to have knowledge of these build names.
coverageJobName = 'Coverage_Gerrit_master-new-releng'
matrixJobName = 'Gromacs_Gerrit_master_nwrpo'
regtestPackageJobName = 'Regressiontests_package_master'
releaseJobName = 'Release_workflow_master'
sourcePackageJobName = 'Source_package_master'

utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('releng')
actions = processTriggeringCommentAndGetActions()
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
    setGerritOutput(builds)
}

@NonCPS
def getBuildersMap()
{
    return [
            'coverage': this.&doCoverage,
            'matrix': this.&doMatrix,
            'regtest-package': this.&doRegressionTestsPackage,
            'release': this.&doReleaseWorkflow,
            'source-package': this.&doSourcePackage,
        ]
}

def doCoverage(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    bld.jobName = coverageJobName
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

def setGerritOutput(builds)
{
    def messages = doPostBuildActions(builds)
    setGerritReview customUrl: messages.url, unsuccessfulMessage: messages.message
}

def doPostBuildActions(builds)
{
    def data = [
            'builds': getBuildInfoForReleng(builds)
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
