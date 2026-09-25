param(
    [string]$Version = "1.8.1.0",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Version must contain four numeric parts, for example 1.5.5.0."
}

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $root "dist\ClicknTranslate\_internal\ClicknTranslateUpdater.exe"
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

$buildDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ClicknTranslateApplyUpdate_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$versionSource = Join-Path $buildDirectory "Version.cs"

try {
    $versionCode = @"
using System.Reflection;
[assembly: AssemblyTitle("Click'n'Translate Update Installer")]
[assembly: AssemblyCompany("Jabrail Digital")]
[assembly: AssemblyProduct("Click'n'Translate")]
[assembly: AssemblyVersion("$Version")]
[assembly: AssemblyFileVersion("$Version")]
// The Win32 longPathAware manifest alone does not enable modern .NET IO.
[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.6.2")]
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
        /reference:System.IO.Compression.dll `
        /reference:System.IO.Compression.FileSystem.dll `
        /reference:System.Windows.Forms.dll `
        "/win32icon:$root\src\icons\icon.ico" `
        "/win32manifest:$root\tools\launcher\ClicknTranslateApplyUpdate.manifest" `
        "/out:$OutputPath" `
        "$root\tools\launcher\ClicknTranslateApplyUpdate.cs" `
        "$root\tools\launcher\SilentWinFormsDialog.cs" `
        $versionSource

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputPath)) {
        throw "Apply-update helper compilation failed with exit code $LASTEXITCODE."
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
