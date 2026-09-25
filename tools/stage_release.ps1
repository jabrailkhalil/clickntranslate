param(
    [string]$Version = "1.8.1",
    [switch]$SkipPyInstaller,
    # Separate private test builds from an existing stage and its user data.
    [ValidatePattern('^$|^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$StageName = "",
    [string]$CertificateThumbprint = "",
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$CertificateStoreLocation = 'CurrentUser',
    [switch]$RequireSignature,
    [switch]$ScanWithDefender
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
if (-not $StageName) { $StageName = "ClicknTranslate-v" + $Version + "-win64-stage" }
$stageRoot = Join-Path $releasesRoot $StageName
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
            (Join-Path $repoRoot "tools/packaging/ClicknTranslate.spec") --clean --noconfirm
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
& (Join-Path $repoRoot '.venv\Scripts\python.exe') (Join-Path $repoRoot 'src/release_manifest.py') write $packageRoot $Version
if ($LASTEXITCODE -ne 0) { throw 'Program manifest generation failed.' }

# The installed updater from earlier versions requires this manifest beside
# ClicknTranslate.exe. Keep that compatibility file at the root but hide it in
# Explorer so the program files remain organized under app/.
$legacyManifest = Get-Item -LiteralPath (Join-Path $packageRoot 'program-files.sha256')
if (($legacyManifest.Attributes -band [IO.FileAttributes]::Hidden) -eq 0) {
    $legacyManifest.Attributes = $legacyManifest.Attributes -bor [IO.FileAttributes]::Hidden
}
if (($legacyManifest.Attributes -band [IO.FileAttributes]::Hidden) -eq 0) {
    throw 'The legacy update manifest could not be hidden.'
}

$defenderReport = $null
if ($RequireSignature -or $CertificateThumbprint -or $ScanWithDefender) {
    $defenderReport = Join-Path $stageRoot 'windows-defender.json'
    & (Join-Path $PSScriptRoot 'scan_windows_release.ps1') -Path $packageRoot -ReportPath $defenderReport
}

[pscustomobject]@{
    Version = $Version
    Stage = $stageRoot
    Package = $packageRoot
    SignatureReport = $signatureReport
    DefenderReport = $defenderReport
    Signed = [bool]$CertificateThumbprint
    LauncherVersion = (Get-Item -LiteralPath (Join-Path $packageRoot "ClicknTranslate.exe")).VersionInfo.FileVersion
    PackageBytes = (Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Measure-Object -Property Length -Sum).Sum
}
