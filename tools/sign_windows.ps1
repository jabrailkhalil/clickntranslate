[CmdletBinding()]
param(
    [ValidateSet('Sign', 'Verify', 'Audit', 'Check')][string]$Mode = 'Sign',
    [string]$PackageRoot = '',
    [string[]]$FilePath = @(),
    [string]$CertificateThumbprint = '',
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$CertificateStoreLocation = 'CurrentUser',
    [string]$TimestampServer = 'http://timestamp.digicert.com',
    [string]$SignToolPath = '',
    [string]$ReportPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# A Python process launched from PowerShell 7 can pass its module search path
# to Windows PowerShell 5.1. Load this host's security module explicitly.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1')
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')

if ($CertificateThumbprint) {
    $CertificateThumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
    if ($CertificateThumbprint -notmatch '^[A-F0-9]{40}$') {
        throw 'CertificateThumbprint must be the 40-character certificate thumbprint, not a password.'
    }
}
if ($Mode -in @('Sign', 'Check')) {
    if (-not $CertificateThumbprint) {
        throw 'A trusted code-signing certificate is required. No files were signed. See docs/WINDOWS_SIGNING.md.'
    }
    $certificate = Get-Item -LiteralPath "Cert:\$CertificateStoreLocation\My\$CertificateThumbprint"
    if (-not $certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date) -or
        $certificate.NotBefore -gt (Get-Date)) {
        throw 'The selected certificate must be current and have an accessible private key.'
    }
    if ($certificate.Subject -eq $certificate.Issuer) {
        throw 'Self-signed certificates are not suitable for public releases.'
    }
    $usages = @($certificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
        ForEach-Object { $_.EnhancedKeyUsages } | ForEach-Object { $_.Value })
    if ('1.3.6.1.5.5.7.3.3' -notin $usages) {
        throw 'The selected certificate is not a code-signing certificate.'
    }
    $timestampUri = $null
    if (-not [Uri]::TryCreate($TimestampServer, [UriKind]::Absolute, [ref]$timestampUri) -or
        $timestampUri.Scheme -notin @('http', 'https')) {
        throw 'TimestampServer must be an HTTP or HTTPS RFC 3161 timestamp service.'
    }
}

if ($Mode -ne 'Audit') {
    if (-not $SignToolPath) {
        $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($command) { $SignToolPath = $command.Source }
        else {
            $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
            $candidate = Get-ChildItem -Path "$sdkRoot\*\x64\signtool.exe" -File -ErrorAction SilentlyContinue |
                Sort-Object { [version]$_.Directory.Parent.Name } -Descending | Select-Object -First 1
            if ($candidate) { $SignToolPath = $candidate.FullName }
        }
    }
    if (-not $SignToolPath -or -not (Test-Path -LiteralPath $SignToolPath -PathType Leaf)) {
        throw 'SignTool.exe was not found. Install the Windows SDK signing tools.'
    }
}
if ($Mode -eq 'Check') {
    Write-Output 'Signing certificate and SignTool are available. No files were changed.'
    return
}

if ([bool]$PackageRoot -eq [bool]$FilePath.Count) {
    throw 'Specify either PackageRoot or FilePath.'
}
if ($PackageRoot) {
    $PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
    # These five EXEs are built from this repository. Do not re-sign upstream DLLs.
    $FilePath = @(
        'ClicknTranslate.exe',
        'app\ClicknTranslateApp.exe',
        'app\_internal\ArgosWorker.exe',
        'app\_internal\OcrWorker.exe',
        'app\_internal\ClicknTranslateUpdater.exe'
    ) | ForEach-Object { Join-Path $PackageRoot $_ }
}
$paths = @($FilePath | ForEach-Object {
    $resolved = [IO.Path]::GetFullPath($_)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "Required executable is missing: $resolved"
    }
    if ([IO.Path]::GetExtension($resolved) -ne '.exe') {
        throw "Expected an application, helper or installer EXE: $resolved"
    }
    $resolved
} | Select-Object -Unique)

# Validate the whole input set before modifying the first file.
if ($ReportPath) {
    $ReportPath = [IO.Path]::GetFullPath($ReportPath)
    if ($ReportPath -in $paths) { throw 'ReportPath cannot overwrite an input executable.' }
}
$report = @()
foreach ($path in $paths) {
    if ($Mode -eq 'Sign') {
        $signArgs = @('sign', '/fd', 'SHA256', '/tr', $TimestampServer, '/td', 'SHA256',
            '/sha1', $CertificateThumbprint, '/s', 'My',
            '/d', "Click'n'Translate", '/du', 'https://github.com/jabrailkhalil/clickntranslate')
        if ($CertificateStoreLocation -eq 'LocalMachine') { $signArgs += '/sm' }
        & $SignToolPath @signArgs $path
        if ($LASTEXITCODE -ne 0) { throw "Signing failed for $path (exit $LASTEXITCODE)." }
    }
    if ($Mode -in @('Sign', 'Verify')) {
        # /pa checks Authenticode trust, /all checks every signature, /tw requires
        # a timestamp (a warning also fails this release gate).
        & $SignToolPath verify /pa /all /tw $path
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed for $path (exit $LASTEXITCODE)." }
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    $signer = $signature.SignerCertificate
    $timestamp = $signature.TimeStamperCertificate
    if ($Mode -in @('Sign', 'Verify')) {
        if ($signature.Status.ToString() -ne 'Valid' -or -not $signer -or -not $timestamp) {
            throw "A trusted, timestamped signature is required: $path"
        }
        if (-not $CertificateThumbprint) { $CertificateThumbprint = $signer.Thumbprint }
        if ($signer.Thumbprint -ne $CertificateThumbprint) {
            throw "The executable was signed by a different certificate: $path"
        }
    }
    $file = Get-Item -LiteralPath $path
    $name = if ($PackageRoot) { $path.Substring($PackageRoot.TrimEnd('\').Length + 1) } else { $file.Name }
    $report += [pscustomobject]@{
        File = $name
        SHA256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        Bytes = $file.Length
        FileVersion = $file.VersionInfo.FileVersion
        Product = $file.VersionInfo.ProductName
        Signature = $signature.Status.ToString()
        Signer = if ($signer) { $signer.Subject } else { $null }
        CertificateThumbprint = if ($signer) { $signer.Thumbprint } else { $null }
        Timestamped = [bool]$timestamp
    }
}
if ($ReportPath) {
    $parent = Split-Path -Parent $ReportPath
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [IO.File]::WriteAllText($ReportPath, (ConvertTo-Json -InputObject $report -Depth 4), [Text.UTF8Encoding]::new($false))
}
$report
