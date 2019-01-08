utils = load 'releng/workflow/utils.groovy'
matrixbuild = load 'releng/workflow/matrixbuild.groovy'
revisions = utils.initBuildRevisions('gromacs')
utils.checkoutDefaultProject()
matrix = matrixbuild.processMatrixConfigs('pre-submit-matrix')

def doBuild(matrixJobPrefix)
{
    def matrixJobName = matrixJobPrefix + revisions.gromacs.build_branch_label
    def result = matrixbuild.doMatrixBuild(matrixJobName, matrix)
    utils.combineResultToCurrentBuild(result.status.result)
    matrixbuild.addSummaryForMatrix(result)
    setGerritReview customUrl: result.build.absoluteUrl, unsuccessfulMessage: result.status.reason
}

return this
