// TODO: Consider what's the best place to have knowledge of these build names.
// TODO: Do more of these actions as part of this workflow, instead of a separate build.
clangAnalyzerJobName = 'clang_static_analyzer_PreSubmit'
coverageJobName = 'Coverage_OnDemand'
documentationJobName = 'Documentation_PreSubmit'
matrixJobName = 'Matrix_OnDemand'
releaseJobName = 'Release_workflow_master'
uncrustifyJobName = 'uncrustify_PreSubmit'

utils = load 'releng/workflow/utils.groovy'
packaging = load 'releng/workflow/packaging.groovy'
utils.setEnvForReleng('releng')
actions = processTriggeringCommentAndGetActions()
setEnvFromActions(actions.env)
utils.checkoutDefaultProject()
utils.readBuildRevisions()

def processTriggeringCommentAndGetActions()
{
    env.MANUAL_COMMENT_TEXT = MANUAL_COMMENT_TEXT
    // Information is returned as
    //   {
    //     builds: [
    //       {
    //         type: ...,
    //         // values specific to build type
    //       },
    //       ...
    //     ],
    //     env: {
    //       ...
    //     },
    //     gerrit_info: {
    //       // opaque data passed back to do_ondemand_post_build()
    //     }
    //   }
    def status = utils.runRelengScriptNoCheckout("""\
        releng.get_actions_from_triggering_comment()
        """)
    return status.return_value
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
    def builders = getBuildersMap()
    def tasks = builds.collectEntries {
        [(it.type): { builders[it.type](it) }]
    }
    parallel tasks
    setBuildResult(builds)
    def messages = doPostBuildActions(builds, actions.gerrit_info)
    addSummaryForTriggeredBuilds(builds)
    if (messages) {
        setGerritReview customUrl: messages.url, unsuccessfulMessage: messages.message
    }
}

@NonCPS
def getBuildersMap()
{
    return [
            'clang-analyzer': this.&doClangAnalyzer,
            'coverage': this.&doCoverage,
            'documentation': this.&doDocumentation,
            'matrix': this.&doMatrix,
            'regtest-package': this.&doRegressionTestsPackage,
            'release': this.&doReleaseWorkflow,
            'source-package': this.&doSourcePackage,
            'uncrustify': this.&doUncrustify,
            'update-regtest-hash': this.&doUpdateRegressionTestsHash,
            'regressiontests-update': this.&doRegressiontestsUpdate
        ]
}

def doClangAnalyzer(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    doChildBuild(bld, clangAnalyzerJobName, parameters)
}

def doCoverage(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    doChildBuild(bld, coverageJobName, parameters)
}

def doDocumentation(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    doChildBuild(bld, documentationJobName, parameters)
}

def doMatrix(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'StringParameterValue', name: 'OPTIONS', value: bld.matrix.as_axis]
    doChildBuild(bld, matrixJobName, parameters)
}

def doRegressionTestsPackage(bld)
{
    bld.title = 'Regressiontests package'
    createRegressionTestsPackage(bld, bld.version, false)
}

def createRegressionTestsPackage(bld, version, release)
{
    def packageInfo = null
    node('bs_mic') {
        timestamps {
            timeout(20) {
                bld.status = utils.runRelengScript("""\
                    import os
                    os.environ['PACKAGE_VERSION_STRING'] = '${version}'
                    os.environ['RELEASE'] = '${release}'
                    releng.run_build('package', releng.JobType.GERRIT, None, project=releng.Project.REGRESSIONTESTS)
                    """, false)
            }
        }
        if (utils.isRelengStatusSuccess(bld.status)) {
            packageInfo = packaging.readPackageInfo('logs/package-info.log')
        }
    }
    bld.summary = packaging.createPackagingSummaryText(bld.status, packageInfo)
    return packageInfo
}

def doReleaseWorkflow(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'BooleanParameterValue', name: 'FORCE_REPACKAGING', value: false]
    parameters += [$class: 'BooleanParameterValue', name: 'RELEASE', value: bld.release_flag]
    doChildBuild(bld, releaseJobName, parameters)
}

