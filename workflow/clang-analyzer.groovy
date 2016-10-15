utils = load 'releng/workflow/utils.groovy'
utils.setEnvForReleng('gromacs')
utils.checkoutDefaultProject()
utils.readBuildRevisions()
config = utils.processBuildScriptConfig('clang-analyzer')

def doBuild()
{
    node (config.labels)
    {
        timestamps {
            // This has at least sometimes remained running forever in Jenkins.
            // If we are lucky, the timeout will actually stop the build at
            // some point instead of leaving it running forever...
            timeout(120) {
                utils.runRelengScript("""\
                    releng.run_build('clang-analyzer', releng.JobType.GERRIT, ['build-jobs=4'])
                    """)
            }
            addInformationAboutWarnings()
            step([$class: 'WarningsPublisher',
                canComputeNew: false, canRunOnFailed: true,
                consoleParsers: [[parserName: "Clang (LLVM based)"]],
                excludePattern: ''])
            publishHTML(target: [
                reportDir: 'logs/scan_html/final',
                reportFiles: 'index.html',
                allowMissing: true, alwaysLinkToLastBuild: false, keepAll: true,
                reportName: 'Analysis Report'])
        }
    }
}

def addInformationAboutWarnings()
{
    def summary = manager.createSummary('empty')
    summary.appendText("""\
        More details for the warnings reported below can be accessed
        through 'Analysis Report' (link on left).  Only issues that appear
        in the analysis report mark the build unstable.  In particular,
        issues reported from headers will contribute to the warning
        count, but will not mark the build unstable.
        """.stripIndent(), true)
}

return this
