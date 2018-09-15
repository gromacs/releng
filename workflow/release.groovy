utils = load 'releng/workflow/utils.groovy'
packaging = load 'releng/workflow/packaging.groovy'
utils.setEnvForReleng('releng')
utils.checkoutDefaultProject()
buildRevisions = utils.readBuildRevisions()
testMatrix = utils.processMatrixConfigs('release-matrix.txt')
sourceVersionInfo = utils.readSourceVersion()

RELEASE = (RELEASE == 'true')
FORCE_REPACKAGING = (FORCE_REPACKAGING == 'true')

def doBuild(sourcePackageJob, regressiontestsPackageJob)
{
    def tarballBuilds = [
            gromacs: [ dir: 'gromacs', revision: buildRevisions.gromacs, jobName: sourcePackageJob ],
            regressiontests: [ dir: 'regressiontests', revision: buildRevisions.regressiontests, jobName: regressiontestsPackageJob ]
        ]
    tarballBuilds = getOrGenerateTarballs(tarballBuilds)
    if (!tarballBuilds) {
        return
    }
    setTarballEnvironmentVariablesForReleng()
    if (testTarballs(tarballBuilds, testMatrix)) {
        createWebsitePackage(tarballBuilds)
    }
}

def getOrGenerateTarballs(builds)
{
    builds = getExistingTarballBuilds(builds)
    builds.regressiontests = getOrTriggerTarballBuild(builds.regressiontests, sourceVersionInfo.version)
    def sourceMd5 = sourceVersionInfo.regressiontestsMd5sum
    if (builds.regressiontests.md5sum != sourceMd5) {
        echo "Regressiontests MD5 mismatch:\n" +
             "source:  ${sourceMd5}\n" +
             "tarball: ${builds.regressiontests.md5sum}"
        if (RELEASE) {
            // TODO: Currently, there is no easy way to pass back failure message
            // from on-demand builds.
            // setGerritReview unsuccessfulReason: "Regression test MD5 in source code is incorrect"
            def summary = manager.createSummary('error')
            summary.appendText("Regression test MD5 in source code (${sourceMd5}) does not match the regressiontests tarball", true)
            currentBuild.setResult("FAILURE")
            return null
        }
    }
    builds.gromacs = getOrTriggerTarballBuild(builds.gromacs)
    return builds
}

def getExistingTarballBuilds(builds)
{
    node('pipeline-general') {
        builds.gromacs = getExistingBuild(builds.gromacs)
        builds.regressiontests = getExistingBuild(builds.regressiontests)
    }
    return builds
}

def getExistingBuild(buildInfo)
{
    def newInfo = packaging.getPackageInfo(buildInfo.dir, buildInfo.jobName, buildInfo.buildNumber)
    newInfo.dir = buildInfo.dir
    newInfo.revision = buildInfo.revision
    newInfo.jobName = buildInfo.jobName
    return newInfo
}

def getOrTriggerTarballBuild(buildInfo, version = null)
{
    if (!FORCE_REPACKAGING && existingBuildIsValid(buildInfo, version)) {
        addTarballSummary(buildInfo, false)
        return buildInfo
    }
    def parameters = utils.currentBuildParametersForJenkins()
    if (version) {
        parameters += [$class: 'StringParameterValue', name: 'PACKAGE_VERSION_STRING', value: version]
    }
    parameters += [$class: 'BooleanParameterValue', name: 'RELEASE', value: RELEASE]
    def packagingBuild = build job: buildInfo.jobName, parameters: parameters
    buildInfo.buildNumber = packagingBuild.number.toString()
    node('pipeline-general') {
        buildInfo = getExistingBuild(buildInfo)
    }
    addTarballSummary(buildInfo, true)
    return buildInfo
}

def existingBuildIsValid(buildInfo, version)
{
    def infoMessage = "Existing ${buildInfo.jobName} build ${buildInfo.buildNumber}"
    infoMessage += "\n  Version: ${buildInfo.version}"
    if (version) {
        infoMessage += "  Expected: ${version}"
    }
    infoMessage += "\n  Release: ${buildInfo.isRelease}  Expected: ${RELEASE}"
    infoMessage += "\n  HEAD:    ${buildInfo.props.HEAD_HASH}  Expected: ${buildInfo.revision.hash}"
    echo infoMessage
    def versionMatches = (buildInfo.isRelease == RELEASE)
    if (versionMatches && version) {
        versionMatches = (version == buildInfo.version)
    }
    return (versionMatches && buildInfo.revision.hash == buildInfo.props.HEAD_HASH)
}

