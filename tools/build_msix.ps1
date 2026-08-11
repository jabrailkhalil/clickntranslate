param(
    [string]$IdentityName = "JabrailDigital.ClicknTranslate.Test",
    [string]$Publisher = "CN=Jabrail Digital Test",
    [string]$PublisherDisplayName = "Jabrail Digital",
    [string]$Version = "1.5.9.0",
    [string]$BuildPath = "",
    [string]$OutputPath = "",
    [string]$CertificatePath = "",
    [string]$CertificatePassword = "",
    [switch]$SkipPyInstaller,
    [switch]$Store
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $BuildPath) {
    $BuildPath = Join-Path $repoRoot "dist\ClicknTranslate"
}
$BuildPath = [System.IO.Path]::GetFullPath($BuildPath)

if ($Store) {
    if (-not $PSBoundParameters.ContainsKey("IdentityName") -or
        -not $PSBoundParameters.ContainsKey("Publisher")) {
        throw "Store mode requires the exact -IdentityName and -Publisher values from Partner Center > Product identity."
    }
}

if ($IdentityName -notmatch '^[A-Za-z0-9.-]{3,50}$') {
    throw "IdentityName must contain 3-50 letters, numbers, dots, or dashes."
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Version must use four numeric parts, for example 1.5.0.0."
}

function Reset-SafeDirectory([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootPrefix = $repoRoot.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset a directory outside the repository: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $fullPath | Out-Null
}

function ConvertTo-XmlText([string]$Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

if (-not $SkipPyInstaller) {
    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Python environment not found: $python"
    }
    & $python -m PyInstaller (Join-Path $repoRoot "ClicknTranslate.spec") --clean --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $BuildPath "ClicknTranslate.exe"))) {
    throw "ClicknTranslate.exe was not found in $BuildPath"
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
& $python (Join-Path $repoRoot "tools\generate_msix_assets.py")
if ($LASTEXITCODE -ne 0) {
    throw "Store asset generation failed with exit code $LASTEXITCODE."
}

$workRoot = Join-Path $repoRoot "build\msix"
$stagePath = Join-Path $workRoot "stage"
Reset-SafeDirectory $stagePath

$excludedPortableFiles = @("data", "CreateShortcut.bat", "README.md")
Get-ChildItem -LiteralPath $BuildPath -Force | Where-Object {
    $_.Name -notin $excludedPortableFiles
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $stagePath -Recurse -Force
}

# PyInstaller's broad NumPy collection includes upstream test fixtures. They
# are not used at runtime, add several megabytes, and WACK flags their nested
# gzip archives. Prune only test directories inside the disposable MSIX stage.
$numpyPath = Join-Path $stagePath "_internal\numpy"
if (Test-Path -LiteralPath $numpyPath) {
    Get-ChildItem -LiteralPath $numpyPath -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "tests" } |
        Sort-Object { $_.FullName.Length } -Descending |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

Copy-Item -LiteralPath (Join-Path $repoRoot "installer\msix\Assets") -Destination $stagePath -Recurse -Force

$manifestTemplate = [System.IO.File]::ReadAllText(
    (Join-Path $repoRoot "installer\msix\AppxManifest.xml.in"),
    [System.Text.Encoding]::UTF8
)
$manifest = $manifestTemplate.Replace("__IDENTITY_NAME__", (ConvertTo-XmlText $IdentityName))
$manifest = $manifest.Replace("__PUBLISHER__", (ConvertTo-XmlText $Publisher))
$manifest = $manifest.Replace("__PUBLISHER_DISPLAY_NAME__", (ConvertTo-XmlText $PublisherDisplayName))
$manifest = $manifest.Replace("__VERSION__", $Version)
[System.IO.File]::WriteAllText(
    (Join-Path $stagePath "AppxManifest.xml"),
    $manifest,
    [System.Text.UTF8Encoding]::new($false)
)

$makeAppx = Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe" |
    Sort-Object -Property FullName -Descending |
    Select-Object -First 1
if (-not $makeAppx) {
    throw "MakeAppx.exe was not found. Install the Windows SDK."
}

if (-not $OutputPath) {
    $outputName = if ($Store) { "ClicknTranslate-$Version-store-x64.msix" } else { "ClicknTranslate-$Version-test-x64.msix" }
    $OutputPath = Join-Path $repoRoot "releases\$outputName"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

& $makeAppx.FullName pack /d $stagePath /p $OutputPath /o
if ($LASTEXITCODE -ne 0) {
    throw "MakeAppx failed with exit code $LASTEXITCODE."
}

if ($CertificatePath) {
    $signTool = Join-Path $makeAppx.Directory.FullName "signtool.exe"
    if (-not (Test-Path -LiteralPath $signTool)) {
        throw "SignTool.exe was not found next to MakeAppx.exe."
    }
    $signArgs = @("sign", "/fd", "SHA256", "/f", $CertificatePath)
    if ($CertificatePassword) {
        $signArgs += @("/p", $CertificatePassword)
    }
    $signArgs += $OutputPath
    & $signTool @signArgs
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool failed with exit code $LASTEXITCODE."
    }
}

$uploadPath = [System.IO.Path]::ChangeExtension($OutputPath, ".msixupload")
$uploadZipPath = "$uploadPath.zip"
if (Test-Path -LiteralPath $uploadPath) { Remove-Item -LiteralPath $uploadPath -Force }
if (Test-Path -LiteralPath $uploadZipPath) { Remove-Item -LiteralPath $uploadZipPath -Force }
Compress-Archive -LiteralPath $OutputPath -DestinationPath $uploadZipPath -CompressionLevel Optimal
Move-Item -LiteralPath $uploadZipPath -Destination $uploadPath

$hashPath = "$OutputPath.sha256"
$hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    $hashPath,
    "$hash  $([System.IO.Path]::GetFileName($OutputPath))`n",
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "MSIX package: $OutputPath"
Write-Host "Store upload: $uploadPath"
Write-Host "SHA-256: $hash"
if (-not $CertificatePath) {
    Write-Host "Package is unsigned. Partner Center signs Store packages; sign a test package before sideloading it."
}