def doSourcePackage(bld)
{
    bld.title = 'Source package'
    node('doxygen') {
        timestamps {
            timeout(45) {
                bld.status = utils.runRelengScript("""\
                    import os
                    os.environ['RELEASE'] = 'false'
                    releng.run_build('source-package', releng.JobType.GERRIT, None)
                    """, false)
            }
        }
        if (utils.isRelengStatusSuccess(bld.status)) {
            def packageInfo = packaging.readPackageInfo('logs/package-info.log')
            bld.summary = packaging.createPackagingSummaryText(bld.status, packageInfo)
        }
    }
}

def doUncrustify(bld)
{
    def parameters = utils.currentBuildParametersForJenkins()
    doChildBuild(bld, uncrustifyJobName, parameters)
}

def doUpdateRegressionTestsHash(bld)
{
    bld.title = 'Regressiontests MD5 update'
    def packageInfo = createRegressionTestsPackage(bld, bld.version, true)
    if (packageInfo == null) {
        return
    }
    node('pipeline-general')
    {
        timestamps {
            timeout(20) {
                bld.status = utils.runRelengScript("""\
                    releng.run_build('update-regtest-hash', releng.JobType.GERRIT, ['md5sum=${packageInfo.md5sum}'])
                    """, false)
            }
        }
        bld.summary += "<p>Update: ${bld.status.result}</p>"
    }
}

def doRegressiontestsUpdate(bld)
{
    bld.title = 'Regressiontests update'
    node('bs_nix-amd')
    {
        timestamps {
            timeout(45) {
                bld.status = utils.runRelengScript("""\
                    releng.run_build('regressiontests-update', releng.JobType.GERRIT, ['build-jobs=4'])
                    """, false)
            }
        }
    }
}

def doChildBuild(bld, jobName, parameters)
{
    bld.title = jobName
    def childBuild = build job: jobName, parameters: parameters, propagate: false
    bld.url = childBuild.absoluteUrl
    bld.number = childBuild.number
    // TODO: Add handling for unsuccessful-reason.log from the child builds.
    bld.status = [
            'result': childBuild.result
        ]
}

@NonCPS
def setBuildResult(builds)
{
    utils.setCombinedBuildResult(builds.collect { it.status.result })
}

def addSummaryForTriggeredBuilds(builds)
{
    def text = """\
        Builds:
        <table>
        """.stripIndent()
    for (def bld : builds) {
        def summary = bld.status.result
        if (bld.summary) {
            summary = bld.summary
        }
        if (bld.url) {
            text += """\
                <tr>
                  <td>${bld.title}</td>
                  <td><a href="${bld.url}">#${bld.number}</a></td>
                  <td>${summary}</td>
                </tr>
                """.stripIndent()
        } else {
            text += """\
                <tr>
                  <td>${bld.title}</td>
                  <td/>
                  <td>${summary}</td>
                </tr>
                """.stripIndent()
        }
        if (bld.status.reason) {
            text += """\
                <tr>
                  <td />
                  <td colspan=2>
                    <pre>
                """.stripIndent()
            text += bld.status.reason
            text += """
                    </pre>
                  </td>
                </tr>
                """.stripIndent()
        }
    }
    text += "</table>"
    manager.createSummary('empty').appendText(text, false)
}

def doPostBuildActions(builds, gerrit_info)
{
    def data = [
            'builds': getBuildInfosForReleng(builds),
            'gerrit_info': gerrit_info
        ]
    def messages
    node('pipeline-general') {
        // This should not take any time, but it seems to often hang in
        // Jenkins.  If we are lucky, the one-minute timeout will actually stop
        // the build instead of leaving it running forever...
        timeout(1) {
            utils.writeJsonFile('build/actions.json', data)
            // Information is returned as
            //   {
            //     url: ...,
            //     message: ...
            //   }
            def status = utils.runRelengScript("""\
                releng.do_ondemand_post_build('build/actions.json')
                """, false)
            utils.processRelengStatus(status)
            messages = status.return_value
        }
    }
    return messages
}

@NonCPS
def getBuildInfosForReleng(builds)
{
    return builds.collect { getBuildInfoForReleng(it) }
}

@NonCPS
def getBuildInfoForReleng(bld)
{
    def info = [
            'title': bld.title,
            'url': bld.url,
            'desc': bld.desc,
            'result': bld.status.result,
            'reason': bld.status.reason
        ]
    if (bld.matrix) {
        info.matrix = bld.matrix
    }
    return info
}

return this
