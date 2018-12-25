def checkoutDefaultProject()
{
    def project = this.defaultProject
    def refspec = this.defaultProjectRefspec
    checkout scm: [$class: 'GitSCM',
        branches: [[name: refspec]],
        doGenerateSubmoduleConfigurations: false,
        extensions: [
            [$class: 'RelativeTargetDirectory', relativeTargetDir: project],
            [$class: 'CleanCheckout'],
            [$class: 'BuildChooserSetting', buildChooser: [$class: 'GerritTriggerBuildChooser']]],
        submoduleCfg: [],
        userRemoteConfigs: [[refspec: refspec,
            url: "ssh://jenkins@gerrit.gromacs.org/${project}.git"]]]
}

@NonCPS
def currentBuildParametersForJenkins()
{
    def parameters = []
    parameters = addBuildParameterIfExists(parameters, 'GROMACS_REFSPEC')
    parameters = addBuildParameterIfExists(parameters, 'GROMACS_HASH')
    parameters = addBuildParameterIfExists(parameters, 'REGRESSIONTESTS_REFSPEC')
    parameters = addBuildParameterIfExists(parameters, 'REGRESSIONTESTS_HASH')
    parameters = addBuildParameterIfExists(parameters, 'RELENG_REFSPEC')
    parameters = addBuildParameterIfExists(parameters, 'RELENG_HASH')
    // We cannot forward the Gerrit Trigger parameters, because of SECURITY-170.
    // Instead, they are dealt with in initBuildRevisions() such that the
    // project-specific REFSPEC parameters contain the correct references.
    // Passing CHECKOUT_PROJECT allows the Changes section work properly.
    parameters += [$class: 'StringParameterValue', name: 'CHECKOUT_PROJECT', value: defaultProject]
    return parameters
}

@NonCPS
def addBuildParameterIfExists(parameters, name)
{
    // TODO: Consider managing the parameters for child build in a separate
    // data structure from the environment variables for the current workflow.
    if (env."$name") {
        parameters += [$class: 'StringParameterValue', name: name, value: env."$name"]
    }
    return parameters
}

def runRelengScript(contents, propagate = true)
{
    def checkoutScript = """\
        import os
        import subprocess
        if not os.path.isdir('releng'):
            os.makedirs('releng')
        os.chdir('releng')
        subprocess.check_call(['git', 'init'])
        subprocess.check_call(['git', 'fetch',
            'ssh://jenkins@gerrit.gromacs.org/releng.git', os.environ['RELENG_REFSPEC']])
        subprocess.check_call(['git', 'checkout', '-qf', os.environ['RELENG_HASH']])
        subprocess.check_call(['git', 'clean', '-ffdxq'])
        subprocess.check_call(['git', 'gc'])
        os.chdir('..')
        """
    runRelengScriptInternal(checkoutScript, contents, propagate)
}

def runRelengScriptNoCheckout(contents, propagate = true)
{
    runRelengScriptInternal('', contents, propagate)
}

def runRelengScriptInternal(prepareScript, contents, propagate)
{
    def statusFile = 'logs/status.json'
    def script = """\
        import os
        import sys
        try:
            os.remove('${statusFile}')
        except:
            pass
        os.environ['STATUS_FILE'] = '${statusFile}'
        """.stripIndent()
    if (!propagate) {
        script += "os.environ['NO_PROPAGATE_FAILURE'] = '1'\n"
    }
    script += prepareScript.stripIndent()
    script += "sys.path.append(os.path.abspath('releng'))\n"
    script += "import releng\n"
    script += contents.stripIndent()
    try {
        def returncode = runPythonScript(script)
        if (isAbortCode(returncode)) {
            return [ 'result': 'ABORTED', 'reason': null ]
        }
        if (returncode != 0) {
            throw new hudson.AbortException("releng script exited with ${returncode}")
        }
    } catch (err) {
        handleRelengError(statusFile)
        throw err
    }
    def status = readJsonFile(statusFile)
    if (propagate) {
        processRelengStatus(status)
    }
    return status
}

def runPythonScript(contents)
{
    writeFile file: 'build.py', text: contents
    def returncode = sh script: 'python build.py', returnStatus: true
    return returncode
}

def isAbortCode(returncode)
{
    // Currently, this we do not support this on Windows (not in
    // runPythonScript() either), where the code seems to be -1 for
    // aborting.
    return returncode == 137 || returncode == 143;
}

def handleRelengError(statusFile)
{
    def reason = null
    if (fileExists(statusFile)) {
        reason = readJsonFile(statusFile).reason
        setGerritReview unsuccessfulMessage: reason
    }
    addRelengErrorSummary(reason)
}

def addRelengErrorSummary(reason)
{
    def summary = manager.createSummary('error')
    summary.appendText("""\
        Unexpected failure in releng Python script:
        <pre>
        """.stripIndent(), false)
    if (reason) {
        summary.appendText(reason, true)
    } else {
        summary.appendText('Not available. See console log.', true)
    }
    summary.appendText("</pre>", false)
}

