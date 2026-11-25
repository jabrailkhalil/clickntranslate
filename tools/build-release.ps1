[CmdletBinding()]
param([string]$SigningDirectory = (Join-Path $env:USERPROFILE '.android/clickntranslate-signing'))
$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$configurationPath = Join-Path $SigningDirectory 'signing.private.json'
if (-not (Test-Path -LiteralPath $configurationPath)) {
    throw 'Restore the existing production signing directory. This script never creates or replaces keys.'
}
$privateConfiguration = Get-Content -LiteralPath $configurationPath -Raw | ConvertFrom-Json
if ([IO.Path]::GetFileName($privateConfiguration.keystoreFile) -ne $privateConfiguration.keystoreFile) {
    throw 'The private configuration must name a key file inside the signing directory.'
}
$existingKey = Join-Path $SigningDirectory $privateConfiguration.keystoreFile
if (-not (Test-Path -LiteralPath $existingKey)) { throw 'Existing signing key is missing.' }
$variableNames = @('RELEASE_KEYSTORE_PATH', 'RELEASE_KEYSTORE_PASSWORD', 'RELEASE_KEY_ALIAS', 'RELEASE_KEY_PASSWORD')
$previousValues = @{}
$temporaryCertificate = $null
foreach ($variableName in $variableNames) { $previousValues[$variableName] = [Environment]::GetEnvironmentVariable($variableName) }
try {
    $env:RELEASE_KEYSTORE_PATH = $existingKey
    $env:RELEASE_KEYSTORE_PASSWORD = $privateConfiguration.password
    $env:RELEASE_KEY_ALIAS = $privateConfiguration.keyAlias
    $env:RELEASE_KEY_PASSWORD = $privateConfiguration.password
    $temporaryCertificate = [IO.Path]::GetTempFileName()
    & keytool -exportcert -keystore $existingKey -alias $privateConfiguration.keyAlias -storepass:env RELEASE_KEYSTORE_PASSWORD -file $temporaryCertificate 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the certificate of the existing key.' }
    $expectedIdentity = '1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85'
    $actualIdentity = (Get-FileHash -LiteralPath $temporaryCertificate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualIdentity -ne $expectedIdentity) { throw 'Signing certificate does not match the existing production identity. Build stopped.' }
    Push-Location -LiteralPath $projectPath
    try {
        & .\gradlew.bat :app:assembleRelease :app:lintRelease --console plain
        if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }
        $releasePath = Join-Path $projectPath 'app/build/outputs/apk/release/app-release.apk'
        if (-not (Test-Path -LiteralPath $releasePath)) { throw 'Signed release was not produced.' }
        Get-FileHash -LiteralPath $releasePath -Algorithm SHA256 | Select-Object Algorithm, Hash, Path
    } finally { Pop-Location }
} finally {
    foreach ($variableName in $variableNames) { [Environment]::SetEnvironmentVariable($variableName, $previousValues[$variableName]) }
    $privateConfiguration = $null
    if ($temporaryCertificate -and (Test-Path -LiteralPath $temporaryCertificate)) { Remove-Item -LiteralPath $temporaryCertificate }
}