def addTarballSummary(buildInfo, wasTriggered)
{
    def title = (buildInfo.dir == 'gromacs' ? "Source package" : "Regression tests")
    def jobUrl = "${env.JENKINS_URL}/job/${buildInfo.jobName}"
    def buildUrl = "${jobUrl}/${buildInfo.buildNumber}"
    def buildStatus = (wasTriggered ? "triggered" : "reused existing")
    def text = """\
        <table>
          <tr>
            <td><b>${title}</b>:</td>
            <td>${buildInfo.packageFileName}</td>
          </tr>
          <tr>
            <td>Build:</td>
            <td>
              <a href="${jobUrl}">${buildInfo.jobName}</a> build
              <a href="${buildUrl}">${buildInfo.buildNumber}</a>
              (${buildStatus})
            </td>
          </tr>
          <tr>
            <td>MD5 sum:</td>
            <td>${buildInfo.md5sum}</td>
          </tr>
        </table>
        """.stripIndent()
    manager.createSummary('package').appendText(text, false)
}

def setTarballEnvironmentVariablesForReleng()
{
    env.GROMACS_REFSPEC = 'tarballs/gromacs'
    env.REGRESSIONTESTS_REFSPEC = 'tarballs/regressiontests'
}

def testTarballs(tarballBuilds, testMatrix)
{
    def tasks = testMatrix.configs.collectEntries {
        [(it.opts): { runSingleTestConfig(tarballBuilds, it) }]
    }
    parallel tasks
    addConfigurationSummary(testMatrix.configs)
    return setBuildResult(testMatrix.configs)
}

def runSingleTestConfig(tarballBuilds, config)
{
    // TODO: This should be config.labels, once Jenkins has all the labels
    // defined matching agents.py.
    node(config.host) {
        config.host = env.NODE_NAME
        getTarball(tarballBuilds.gromacs)
        getTarball(tarballBuilds.regressiontests)
        def opts = config.opts.clone()
        opts.add('out-of-source')
        def pythonOpts = listAsPythonList(opts)
        // TODO: Timeout.
        timestamps {
            config.status = utils.runRelengScript("""\
                releng.run_build('gromacs', releng.JobType.RELEASE, ${pythonOpts})
                """, false)
        }
    }
}

def getTarball(buildInfo)
{
    packaging.getPackageArtifacts(buildInfo.dir, buildInfo.jobName, buildInfo.buildNumber, true)
}

def getTarballInfo(buildInfo)
{
    packaging.getPackageArtifacts(buildInfo.dir, buildInfo.jobName, buildInfo.buildNumber, false)
}

@NonCPS
def listAsPythonList(list)
{
    def items = list.collect { "'${it}'" }.join(', ')
    return "[ ${items} ]"
}

def addConfigurationSummary(testConfigs)
{
    def text = """\
        <table>
          <tr>
            <td><b>Tested Configurations</b></td>
            <td>Host</td>
            <td>Result</td>
          </tr>
        """.stripIndent()
    for (def config : testConfigs) {
        def opts = config.opts.join(' ')
        text += """\
            <tr>
              <td>${opts}</td>
              <td>${config.host}</td>
              <td>${config.status.result}</td>
            </tr>
            """.stripIndent()
        if (config.status.reason) {
            text += """\
                <tr>
                  <td />
                  <td colspan=2>
                    <pre>
                """.stripIndent()
            text += config.status.reason
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

@NonCPS
def setBuildResult(testConfigs)
{
    return utils.setCombinedBuildResult(testConfigs.collect { it.status.result })
}

def createWebsitePackage(tarballBuilds)
{
    node('doxygen') {
        wrap([$class: 'TimestamperBuildWrapper']) {
            getTarball(tarballBuilds.gromacs)
            getTarballInfo(tarballBuilds.regressiontests)
            utils.runRelengScript("""\
                releng.run_build('documentation', releng.JobType.RELEASE, ['source-md5=${tarballBuilds.gromacs.md5sum}'])
                """)
            publishHTML(target: [allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'build/docs/html', reportFiles: 'index.html', reportName: 'Website'])
            if (RELEASE) {
                archive 'gromacs/build/website-*.tar.gz'
            }
        }
    }
    def text = "Documentation for website was built"
    if (RELEASE) {
        text += " and archived as an artifact"
    }
    text += ".\n"
    text += """\
        The HTML pages from the last successful build can be accessed
        at the Jenkins project level:<br />
        <a href="${env.JOB_URL}/Website">Website from last successful build</a>
        """.stripIndent()
    manager.createSummary('graph').appendText(text, false)
}

return this
