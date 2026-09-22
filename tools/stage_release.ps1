param(
    [string]$Version = "1.7.1",
    [switch]$SkipPyInstaller,
    [string]$CertificateThumbprint = "",
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$CertificateStoreLocation = 'CurrentUser',
    [switch]$RequireSignature
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') {
    throw "Version must contain three or four numeric parts, for example 1.5.8 or 1.5.8.1."
}
$fileVersion = if (($Version -split '\.').Count -eq 3) { "$Version.0" } else { $Version }

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$releasesRoot = Join-Path $repoRoot "releases"
$distRoot = Join-Path $repoRoot "dist\ClicknTranslate"
$stageRoot = Join-Path $releasesRoot ("ClicknTranslate-v" + $Version + "-win64-stage")
$packageRoot = Join-Path $stageRoot "ClicknTranslate"
$innerRoot = Join-Path $packageRoot "app"

if ($RequireSignature -and -not $CertificateThumbprint) {
    throw "A signing certificate is required for a signed release. See docs/WINDOWS_SIGNING.md."
}
if ($CertificateThumbprint) {
    & (Join-Path $PSScriptRoot 'sign_windows.ps1') -Mode Check `
        -CertificateThumbprint $CertificateThumbprint -CertificateStoreLocation $CertificateStoreLocation
}

if (-not $SkipPyInstaller) {
    Push-Location $repoRoot
    try {
        & (Join-Path $repoRoot ".venv\Scripts\python.exe") -m PyInstaller `
            (Join-Path $repoRoot "ClicknTranslate.spec") --clean --noconfirm
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $distRoot "ClicknTranslate.exe"))) {
    throw "The PyInstaller output is missing: $distRoot"
}

foreach ($relativePath in @('ClicknTranslate.exe', '_internal\ArgosWorker.exe', '_internal\OcrWorker.exe')) {
    $frozen = Get-Item -LiteralPath (Join-Path $distRoot $relativePath)
    if ($frozen.VersionInfo.FileVersion -ne $fileVersion) {
        throw "The frozen build is stale or lacks version resources: $relativePath. Rebuild version $fileVersion."
    }
}

$resolvedReleases = [System.IO.Path]::GetFullPath($releasesRoot).TrimEnd('\') + '\'
$resolvedStage = [System.IO.Path]::GetFullPath($stageRoot)
if (-not $resolvedStage.StartsWith($resolvedReleases, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace a stage outside the releases directory: $resolvedStage"
}
if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $innerRoot -Force | Out-Null
Copy-Item -Path (Join-Path $distRoot "*") -Destination $innerRoot -Recurse -Force
Move-Item `
    -LiteralPath (Join-Path $innerRoot "ClicknTranslate.exe") `
    -Destination (Join-Path $innerRoot "ClicknTranslateApp.exe")

& (Join-Path $PSScriptRoot "build_launcher.ps1") `
    -Version $fileVersion `
    -OutputPath (Join-Path $packageRoot "ClicknTranslate.exe")
if ($LASTEXITCODE -ne 0) {
    throw "Launcher build failed with exit code $LASTEXITCODE."
}

& (Join-Path $PSScriptRoot "build_apply_updater.ps1") `
    -Version $fileVersion `
    -OutputPath (Join-Path $innerRoot "_internal\ClicknTranslateUpdater.exe")
if ($LASTEXITCODE -ne 0) {
    throw "Updater build failed with exit code $LASTEXITCODE."
}

$required = @(
    "ClicknTranslate.exe",
    "app\ClicknTranslateApp.exe",
    "app\_internal\ArgosWorker.exe",
    "app\_internal\OcrWorker.exe",
    "app\_internal\ClicknTranslateUpdater.exe",
    "app\_internal",
    "app"
)
foreach ($relativePath in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $relativePath))) {
        throw "Release stage is incomplete: $relativePath"
    }
}

$signatureReport = Join-Path $stageRoot 'windows-signatures.json'
$signingMode = if ($CertificateThumbprint) { 'Sign' } else { 'Audit' }
& (Join-Path $PSScriptRoot 'sign_windows.ps1') -Mode $signingMode -PackageRoot $packageRoot `
    -CertificateThumbprint $CertificateThumbprint -CertificateStoreLocation $CertificateStoreLocation `
    -ReportPath $signatureReport | Out-Host
if (-not $CertificateThumbprint) {
    Write-Warning 'This is an unsigned stage. Do not describe it as a signed release.'
}

# Hash the final signed bytes of every program module, library and worker.
& (Join-Path $repoRoot '.venv\Scripts\python.exe') (Join-Path $repoRoot 'release_manifest.py') write $packageRoot $Version
if ($LASTEXITCODE -ne 0) { throw 'Program manifest generation failed.' }

[pscustomobject]@{
    Version = $Version
    Stage = $stageRoot
    Package = $packageRoot
    SignatureReport = $signatureReport
    Signed = [bool]$CertificateThumbprint
    LauncherVersion = (Get-Item -LiteralPath (Join-Path $packageRoot "ClicknTranslate.exe")).VersionInfo.FileVersion
    PackageBytes = (Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Measure-Object -Property Length -Sum).Sum
}
