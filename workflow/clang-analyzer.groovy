utils = load 'releng/workflow/utils.groovy'
utils.setEnvForRelengFromBuildParameters('gromacs')
utils.checkoutDefaultProject()
utils.readBuildRevisions()
config = utils.processBuildScriptConfig('clang-analyzer')

def doBuild()
{
    utils.setEnvForRelengSecondaryCheckouts()
    node (config.labels)
    {
        wrap([$class: 'TimestamperBuildWrapper']) {
            // TODO: Post errors if any back to Gerrit.
            utils.runRelengScript("""\
                releng.run_build('clang-analyzer', releng.JobType.GERRIT, ['build-jobs=4'])
                """)
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

return this
