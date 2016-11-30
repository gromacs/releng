def getPackageInfo(dirName, jobName, buildNumber)
{
    getPackageArtifacts(dirName, jobName, buildNumber)
    return readPackageInfo("tarballs/${dirName}/package-info.log")
}

def getPackageArtifacts(dirName, jobName, buildNumber, withTarball = false)
{
    def filter = null
    if (!withTarball) {
        filter = '**/package-info.log'
    }
    if (buildNumber) {
        step([$class: 'CopyArtifact', projectName: jobName,
              selector: [$class: 'SpecificBuildSelector', buildNumber: buildNumber.toString()],
              filter: filter, target: "tarballs/${dirName}",
              fingerprintArtifacts: true, flatten: true])
    } else {
        step([$class: 'CopyArtifact', projectName: jobName,
              filter: filter, target: "tarballs/${dirName}",
              fingerprintArtifacts: true, flatten: true])
    }
}

def readPackageInfo(packageInfoLogPath)
{
    def props = utils.readPropertyFile(packageInfoLogPath)
    def version = props.PACKAGE_VERSION
    return [
            packageFileName: props.PACKAGE_FILE_NAME,
            buildNumber: props.BUILD_NUMBER,
            version: stripDevSuffix(version),
            isRelease: !version.endsWith('-dev'),
            md5sum: props.MD5SUM,
            props: props
        ]
}

def stripDevSuffix(version) {
    def match = version =~ /(.*)-dev$/
    if (match) {
        version = match.group(1)
    }
    return version
}

def createPackagingSummaryText(status, packageInfo)
{
    if (packageInfo == null)
        return null
    return """\
        <p>${status.result}</p>
        <table>
          <tr>
            <td><b>Package</b>:</td>
            <td>${packageInfo.packageFileName}</td>
          </tr>
          <tr>
            <td>MD5 sum:</td>
            <td>${packageInfo.md5sum}</td>
          </tr>
        </table>
        """.stripIndent()
}

return this
