[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageRoot,
    [Parameter(Mandatory = $true)][string]$CertificateThumbprint,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$CertificateStoreLocation = 'CurrentUser',
    [string]$OutputDirectory = '',
    [string]$CompilerPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$versionSource = Get-Content -LiteralPath (Join-Path $repoRoot 'app_version.py') -Raw
if ($versionSource -notmatch 'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+(?:\.\d+)?)"') {
    throw 'APP_VERSION could not be read.'
}
$version = $Matches[1]
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'releases' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$signScript = Join-Path $PSScriptRoot 'sign_windows.ps1'
$CertificateThumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
& $signScript -Mode Check -CertificateThumbprint $CertificateThumbprint -CertificateStoreLocation $CertificateStoreLocation
& $signScript -Mode Verify -PackageRoot $PackageRoot -CertificateThumbprint $CertificateThumbprint | Out-Host

# A stale stage must not acquire the next version's installer label.
$expectedFileVersion = if ($version.Split('.').Count -eq 3) { "$version.0" } else { $version }
foreach ($relative in @('ClicknTranslate.exe', 'app\ClicknTranslateApp.exe',
    'app\_internal\ArgosWorker.exe', 'app\_internal\OcrWorker.exe', 'app\_internal\ClicknTranslateUpdater.exe')) {
    $file = Get-Item -LiteralPath (Join-Path $PackageRoot $relative)
    if ($file.VersionInfo.FileVersion -ne $expectedFileVersion) {
        throw "Rebuild the stage: $relative is not version $expectedFileVersion."
    }
}

if (-not $CompilerPath) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $CompilerPath = $command.Source }
    else {
        $CompilerPath = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
}
if (-not $CompilerPath) { throw 'Inno Setup 6 ISCC.exe was not found.' }

# $f and $q are Inno Setup's filename/quote substitutions, not shell expansion.
# Escape literal dollar signs in the script path for the Inno command parser.
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$signCommand = '$q{0}$q -NoProfile -NonInteractive -File $q{1}$q -FilePath $f -CertificateThumbprint {2} -CertificateStoreLocation {3}' -f `
    $powershell.Replace('$', '$$'), $signScript.Replace('$', '$$'), $CertificateThumbprint, $CertificateStoreLocation
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$installerName = "Click-n-Translate-$version-windows-x64-installer"
$installerPath = Join-Path $OutputDirectory "$installerName.exe"
if (Test-Path -LiteralPath $installerPath) {
    throw "The installer already exists; choose a new OutputDirectory: $installerPath"
}
& $CompilerPath "/DMyAppVersion=$version" "/DSourceDir=$PackageRoot" "/DReleaseDir=$OutputDirectory" `
    '/DSignRelease=1' "/F$installerName" "/Scntsign=$signCommand" (Join-Path $repoRoot 'installer\ClicknTranslate.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE." }
& $signScript -Mode Verify -FilePath $installerPath -CertificateThumbprint $CertificateThumbprint `
    -ReportPath "$installerPath.signatures.json"
$hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText("$installerPath.sha256", "$hash  $([IO.Path]::GetFileName($installerPath))`n", [Text.UTF8Encoding]::new($false))
