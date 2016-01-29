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
    def parameters = [
            [$class: 'StringParameterValue', name: 'GROMACS_REFSPEC', value: GROMACS_REFSPEC],
            [$class: 'StringParameterValue', name: 'REGRESSIONTESTS_REFSPEC', value: REGRESSIONTESTS_REFSPEC],
            [$class: 'StringParameterValue', name: 'RELENG_REFSPEC', value: RELENG_REFSPEC]
        ]
    binding.variables.findAll { it.key.startsWith('GERRIT_') }.each {
        key, value ->
            parameters += [$class: 'StringParameterValue', name: key, value: value]
    }
    return parameters
}

def runPythonScript(contents)
{
    writeFile file: 'build.py', text: contents
    sh 'python build.py'
}

def runRelengScriptNoCheckout(contents)
{
    def importScript = """\
        import os
        import sys
        os.environ['WORKSPACE'] = os.getcwd()
        sys.path.append(os.path.abspath('releng'))
        import releng
        """.stripIndent()
    def script = importScript + contents.stripIndent()
    runPythonScript(script)
}

def processMatrixConfigsToBuildAxis(filename)
{
    runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}', 'matrix.txt')
        """)
    return readPropertyFile('build/matrix.txt').OPTIONS
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

return this
