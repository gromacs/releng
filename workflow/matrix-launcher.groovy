utils = load 'releng/workflow/utils.groovy'
matrixbuild = load 'releng/workflow/matrixbuild.groovy'
utils.initBuildRevisions('gromacs')
utils.checkoutDefaultProject()

def loadMatrixConfigs(filename)
{
    matrix = matrixbuild.processMatrixConfigs(filename)
}

def doBuild(matrixJobName)
{
    def result = matrixbuild.doMatrixBuild(matrixJobName, matrix)
    utils.combineResultToCurrentBuild(result.status.result)
    matrixbuild.addSummaryForMatrix(result)
    setGerritReview customUrl: result.build.absoluteUrl, unsuccessfulMessage: result.status.reason
}

return this
