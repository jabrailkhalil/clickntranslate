param(
    [string]$Version = "1.5.3.0",
    [string]$OutputPath = "",
    [string]$PackageUrl = "https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.5.3/ClicknTranslate-v1.5.3-win64.zip",
    [string]$PackageSha256 = "1E6594368FEA3771259AB3384DDDC26F343A8AA7F489AAEB9EAF40AC57650488"
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Version must contain four numeric parts, for example 1.5.0.0."
}
if (-not [Uri]::IsWellFormedUriString($PackageUrl, [UriKind]::Absolute)) {
    throw "PackageUrl must be an absolute URL."
}
if ($PackageSha256 -notmatch '^[0-9A-Fa-f]{64}$') {
    throw "PackageSha256 must be a 64-character SHA-256 digest."
}

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $root "releases\ClicknTranslate-Update-Repair.exe"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw "The .NET Framework C# compiler was not found."
}

$buildDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ClicknTranslateUpdateRepair_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$versionSource = Join-Path $buildDirectory "Version.cs"
$buildInfoSource = Join-Path $buildDirectory "RepairBuildInfo.cs"

try {
    $versionCode = @"
using System.Reflection;
[assembly: AssemblyTitle("Click'n'Translate Update Repair")]
[assembly: AssemblyCompany("Jabrail Digital")]
[assembly: AssemblyProduct("Click'n'Translate Update Repair")]
[assembly: AssemblyVersion("$Version")]
[assembly: AssemblyFileVersion("$Version")]
"@
    [System.IO.File]::WriteAllText($versionSource, $versionCode, [System.Text.UTF8Encoding]::new($false))

    $displayVersion = ($Version -split '\.')[0..2] -join '.'
    $escapedPackageUrl = $PackageUrl.Replace('"', '""')
    $buildInfoCode = @"
internal static class RepairBuildInfo
{
    internal const string DisplayVersion = "$displayVersion";
    internal const string PackageUrl = @"$escapedPackageUrl";
    internal const string PackageSha256 = "$($PackageSha256.ToUpperInvariant())";
}
"@
    [System.IO.File]::WriteAllText($buildInfoSource, $buildInfoCode, [System.Text.UTF8Encoding]::new($false))

    & $compiler `
        /nologo `
        /target:winexe `
        /platform:x64 `
        /optimize+ `
        /reference:System.dll `
        /reference:System.Core.dll `
        /reference:System.Drawing.dll `
        /reference:System.IO.Compression.dll `
        /reference:System.IO.Compression.FileSystem.dll `
        /reference:System.Windows.Forms.dll `
        "/win32icon:$root\icons\icon.ico" `
        "/win32manifest:$root\launcher\ClicknTranslateUpdateRepair.manifest" `
        "/out:$OutputPath" `
        "$root\launcher\ClicknTranslateUpdateRepair.cs" `
        "$root\launcher\SilentWinFormsDialog.cs" `
        $versionSource `
        $buildInfoSource

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputPath)) {
        throw "Update repair compilation failed with exit code $LASTEXITCODE."
    }
}
finally {
    if (Test-Path -LiteralPath $buildDirectory) {
        Remove-Item -LiteralPath $buildDirectory -Recurse -Force
    }
}

$item = Get-Item -LiteralPath $OutputPath
[pscustomobject]@{
    Path = $item.FullName
    Length = $item.Length
    FileVersion = $item.VersionInfo.FileVersion
}
