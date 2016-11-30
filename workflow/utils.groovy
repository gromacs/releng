@NonCPS
def setEnvForReleng(defaultProject)
{
    setBuildParametersToEnv()
    env.CHECKOUT_PROJECT = 'releng'
    env.CHECKOUT_REFSPEC = RELENG_REFSPEC
    if (env.GERRIT_PROJECT == 'releng') {
        env.CHECKOUT_REFSPEC = GERRIT_REFSPEC
    }
    if (env.GERRIT_PROJECT) {
        this.defaultProject = env.GERRIT_PROJECT
        this.defaultProjectRefspec = env.GERRIT_REFSPEC
    } else {
        this.defaultProject = defaultProject
        this.defaultProjectRefspec = env."${defaultProject.toUpperCase()}_REFSPEC"
    }
}

@NonCPS
def setBuildParametersToEnv()
{
    // All of this should become unnecessary after we upgrade to latest
    // pipeline plugins (and we can switch in many places from using env
    // to using params, which is clearer).
    setEnvFromBindingIfExists('GROMACS_REFSPEC')
    setEnvFromBindingIfExists('GROMACS_HASH')
    setEnvFromBindingIfExists('REGRESSIONTESTS_REFSPEC')
    setEnvFromBindingIfExists('REGRESSIONTESTS_HASH')
    setEnvFromBindingIfExists('RELENG_REFSPEC')
    setEnvFromBindingIfExists('RELENG_HASH')
    if (binding.variables.containsKey('GERRIT_PROJECT')) {
        binding.variables.findAll { it.key.startsWith('GERRIT_') }.each {
            key, value -> env."$key" = value
        }
    }
}

@NonCPS
def setEnvFromBindingIfExists(name)
{
    if (binding.variables.containsKey(name)) {
        env."$name" = binding.variables."$name"
    }
}

def checkoutDefaultProject()
{
    def checkout_project = defaultProject
    def checkout_refspec = defaultProjectRefspec
    checkout scm: [$class: 'GitSCM',
        branches: [[name: checkout_refspec]],
        doGenerateSubmoduleConfigurations: false,
        extensions: [
            [$class: 'RelativeTargetDirectory', relativeTargetDir: checkout_project],
            [$class: 'CleanCheckout'],
            [$class: 'BuildChooserSetting', buildChooser: [$class: 'GerritTriggerBuildChooser']]],
        submoduleCfg: [],
        userRemoteConfigs: [[refspec: checkout_refspec,
            url: "ssh://jenkins@gerrit.gromacs.org/${checkout_project}.git"]]]
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
    // Instead, they are dealt with in readBuildRevisions() such that the
    // project-specific REFSPEC parameters contain the correct references.
    // Passing CHECKOUT_PROJECT allows the Changes section work properly.
    parameters += [$class: 'StringParameterValue', name: 'CHECKOUT_PROJECT', value: defaultProject]
    return parameters
}

@NonCPS
def addBuildParameterIfExists(parameters, name)
{
    if (env."$name") {
        parameters += [$class: 'StringParameterValue', name: name, value: env."$name"]
    }
    return parameters
}

def runPythonScript(contents)
{
    writeFile file: 'build.py', text: contents
    def returncode = sh script: 'python build.py', returnStatus: true
    return returncode
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
            'ssh://jenkins@gerrit.gromacs.org/releng.git', os.environ['CHECKOUT_REFSPEC']])
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
    def script = prepareScript.stripIndent()
    script += """\
        import os
        import sys
        os.environ['STATUS_FILE'] = 'logs/status.json'
        os.environ['WORKSPACE'] = os.getcwd()
        sys.path.append(os.path.abspath('releng'))
        import releng
        """.stripIndent()
    if (!propagate) {
        script += "os.environ['NO_PROPAGATE_FAILURE'] = '1'\n"
    }
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
        handleRelengError()
        throw err
    }
    def status = readJsonFile('logs/status.json')
    if (propagate) {
        processRelengStatus(status)
    }
    return status
}

def isAbortCode(returncode)
{
    // Currently, this we do not support this on Windows (not in
    // runPythonScript() either), where the code seems to be -1 for
    // aborting.
    return returncode == 137 || returncode == 143;
}

def handleRelengError()
{
    def reason = null
    if (fileExists('logs/status.json')) {
        reason = readJsonFile('logs/status.json').reason
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
    def result = hudson.model.Result.fromString(status.result)
    if (result.isWorseThan(hudson.model.Result.SUCCESS) && status.reason) {
        def summary = manager.createSummary('empty')
        summary.appendText("<pre>\n",false)
        summary.appendText(status.reason, true)
        summary.appendText("</pre>", false)
        setGerritReview unsuccessfulMessage: status.reason
    }
    if (currentBuild.result) {
        def prevResult = hudson.model.Result.fromString(currentBuild.result)
        result = prevResult.combine(result)
    }
    currentBuild.setResult(result.toString())
}

def isRelengStatusSuccess(status)
{
    return status.result == 'SUCCESS'
}

def readBuildRevisions()
{
    runRelengScriptNoCheckout("""\
        releng.get_build_revisions(outputfile='build-revisions.json')
        """)
    def revisionList = readJsonFile('logs/build-revisions.json')
    setRevisionsToEnv(revisionList)
    addBuildRevisionsSummary(revisionList)
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
    for (int i = 0; i != revisionList.size(); ++i) {
        def rev = revisionList[i]
        text += """\
            <tr>
              <td>${rev.project}:</td>
              <td>${rev.refspec}</td>
              <td>${rev.hash}</td>
            </tr>
            """.stripIndent()
        if (rev.title) {
            text += """\
                <tr>
                  <td />
                  <td colspan=2>${rev.title}</td>
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
    // Information is passed from the Python code using a temporary file named here.
    runRelengScriptNoCheckout("""\
        releng.read_build_script_config('${script}', outputfile='config.json')
        """)
    return readJsonFile('build/config.json')
}

def processMatrixConfigsToBuildAxis(filename)
{
    // Information is passed from the Python code using a temporary file named here.
    runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}', outputfile='matrix.txt')
        """)
    return readPropertyFile('build/matrix.txt').OPTIONS
}

def processMatrixConfigs(filename)
{
    // Information is passed from the Python code using a temporary file named here.
    runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}', outputfile='matrix.json')
        """)
    return readJsonFile('build/matrix.json')
}

def readSourceVersion()
{
    // Information is passed from the Python code using a temporary file named here.
    runRelengScriptNoCheckout("""\
        releng.read_source_version_info(outputfile='version.json')
        """)
    return readJsonFile('logs/version.json')
}

@NonCPS
def setCombinedBuildResult(results)
{
    def combinedResult = hudson.model.Result.SUCCESS
    for (int i = 0; i != results.size(); ++i) {
        def result = hudson.model.Result.fromString(results[i])
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
