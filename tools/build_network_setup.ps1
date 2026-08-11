param(
    [string]$Version = "1.5.9",
    [Parameter(Mandatory = $true)][string]$SetupUrl,
    [Parameter(Mandatory = $true)][string]$SetupSha256,
    [string]$OutputPath = ""
)
$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') { throw "Invalid version." }
if ($SetupSha256 -notmatch '^[0-9A-Fa-f]{64}$') { throw "Invalid setup SHA-256." }
$fileVersion = if (($Version -split '\.').Count -eq 3) { "$Version.0" } else { $Version }
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $root "releases\ClicknTranslate-Setup-v$Version-win64.exe" }
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force | Out-Null
$compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $compiler)) { $compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
$buildDir = Join-Path ([System.IO.Path]::GetTempPath()) ("ClicknTranslateNetworkSetup_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
try {
    $escapedUrl = $SetupUrl.Replace('"', '""')
    [System.IO.File]::WriteAllText((Join-Path $buildDir "Info.cs"), @"
internal static class SetupBootstrapInfo
{
    internal const string Version = "$Version";
    internal const string Url = @"$escapedUrl";
    internal const string Sha256 = "$($SetupSha256.ToUpperInvariant())";
}
"@, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText((Join-Path $buildDir "Version.cs"), @"
using System.Reflection;
[assembly: AssemblyTitle("Click'n'Translate Setup")]
[assembly: AssemblyCompany("Jabrail Digital")]
[assembly: AssemblyProduct("Click'n'Translate")]
[assembly: AssemblyVersion("$fileVersion")]
[assembly: AssemblyFileVersion("$fileVersion")]
"@, [System.Text.UTF8Encoding]::new($false))
    & $compiler /nologo /target:winexe /platform:x64 /optimize+ `
        /reference:System.dll /reference:System.Core.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll `
        "/win32icon:$root\icons\icon.ico" "/win32manifest:$root\installer\windows\ClicknTranslate.exe.manifest" `
        "/out:$OutputPath" "$root\launcher\ClicknTranslateNetworkSetup.cs" `
        (Join-Path $buildDir "Info.cs") (Join-Path $buildDir "Version.cs")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputPath)) { throw "Network setup compilation failed." }
}
finally { Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue }
Get-Item -LiteralPath $OutputPath
