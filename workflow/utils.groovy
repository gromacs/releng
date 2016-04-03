@NonCPS
def setEnvForRelengFromBuildParameters(defaultProject)
{
    // Most of this becomes unnecessary if JENKINS-30910 is resolved.
    env.GROMACS_REFSPEC = GROMACS_REFSPEC
    env.REGRESSIONTESTS_REFSPEC = REGRESSIONTESTS_REFSPEC
    env.RELENG_REFSPEC = RELENG_REFSPEC
    if (binding.variables.containsKey('GERRIT_PROJECT')) {
        binding.variables.findAll { it.key.startsWith('GERRIT_') }.each {
            key, value -> env."$key" = value
        }
        env.CHECKOUT_PROJECT = GERRIT_PROJECT
        env.CHECKOUT_REFSPEC = GERRIT_REFSPEC
    } else {
        env.CHECKOUT_PROJECT = defaultProject
        env.CHECKOUT_REFSPEC = env."${defaultProject.toUpperCase()}_REFSPEC"
    }
}

def checkoutDefaultProject()
{
    checkout scm: [$class: 'GitSCM',
        branches: [[name: env.CHECKOUT_REFSPEC]],
        doGenerateSubmoduleConfigurations: false,
        extensions: [
            [$class: 'RelativeTargetDirectory', relativeTargetDir: env.CHECKOUT_PROJECT],
            [$class: 'CleanCheckout'],
            [$class: 'BuildChooserSetting', buildChooser: [$class: 'GerritTriggerBuildChooser']]],
        submoduleCfg: [],
        userRemoteConfigs: [[refspec: env.CHECKOUT_REFSPEC,
            url: "ssh://jenkins@gerrit.gromacs.org/${env.CHECKOUT_PROJECT}.git"]]]
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
    binding.variables.findAll { it.key.startsWith('GERRIT_') }.each {
        key, value ->
            parameters += [$class: 'StringParameterValue', name: key, value: value]
    }
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
    sh 'python build.py'
}

def runRelengScript(contents, propagate = true)
{
    def refspec = RELENG_REFSPEC
    if (env.CHECKOUT_PROJECT == 'releng') {
        refspec = env.CHECKOUT_REFSPEC
    }
    def checkoutScript = """\
        import os
        import subprocess
        if not os.path.isdir('releng'):
            os.makedirs('releng')
        os.chdir('releng')
        subprocess.check_call(['git', 'init'])
        subprocess.check_call(['git', 'fetch',
            'ssh://jenkins@gerrit.gromacs.org/releng.git', '${refspec}'])
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
        runPythonScript(script)
    } catch (err) {
        def reason = null
        if (fileExists('logs/status.json')) {
            reason = readJsonFile('logs/status.json').reason
        }
        addRelengErrorSummary(reason)
        throw err
    }
    return readJsonFile('logs/status.json')
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

def readBuildRevisions()
{
    runRelengScriptNoCheckout("""\
        releng.get_build_revisions('build-revisions.json')
        """)
    def revisionList = readJsonFile('logs/build-revisions.json')
    setRevisionHashesToEnv(revisionList)
    addBuildRevisionsSummary(revisionList)
    return revisionListToRevisionMap(revisionList)
}

@NonCPS
def setRevisionHashesToEnv(revisionList)
{
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
    runRelengScriptNoCheckout("""\
        releng.read_build_script_config('${script}', 'config.json')
        """)
    return readJsonFile('build/config.json')
}

def processMatrixConfigsToBuildAxis(filename)
{
    runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}', 'matrix.txt')
        """)
    return readPropertyFile('build/matrix.txt').OPTIONS
}

def processMatrixConfigs(filename)
{
    runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}', 'matrix.json')
        """)
    return readJsonFile('build/matrix.json')
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
    def slurper = new groovy.json.JsonSlurper()
    return slurper.parseText(contents)
}

return this
