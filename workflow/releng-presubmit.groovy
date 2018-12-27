utils = load 'releng/workflow/utils.groovy'
utils.initBuildRevisions('releng')
utils.checkoutDefaultProject()

def doBuild()
{
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

return this