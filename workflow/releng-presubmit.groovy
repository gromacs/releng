utils = load 'releng/workflow/utils.groovy'
utils.setEnvForReleng('releng')
utils.checkoutDefaultProject()
utils.readBuildRevisions()

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