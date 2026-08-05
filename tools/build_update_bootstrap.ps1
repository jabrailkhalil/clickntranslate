param(
    [string]$Version = "1.5.5",
    [string]$SetupPath = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must contain three numeric parts, for example 1.5.1."
}

$root = Split-Path -Parent $PSScriptRoot
if (-not $SetupPath) {
    $SetupPath = Join-Path $root "releases\ClicknTranslate-Setup-v$Version-win64.exe"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $root "releases\ClicknTranslate-v$Version-win64-portable-bootstrap.zip"
}
$SetupPath = [System.IO.Path]::GetFullPath($SetupPath)
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
if (-not (Test-Path -LiteralPath $SetupPath -PathType Leaf)) {
    throw "Setup executable was not found: $SetupPath"
}

$compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw "The .NET Framework C# compiler was not found."
}

$buildDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ClicknTranslateUpdateBootstrap_" + [Guid]::NewGuid().ToString("N"))
$payloadRoot = Join-Path $buildDirectory "ClicknTranslate"
$innerRoot = Join-Path $payloadRoot "app"
$innerInternal = Join-Path $innerRoot "_internal"
$versionSource = Join-Path $buildDirectory "Version.cs"
$bootstrapPath = Join-Path $payloadRoot "ClicknTranslate.exe"

try {
    New-Item -ItemType Directory -Path $innerInternal -Force | Out-Null
    $fourPartVersion = "$Version.0"
    $versionCode = @"
using System.Reflection;
[assembly: AssemblyTitle("Click'n'Translate Update Bootstrap")]
[assembly: AssemblyCompany("Jabrail Digital")]
[assembly: AssemblyProduct("Click'n'Translate")]
[assembly: AssemblyVersion("$fourPartVersion")]
[assembly: AssemblyFileVersion("$fourPartVersion")]
"@
    [System.IO.File]::WriteAllText($versionSource, $versionCode, [System.Text.UTF8Encoding]::new($false))

    & $compiler `
        /nologo `
        /target:winexe `
        /platform:x64 `
        /optimize+ `
        /reference:System.dll `
        /reference:System.Core.dll `
        /reference:System.Drawing.dll `
        /reference:System.Windows.Forms.dll `
        "/win32icon:$root\icons\icon.ico" `
        "/win32manifest:$root\launcher\ClicknTranslateUpdateBootstrap.manifest" `
        "/out:$bootstrapPath" `
        "$root\launcher\ClicknTranslateUpdateBootstrap.cs" `
        "$root\launcher\SilentWinFormsDialog.cs" `
        $versionSource
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $bootstrapPath)) {
        throw "Update bootstrap compilation failed with exit code $LASTEXITCODE."
    }

    Copy-Item -LiteralPath $bootstrapPath -Destination (Join-Path $innerRoot "ClicknTranslateApp.exe") -Force
    Copy-Item -LiteralPath $SetupPath -Destination (Join-Path $payloadRoot (Split-Path -Leaf $SetupPath)) -Force
    [System.IO.File]::WriteAllText(
        (Join-Path $innerInternal "update-bootstrap.txt"),
        "The full application is installed by the bundled verified setup executable.",
        [System.Text.UTF8Encoding]::new($false)
    )

    $outputDirectory = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
    Compress-Archive -LiteralPath $payloadRoot -DestinationPath $OutputPath -CompressionLevel NoCompression

    $hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sidecarPath = "$OutputPath.sha256"
    [System.IO.File]::WriteAllText(
        $sidecarPath,
        "$hash  $(Split-Path -Leaf $OutputPath)`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $item = Get-Item -LiteralPath $OutputPath
    [pscustomobject]@{
        Path = $item.FullName
        Length = $item.Length
        Sha256 = $hash
        Setup = $SetupPath
        Sidecar = $sidecarPath
    }
}
finally {
    if (Test-Path -LiteralPath $buildDirectory) {
        Remove-Item -LiteralPath $buildDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}
