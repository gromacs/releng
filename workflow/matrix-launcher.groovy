// FIXME: Reporting back to Gerrit cannot work before JENKINS-32692 is resolved.
env.URL_TO_POST = env.BUILD_URL

utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('gromacs')
utils.checkoutDefaultProject()

def loadMatrixConfigs(filename)
{
    optionsString = utils.processMatrixConfigsToBuildAxis(filename)
}

def doBuild(matrixJobName)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'StringParameterValue', name: 'OPTIONS', value: optionsString]
    def matrixBuild = build job: matrixJobName, parameters: parameters, propagate: false
    currentBuild.setResult(matrixBuild.result)
    addSummaryForTriggeredBuild(matrixJobName, matrixBuild)
    env.URL_TO_POST = matrixBuild.absoluteUrl
}

def addSummaryForTriggeredBuild(jobName, build)
{
    def text = """\
        Matrix build: <a href="${build.absoluteUrl}">${jobName} #${build.number}</a>
        """.stripIndent()
    manager.createSummary('empty').appendText(text, false)
}

return this
