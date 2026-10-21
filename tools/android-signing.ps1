[CmdletBinding()]
param(
    [switch]$Initialize,
    [string]$SigningDirectory = (Join-Path $env:USERPROFILE '.android/clickntranslate-signing'),
    [string[]]$GradleArguments = @('--no-daemon', ':app:assembleRelease', '--no-configuration-cache')
)
$ErrorActionPreference = 'Stop'
$clicknProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$clicknSigningRoot = [IO.Path]::GetFullPath($SigningDirectory)
if ($clicknSigningRoot.StartsWith($clicknProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $clicknSigningRoot -eq $clicknProjectRoot) {
    throw 'Keep the permanent signing key outside the Git checkout.'
}
$clicknSecretsPath = Join-Path $clicknSigningRoot 'signing.private.json'
if ($Initialize) {
    [IO.Directory]::CreateDirectory($clicknSigningRoot) | Out-Null
    $clicknOwner = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $clicknAcl = [Security.AccessControl.DirectorySecurity]::new()
    $clicknAcl.SetOwner($clicknOwner)
    $clicknAcl.SetAccessRuleProtection($true, $false)
    foreach ($clicknSid in @($clicknOwner, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
        $clicknAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $clicknSid, 'FullControl', 'ContainerInherit, ObjectInherit', 'None', 'Allow'))
    }
    Set-Acl -LiteralPath $clicknSigningRoot -AclObject $clicknAcl
    if (-not (Test-Path -LiteralPath $clicknSecretsPath)) {
        if (Test-Path -LiteralPath (Join-Path $clicknSigningRoot 'clickntranslate-release.jks')) {
            throw 'Existing key without credentials: preserve it and recover the original credentials.'
        }
        $clicknRandomBytes = New-Object byte[] 32
        $clicknRng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $clicknRng.GetBytes($clicknRandomBytes) } finally { $clicknRng.Dispose() }
        $clicknPassword = [Convert]::ToBase64String($clicknRandomBytes)
        $clicknNewCredentials = @{
            formatVersion = 1
            keystoreFile = 'clickntranslate-release.jks'
            keyAlias = 'clickntranslate'
            password = $clicknPassword
        }
        $clicknNewCredentials | ConvertTo-Json | Set-Content -LiteralPath $clicknSecretsPath -Encoding utf8
        [Array]::Clear($clicknRandomBytes, 0, $clicknRandomBytes.Length)
    }
}
if (-not (Test-Path -LiteralPath $clicknSecretsPath)) {
    throw 'No release key configured. Run this script with -Initialize once on Windows.'
}
$clicknCredentials = Get-Content -LiteralPath $clicknSecretsPath -Raw | ConvertFrom-Json
if ([IO.Path]::GetFileName($clicknCredentials.keystoreFile) -ne $clicknCredentials.keystoreFile) {
    throw 'The private configuration must name a key inside its signing directory.'
}
$clicknKeyPath = Join-Path $clicknSigningRoot $clicknCredentials.keystoreFile
$clicknEnvironmentNames = @('RELEASE_KEYSTORE_PATH','RELEASE_KEYSTORE_PASSWORD','RELEASE_KEY_ALIAS','RELEASE_KEY_PASSWORD')
$clicknPreviousEnvironment = @{}
foreach ($clicknName in $clicknEnvironmentNames) {
    $clicknPreviousEnvironment[$clicknName] = [Environment]::GetEnvironmentVariable($clicknName)
}
try {
    $env:RELEASE_KEYSTORE_PATH = $clicknKeyPath
    $env:RELEASE_KEYSTORE_PASSWORD = $clicknCredentials.password
    $env:RELEASE_KEY_ALIAS = $clicknCredentials.keyAlias
    $env:RELEASE_KEY_PASSWORD = $clicknCredentials.password
    if ($Initialize) {
        if (-not (Test-Path -LiteralPath $clicknKeyPath)) {
            & keytool -genkeypair -noprompt -storetype JKS -keystore $clicknKeyPath -alias $clicknCredentials.keyAlias -keyalg RSA -keysize 4096 -sigalg SHA256withRSA -validity 36500 -dname 'CN=ClicknTranslate, OU=Android, O=ClicknTranslate' -storepass:env RELEASE_KEYSTORE_PASSWORD -keypass:env RELEASE_KEY_PASSWORD
            if ($LASTEXITCODE -ne 0) { throw 'Signing key generation failed.' }
        }
        $clicknCertificate = Join-Path $clicknSigningRoot 'release-certificate.pem'
        & keytool -exportcert -rfc -keystore $clicknKeyPath -alias $clicknCredentials.keyAlias -storepass:env RELEASE_KEYSTORE_PASSWORD -file $clicknCertificate
        if ($LASTEXITCODE -ne 0) { throw 'Public certificate export failed.' }
        @'
Permanent Clickn Android signing material.
Back up this entire directory privately before publishing the first release.
The JKS and signing.private.json are secret and must never enter Git or public downloads.
The JSON password is stored locally under the owner-only directory permissions.
release-certificate.pem is public.
To build on another Windows PC, restore this directory and pass -SigningDirectory to tools/android-signing.ps1.
'@ | Set-Content -LiteralPath (Join-Path $clicknSigningRoot 'README.txt') -Encoding utf8
        Write-Output ('Permanent key: ' + $clicknKeyPath)
        Write-Output ('Public certificate: ' + $clicknCertificate)
    } else {
        if (-not (Test-Path -LiteralPath $clicknKeyPath)) { throw 'The configured permanent key is missing.' }
        & (Join-Path $clicknProjectRoot 'gradlew.bat') @GradleArguments
        if ($LASTEXITCODE -ne 0) { throw ('Gradle failed with exit code ' + $LASTEXITCODE) }
    }
} finally {
    foreach ($clicknName in $clicknEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($clicknName, $clicknPreviousEnvironment[$clicknName])
    }
    $clicknCredentials = $null
    $clicknPassword = $null
}
