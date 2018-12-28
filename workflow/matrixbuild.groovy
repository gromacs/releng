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
    def status = utils.runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${filename}')
        """)
    return status.return_value
}

def doMatrixBuild(jobName, matrix)
{
    def parameters = utils.currentBuildParametersForJenkins()
    parameters += [$class: 'StringParameterValue', name: 'OPTIONS', value: matrix.as_axis]
    def bld = build job: jobName, parameters: parameters, propagate: false
    status = processMatrixResults(matrix, bld)
    return [ jobName: jobName, build: bld, status: status ]
}

def processMatrixResults(matrix, bld)
{
    def status
    node ('pipeline-general') {
        def data = [ 'matrix': matrix, 'build_url': bld.absoluteUrl ]
        utils.writeJsonFile('build/matrix.json', data)
        status = utils.runRelengScript("""\
            releng.process_multi_configuration_build_results('build/matrix.json')
            """, false)
    }
    return status
}

def addSummaryForMatrix(result)
{
    def text = """\
        Matrix build: <a href="${result.build.absoluteUrl}">${result.jobName} #${result.build.number}</a>
        """.stripIndent()
    manager.createSummary('empty').appendText(text, false)
}

return this
