[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$DefenderPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# A caller running in PowerShell 7 may pass its module paths to Windows
# PowerShell 5.1. Load the modules belonging to this host, as sign_windows does.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1')
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
$Path = (Resolve-Path -LiteralPath $Path).ProviderPath
$ReportPath = [IO.Path]::GetFullPath($ReportPath)
$target = Get-Item -LiteralPath $Path
if ($ReportPath.Equals($Path, [StringComparison]::OrdinalIgnoreCase) -or
    ($target.PSIsContainer -and $ReportPath.StartsWith(
        $Path.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase))) {
    throw 'Save the scan report outside the scanned package.'
}
if (Test-Path -LiteralPath $ReportPath) {
    throw 'The scan report already exists; choose a new ReportPath to preserve previous evidence.'
}

function Get-ScanInventory {
    $files = @(if ($target.PSIsContainer) {
        Get-ChildItem -LiteralPath $Path -File -Recurse -Force
    } else { $target })
    if (-not $files.Count) { throw 'The scan target contains no files.' }
    @($files | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{
            File = if ($target.PSIsContainer) { $_.FullName.Substring($Path.TrimEnd('\').Length + 1) } else { $_.Name }
            SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
}

$report = [ordered]@{
    StartedUtc = [DateTime]::UtcNow.ToString('o')
    Target = $Path
    Status = 'Failed'
    Scanner = $null
    SignatureVersion = $null
    SignatureUpdatedUtc = $null
    ExitCode = $null
    Output = ''
    Error = $null
    Files = @()
}
try {
    $status = Get-MpComputerStatus
    if (-not $status.AntivirusEnabled -or -not $status.RealTimeProtectionEnabled) {
        throw 'Microsoft Defender and real-time protection must be enabled for this release check.'
    }
    $report.SignatureVersion = $status.AntivirusSignatureVersion
    $report.SignatureUpdatedUtc = $status.AntivirusSignatureLastUpdated.ToUniversalTime().ToString('o')
    if ($status.AntivirusSignatureLastUpdated -lt (Get-Date).AddDays(-2)) {
        throw 'Defender definitions are older than two days. Update them and run the check again.'
    }
    if (-not $DefenderPath) {
        $platform = Join-Path $env:ProgramData 'Microsoft\Windows Defender\Platform'
        $DefenderPath = Get-ChildItem -Path "$platform\*\MpCmdRun.exe" -File -ErrorAction SilentlyContinue |
            Sort-Object { $_.Directory.Name } -Descending | Select-Object -First 1 -ExpandProperty FullName
        if (-not $DefenderPath) { $DefenderPath = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe' }
    }
    if (-not (Test-Path -LiteralPath $DefenderPath -PathType Leaf)) {
        throw 'MpCmdRun.exe was not found; the release has not been scanned.'
    }
    $report.Scanner = [IO.Path]::GetFullPath($DefenderPath)
    $report.Files = @(Get-ScanInventory)
    $before = ConvertTo-Json -InputObject $report.Files -Compress

    # This diagnostic custom scan ignores exclusions and scans archives. It
    # reports detections without deleting the release under investigation.
    # It does not disable real-time protection or change Defender settings.
    $scanOutput = & $DefenderPath -Scan -ScanType 3 -File $Path -DisableRemediation 2>&1
    $report.ExitCode = $LASTEXITCODE
    $report.Output = ($scanOutput | Out-String).Trim()
    $report.Output | Write-Host
    if ($report.ExitCode -ne 0) {
        throw "Defender detected a threat or could not complete the scan (exit $($report.ExitCode)). See the report."
    }
    $after = ConvertTo-Json -InputObject @(Get-ScanInventory) -Compress
    if ($before -cne $after) { throw 'Package files changed during the scan; scan the final unchanged bytes again.' }
    $report.Status = 'NoThreatsFound'
}
catch {
    $report.Error = $_.Exception.Message
    throw
}
finally {
    $report.FinishedUtc = [DateTime]::UtcNow.ToString('o')
    New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null
    [IO.File]::WriteAllText($ReportPath, (ConvertTo-Json -InputObject $report -Depth 5), [Text.UTF8Encoding]::new($false))
}
Write-Output "Defender found no threats. Report: $ReportPath"
