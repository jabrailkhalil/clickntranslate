param(
    [string]$Version = "1.6.1",
    [switch]$SkipPyInstaller
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

if (-not $SkipPyInstaller) {
    & (Join-Path $repoRoot ".venv\Scripts\python.exe") -m PyInstaller `
        (Join-Path $repoRoot "ClicknTranslate.spec") --clean --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $distRoot "ClicknTranslate.exe"))) {
    throw "The PyInstaller output is missing: $distRoot"
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

[pscustomobject]@{
    Version = $Version
    Stage = $stageRoot
    Package = $packageRoot
    LauncherVersion = (Get-Item -LiteralPath (Join-Path $packageRoot "ClicknTranslate.exe")).VersionInfo.FileVersion
    PackageBytes = (Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Measure-Object -Property Length -Sum).Sum
}
