utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('gromacs')
utils.checkoutDefaultProject()
utils.readBuildRevisions()

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
    setGerritReview customUrl: matrixBuild.absoluteUrl
}

def addSummaryForTriggeredBuild(jobName, build)
{
    def text = """\
        Matrix build: <a href="${build.absoluteUrl}">${jobName} #${build.number}</a>
        """.stripIndent()
    manager.createSummary('empty').appendText(text, false)
}

return this
