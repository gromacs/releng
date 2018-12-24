utils = load 'releng/workflow/utils.groovy'
utils.initBuildRevisions('releng')
utils.checkoutDefaultProject()

def doBuild()
{
    stage ('releng unit tests') {
        node ('bs_nix-matrix_master')
        {
            timestamps {
                sh """\
                    cd releng
                    python -m releng.test
                    """.stripIndent()
            }
        }
    }

    stage ('Verify matrix contents') {
        failureReason = ''
        node ('pipeline-general') {
            verifyAllMatrixContents('master')
            verifyAllMatrixContents('release-2019')
            verifyAllMatrixContents('release-2018')
        }
        if (failureReason) {
            setGerritReview unsuccessfulMessage: failureReason
        }
    }
}

def verifyAllMatrixContents(branch)
{
    def refspec = "refs/heads/${branch}"
    def envOverrides = [
            "GROMACS_REFSPEC=${refspec}",
            "CHECKOUT_PROJECT=gromacs"
        ]
    withEnv(envOverrides) {
        utils.checkoutSilent('gromacs')
        verifyMatrixContents(branch, 'pre-submit-matrix')
        verifyMatrixContents(branch, 'post-submit-matrix')
        verifyMatrixContents(branch, 'nightly-matrix')
        verifyMatrixContents(branch, 'release-matrix')
    }
}

def verifyMatrixContents(branch, matrixFile)
{
    if (!fileExists("gromacs/admin/builds/${matrixFile}.txt"))
        return
    def status = utils.runRelengScriptNoCheckout("""\
        releng.prepare_multi_configuration_build('${matrixFile}')
        """, false)
    utils.combineResultToCurrentBuild(status.result)
    addMatrixSummary("${branch} ${matrixFile}", status)
}

def addMatrixSummary(title, status)
{
    def result = status.return_value
    def icon = 'notepad'
    def text = """\
        <b>${title}</b>
        """.stripIndent()
    if (result) {
        text += '<table border="1">'
        for (def config : result.configs) {
            def configString = config.opts.join(' ')
            def hostString = config.host
            if (!hostString) {
                hostString = 'NONE'
            }
            text += """\
                <tr>
                  <td>${configString}</td>
                  <td>${hostString}</td>
                </tr>
                """.stripIndent()
        }
        text += '</table>'
    }
    if (!utils.isRelengStatusSuccess(status)) {
        icon = 'error'
        if (status.reason) {
            failureReason += title + ':\n'
            failureReason += status.reason + '\n'
        }
    }
    manager.createSummary(icon).appendText(text, false)
}

return this