def processRelengStatus(status)
{
    if (!isRelengStatusSuccess(status) && status.reason) {
        def summary = manager.createSummary('empty')
        summary.appendText("<pre>\n",false)
        summary.appendText(status.reason, true)
        summary.appendText("</pre>", false)
        setGerritReview unsuccessfulMessage: status.reason
    }
    combineResultToCurrentBuild(status.result)
}

def isRelengStatusSuccess(status)
{
    return status.result == 'SUCCESS'
}

def combineResultToCurrentBuild(result)
{
    if (currentBuild.resultIsBetterOrEqualTo(result)) {
        currentBuild.setResult(result)
    }
}

def initBuildRevisions(defaultProject)
{
    // Information is returned as a list of projects:
    //   [
    //     {
    //       project: ...,
    //       branch: ...,
    //       refspec: ...,
    //       hash: ...,
    //       title: ...,
    //       refspec_env: ...,
    //       hash_env: ...
    //     },
    //     ...
    //   ]
    def status = runRelengScriptNoCheckout("""\
        releng.get_build_revisions()
        """)
    def revisionList = status.return_value
    setRevisionsToEnv(revisionList)
    addBuildRevisionsSummary(revisionList)
    if (params.GERRIT_PROJECT) {
        this.defaultProject = params.GERRIT_PROJECT
        this.defaultProjectRefspec = params.GERRIT_REFSPEC
    } else {
        this.defaultProject = defaultProject
        this.defaultProjectRefspec = env."${defaultProject.toUpperCase()}_REFSPEC"
    }
    return revisionListToRevisionMap(revisionList)
}

@NonCPS
def setRevisionsToEnv(revisionList)
{
    // Set refspec env variables to the actual refspecs so that they can be
    // used as build parameters.
    revisionList.each { env."${it.refspec_env}" = it.refspec }
    revisionList.each { env."${it.hash_env}" = it.hash }
}

def addBuildRevisionsSummary(revisionList)
{
    def text = """\
        Built revisions:
        <table>
        """.stripIndent()
    for (def rev : revisionList) {
        text += """\
            <tr>
              <td>${rev.project}:</td>
              <td>${rev.refspec}</td>
              <td>(${rev.branch})</td>
              <td>${rev.hash}</td>
            </tr>
            """.stripIndent()
        if (rev.title) {
            text += """\
                <tr>
                  <td />
                  <td colspan=3>${rev.title}</td>
                </tr>
                """.stripIndent()
        }
    }
    text += "</table>"
    manager.createSummary('notepad').appendText(text, false)
}

@NonCPS
def revisionListToRevisionMap(revisionList)
{
    return revisionList.collectEntries { [(it.project): it] }
}

def processBuildScriptConfig(script)
{
    // Information is returned as if a single matrix configuration:
    //   {
    //     opts: [...],
    //     host: ...,
    //     labels: ...
    //   }
    def status = runRelengScriptNoCheckout("""\
        releng.read_build_script_config('${script}')
        """)
    return status.return_value
}

def processMatrixConfigs(filename)
{
    // Information is returned as a list of configurations and as a string
    // suitable as a dynamic axis in a matrix build:
    //   {
    //     configs: [
    //       {
    //         opts: [...],
    //         host: ...,
    //         labels: ...
    //       },
    //       ...
    //    ],
    //    as_axis: ...
    //  }
    def status = runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}')
        """)
    return status.return_value
}

def processMatrixResults(matrix, bld)
{
    def data = [ 'matrix': matrix, 'build_url': bld.absoluteUrl ]
    writeJsonFile('build/matrix.json', data)
    def status = runRelengScript("""\
        releng.process_multi_configuration_build_results('build/matrix.json')
        """, false)
    processRelengStatus(status)
}

def readSourceVersion()
{
    // Information is returned as:
    //   {
    //     version: ...,
    //     regressiontestsMd5sum: ...
    //   }
    def status = runRelengScriptNoCheckout("""\
        releng.read_source_version_info()
        """)
    return status.return_value
}

@NonCPS
def setCombinedBuildResult(results)
{
    def combinedResult = hudson.model.Result.SUCCESS
    for (def resultStr : results) {
        def result = hudson.model.Result.fromString(resultStr)
        combinedResult = combinedResult.combine(result)
    }
    currentBuild.setResult(combinedResult.toString())
    return combinedResult.isBetterOrEqualTo(hudson.model.Result.SUCCESS)
}

def readPropertyFile(path)
{
    def contents = readFile path
    return parseProperties(contents)
}

@NonCPS
def parseProperties(contents)
{
    def map = [:]
    def props = new Properties()
    props.load(new StringReader(contents))
    for (def name : props.stringPropertyNames())
        map.put(name, props.getProperty(name));
    return map
}

def readJsonFile(path)
{
    def contents = readFile path
    return parseJson(contents)
}

@NonCPS
def parseJson(contents)
{
    def slurper = new groovy.json.JsonSlurperClassic()
    return slurper.parseText(contents)
}

def writeJsonFile(path, obj)
{
    def contents = toJsonString(obj)
    writeFile file: path, text: contents
}

@NonCPS
def toJsonString(obj)
{
    def builder = new groovy.json.JsonBuilder(obj)
    return builder.toPrettyString()
}

return this
