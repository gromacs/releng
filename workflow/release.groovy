utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('releng')
utils.checkoutDefaultProject()
buildRevisions = utils.readBuildRevisions()
testConfigs = utils.processMatrixConfigs('release-matrix.txt')

RELEASE = (RELEASE == 'true')
FORCE_REPACKAGING = (FORCE_REPACKAGING == 'true')

def doBuild(sourcePackageJob, regressiontestsPackageJob)
{
    def tarballBuilds = [
            gromacs: [ dir: 'gromacs', revision: buildRevisions.gromacs, jobName: sourcePackageJob ],
            regressiontests: [ dir: 'regressiontests', revision: buildRevisions.regressiontests, jobName: regressiontestsPackageJob ]
        ]
    tarballBuilds = getOrGenerateTarballs(tarballBuilds)
    utils.setEnvForRelengSecondaryCheckouts()
    setTarballEnvironmentVariablesForReleng()
    if (testTarballs(tarballBuilds, testConfigs)) {
        createWebsitePackage(tarballBuilds)
    }
}

def getOrGenerateTarballs(builds)
{
    builds = getExistingTarballBuilds(builds)
    // TODO: If we could extract the source package version earlier
    // we could trigger the regressiontests tarball build first,
    // and then test in the source packaging build that the MD5
    // matches.  That would avoid potentially unnecessary tarball
    // builds in the process.
    builds.gromacs = getOrTriggerTarballBuild(builds.gromacs)
    builds.regressiontests = getOrTriggerTarballBuild(builds.regressiontests, builds.gromacs.version)
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
    getPackageArtifacts(buildInfo)
    return createBuildInfoFromPackageInfo(buildInfo)
}

def getPackageArtifacts(buildInfo, withTarball = false)
{
    def filter = null
    if (!withTarball) {
        filter = '**/package-info.log'
    }
    if (buildInfo.buildNumber) {
        step([$class: 'CopyArtifact', projectName: buildInfo.jobName,
              selector: [$class: 'SpecificBuildSelector', buildNumber: buildInfo.buildNumber],
              filter: filter, target: "tarballs/${buildInfo.dir}",
              fingerprintArtifacts: true, flatten: true])
    } else {
        step([$class: 'CopyArtifact', projectName: buildInfo.jobName,
              filter: filter, target: "tarballs/${buildInfo.dir}",
              fingerprintArtifacts: true, flatten: true])
    }
}

def createBuildInfoFromPackageInfo(buildInfo)
{
    def props = utils.readPropertyFile("tarballs/${buildInfo.dir}/package-info.log")
    def version = props.PACKAGE_VERSION
    return [
            dir: buildInfo.dir,
            revision: buildInfo.revision,
            jobName: buildInfo.jobName,
            buildNumber: props.BUILD_NUMBER,
            version: stripDevSuffix(version),
            isRelease: !version.endsWith('-dev'),
            md5sum: props.MD5SUM,
            props: props
        ]
}

def stripDevSuffix(version) {
    def match = version =~ /(.*)-dev$/
    if (match) {
        version = match.group(1)
    }
    return version
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
            <td>${buildInfo.props.PACKAGE_FILE_NAME}</td>
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

def testTarballs(tarballBuilds, testConfigs)
{
    def tasks = [:]
    for (int i = 0; i != testConfigs.size(); ++i) {
        def config = testConfigs[i]
        tasks[config.opts] = {
            runSingleTestConfig(tarballBuilds, config)
        }
    }
    parallel tasks
    addConfigurationSummary(testConfigs)
    return setBuildResult(testConfigs)
}

def runSingleTestConfig(tarballBuilds, config)
{
    // TODO: This should be config.labels, once Jenkins has all the labels
    // defined matching slaves.py.
    node(config.host) {
        config.host = env.NODE_NAME
        getPackageArtifacts(tarballBuilds.gromacs, true)
        getPackageArtifacts(tarballBuilds.regressiontests, true)
        def opts = config.opts.clone()
        opts.add('out-of-source')
        def pythonOpts = listAsPythonList(opts)
        // TODO: Timeout.
        timestamps {
            // TODO: Add a test somewhere that ensures that for a release
            // build, the MD5 sum specified in the source repository matches
            // the regression tests tarball.
            config.status = utils.runRelengScript("""\
                releng.run_build('gromacs', releng.JobType.RELEASE, ${pythonOpts})
                """, false)
        }
    }
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
    for (int i = 0; i != testConfigs.size(); ++i) {
        def config = testConfigs[i]
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
            getPackageArtifacts(tarballBuilds.gromacs, true)
            getPackageArtifacts(tarballBuilds.regressiontests)
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
