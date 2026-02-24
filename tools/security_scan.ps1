param(
    [switch]$Fix,
    [int]$PythonTimeoutSeconds = 180,
    [int]$KeepLatestRuns = 3,
    [bool]$ClearCache = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function New-DirIfMissing {
    param([string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
    }
}

function Clear-DirectoryContentsSafe {
    param(
        [string]$PathValue,
        [System.Collections.Generic.List[string]]$Warnings
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }

    try {
        $entries = Get-ChildItem -LiteralPath $PathValue -Force -ErrorAction Stop
    }
    catch {
        $Warnings.Add("Could not enumerate cache directory '$PathValue': $($_.Exception.Message)")
        return
    }

    foreach ($entry in $entries) {
        try {
            Remove-Item -LiteralPath $entry.FullName -Recurse -Force -ErrorAction Stop
        }
        catch {
            $Warnings.Add("Could not remove '$($entry.FullName)': $($_.Exception.Message)")
        }
    }
}

function Prune-OldSecurityRuns {
    param(
        [string]$ReportsRoot,
        [string]$CurrentRunRoot,
        [int]$RunsToKeep,
        [System.Collections.Generic.List[string]]$Warnings
    )

    if ($RunsToKeep -lt 1) {
        $RunsToKeep = 1
    }

    if (-not (Test-Path -LiteralPath $ReportsRoot)) {
        return 0
    }

    try {
        $runDirs = @(
            Get-ChildItem -LiteralPath $ReportsRoot -Directory -ErrorAction Stop |
                Sort-Object Name -Descending
        )
    }
    catch {
        $Warnings.Add("Could not enumerate security report runs: $($_.Exception.Message)")
        return 0
    }

    $keepSet = New-Object "System.Collections.Generic.HashSet[string]" ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($dir in ($runDirs | Select-Object -First $RunsToKeep)) {
        [void]$keepSet.Add($dir.FullName)
    }

    if (Test-Path -LiteralPath $CurrentRunRoot) {
        $resolvedCurrent = (Resolve-Path -LiteralPath $CurrentRunRoot).Path
        [void]$keepSet.Add($resolvedCurrent)
    }

    $removedCount = 0
    foreach ($dir in $runDirs) {
        if ($keepSet.Contains($dir.FullName)) {
            continue
        }

        try {
            Remove-Item -LiteralPath $dir.FullName -Recurse -Force -ErrorAction Stop
            $removedCount += 1
        }
        catch {
            $Warnings.Add("Could not prune report run '$($dir.Name)': $($_.Exception.Message)")
        }
    }

    return $removedCount
}

function Invoke-ExternalCommand {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Executable,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$TimeoutSeconds = 300
    )

    Write-Host "==> $Name"
    $proc = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -NoNewWindow `
        -PassThru
    $didExit = $proc.WaitForExit($TimeoutSeconds * 1000)
    if ($didExit) {
        $exitCode = $proc.ExitCode
    }
    else {
        try {
            $proc.Kill()
        }
        catch {
            # no-op
        }
        Add-Content -LiteralPath $StderrPath -Value "Command timed out after $TimeoutSeconds second(s)."
        $exitCode = 124
    }

    return [pscustomobject]@{
        name = $Name
        executable = $Executable
        arguments = ($Arguments -join " ")
        working_directory = $WorkingDirectory
        exit_code = $exitCode
        stdout = $StdoutPath
        stderr = $StderrPath
    }
}

function Get-NpmVulnerabilityCount {
    param([string]$JsonPath)
    if (-not (Test-Path -LiteralPath $JsonPath)) {
        return $null
    }

    try {
        $raw = Get-Content -LiteralPath $JsonPath -Raw
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return 0
        }
        $parsed = $raw | ConvertFrom-Json
        $v = $parsed.metadata.vulnerabilities
        if ($null -eq $v) {
            return 0
        }
        return [int]($v.info + $v.low + $v.moderate + $v.high + $v.critical)
    }
    catch {
        return $null
    }
}

function Get-PipAuditVulnerabilityCount {
    param([string]$JsonPath)
    if (-not (Test-Path -LiteralPath $JsonPath)) {
        return $null
    }

    try {
        $raw = Get-Content -LiteralPath $JsonPath -Raw
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return 0
        }
        $parsed = $raw | ConvertFrom-Json
        $count = 0

        if ($parsed -is [System.Array]) {
            foreach ($dep in $parsed) {
                if ($dep.PSObject.Properties.Name -contains "vulns") {
                    $count += @($dep.vulns).Count
                }
            }
            return $count
        }

        if ($parsed.PSObject.Properties.Name -contains "dependencies") {
            foreach ($dep in $parsed.dependencies) {
                if ($dep.PSObject.Properties.Name -contains "vulns") {
                    $count += @($dep.vulns).Count
                }
            }
            return $count
        }

        if ($parsed.PSObject.Properties.Name -contains "vulnerabilities") {
            return @($parsed.vulnerabilities).Count
        }

        return 0
    }
    catch {
        return $null
    }
}

function Test-PipAuditModule {
    param([string]$PythonExe)
    & $PythonExe -c "import pip_audit" 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportsRoot = Join-Path $repoRoot "reports\security"
$cacheRoot = Join-Path $repoRoot "reports\.cache\pip-audit"
$tempRoot = Join-Path $repoRoot "reports\.cache\tmp"
$runRoot = Join-Path $reportsRoot $timestamp

New-DirIfMissing $reportsRoot
New-DirIfMissing $cacheRoot
New-DirIfMissing $tempRoot
New-DirIfMissing $runRoot

$env:TMP = $tempRoot
$env:TEMP = $tempRoot
$env:TMPDIR = $tempRoot
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:all_proxy = ""

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$desktopDir = Join-Path $repoRoot "desktop_app"
$frontendDir = Join-Path $desktopDir "frontend"

$results = New-Object System.Collections.Generic.List[object]
$errors = New-Object System.Collections.Generic.List[string]

if ($ClearCache) {
    Clear-DirectoryContentsSafe -PathValue $cacheRoot -Warnings $errors
    Clear-DirectoryContentsSafe -PathValue $tempRoot -Warnings $errors
}

if (Test-Path -LiteralPath $pythonExe) {
    if (-not (Test-PipAuditModule -PythonExe $pythonExe)) {
        $installOut = Join-Path $runRoot "python_pip_audit_install.stdout.log"
        $installErr = Join-Path $runRoot "python_pip_audit_install.stderr.log"
        $installResult = Invoke-ExternalCommand `
            -Name "Install pip-audit" `
            -WorkingDirectory $repoRoot `
            -Executable $pythonExe `
            -Arguments @("-m", "pip", "install", "pip-audit") `
            -StdoutPath $installOut `
            -StderrPath $installErr `
            -TimeoutSeconds 180
        $results.Add($installResult)

        if ($installResult.exit_code -ne 0) {
            $errors.Add("Failed to install pip-audit. See $installErr")
        }
    }

    $pythonOut = Join-Path $runRoot "python_local.audit.json"
    $pythonErr = Join-Path $runRoot "python_local.audit.stderr.log"
    $pythonScanResult = Invoke-ExternalCommand `
        -Name "Python audit (local venv)" `
        -WorkingDirectory $repoRoot `
        -Executable $pythonExe `
        -Arguments @("-m", "pip_audit", "-l", "--format", "json", "--cache-dir", $cacheRoot, "--timeout", "8", "--progress-spinner", "off") `
        -StdoutPath $pythonOut `
        -StderrPath $pythonErr `
        -TimeoutSeconds $PythonTimeoutSeconds
    $results.Add($pythonScanResult)
}
else {
    $errors.Add("Python virtual environment not found at $pythonExe")
}

foreach ($target in @(
    @{ Name = "Node audit (desktop_app)"; Directory = $desktopDir; Prefix = "node_desktop" },
    @{ Name = "Node audit (frontend)"; Directory = $frontendDir; Prefix = "node_frontend" }
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $target.Directory "package.json"))) {
        $errors.Add("Missing package.json in $($target.Directory)")
        continue
    }

    $stdout = Join-Path $runRoot "$($target.Prefix).audit.json"
    $stderr = Join-Path $runRoot "$($target.Prefix).audit.stderr.log"
    $scanResult = Invoke-ExternalCommand `
        -Name $target.Name `
        -WorkingDirectory $target.Directory `
        -Executable "cmd.exe" `
        -Arguments @("/c", "npm", "audit", "--json") `
        -StdoutPath $stdout `
        -StderrPath $stderr `
        -TimeoutSeconds 180
    $results.Add($scanResult)

    if ($Fix) {
        $fixOut = Join-Path $runRoot "$($target.Prefix).fix.stdout.log"
        $fixErr = Join-Path $runRoot "$($target.Prefix).fix.stderr.log"
        $fixResult = Invoke-ExternalCommand `
            -Name "Node safe fix ($($target.Prefix))" `
            -WorkingDirectory $target.Directory `
            -Executable "cmd.exe" `
            -Arguments @("/c", "npm", "audit", "fix", "--no-fund") `
            -StdoutPath $fixOut `
            -StderrPath $fixErr `
            -TimeoutSeconds 180
        $results.Add($fixResult)

        $recheckOut = Join-Path $runRoot "$($target.Prefix).postfix.audit.json"
        $recheckErr = Join-Path $runRoot "$($target.Prefix).postfix.audit.stderr.log"
        $recheckResult = Invoke-ExternalCommand `
            -Name "Node post-fix audit ($($target.Prefix))" `
            -WorkingDirectory $target.Directory `
            -Executable "cmd.exe" `
            -Arguments @("/c", "npm", "audit", "--json") `
            -StdoutPath $recheckOut `
            -StderrPath $recheckErr `
            -TimeoutSeconds 180
        $results.Add($recheckResult)
    }
}

$summary = [ordered]@{
    timestamp = (Get-Date).ToString("o")
    repository = $repoRoot
    run_directory = $runRoot
    fix_requested = [bool]$Fix
    scans = @()
    totals = [ordered]@{
        python_vulnerabilities = 0
        node_vulnerabilities = 0
        unknown_count = 0
        command_errors = 0
    }
    notes = @()
}

foreach ($r in $results) {
    $name = [string]$r.name
    $stdoutPath = [string]$r.stdout
    $vulnCount = $null

    if ($name -like "Python audit*") {
        $vulnCount = Get-PipAuditVulnerabilityCount -JsonPath $stdoutPath
        if ($null -eq $vulnCount) {
            $summary.totals.unknown_count += 1
        }
        else {
            $summary.totals.python_vulnerabilities += $vulnCount
        }
    }
    elseif ($name -like "Node audit*" -or $name -like "Node post-fix audit*") {
        $vulnCount = Get-NpmVulnerabilityCount -JsonPath $stdoutPath
        $isPreFixScan = $Fix -and ($name -like "Node audit*")
        if (-not $isPreFixScan) {
            if ($null -eq $vulnCount) {
                $summary.totals.unknown_count += 1
            }
            else {
                $summary.totals.node_vulnerabilities += $vulnCount
            }
        }
    }

    if ([int]$r.exit_code -gt 1) {
        $summary.totals.command_errors += 1
    }
    elseif ($name -like "Python audit*" -and [int]$r.exit_code -eq 1 -and $vulnCount -eq 0) {
        $stderrText = ""
        if (Test-Path -LiteralPath ([string]$r.stderr)) {
            $stderrText = Get-Content -LiteralPath ([string]$r.stderr) -Raw
        }
        if ($stderrText -match "Traceback|PermissionError|VirtualEnvError|ERROR") {
            $summary.totals.command_errors += 1
        }
    }

    $summary.scans += [ordered]@{
        name = $name
        exit_code = [int]$r.exit_code
        vulnerability_count = $vulnCount
        stdout = $stdoutPath
        stderr = [string]$r.stderr
    }
}

if ($Fix) {
    $summary.notes += "npm safe auto-fix was requested and executed."
}
$summary.notes += "Python scan targets the local .venv package set. Auto-fixing Python packages is intentionally manual to avoid unexpected runtime breakage."
$summary.notes += "Python scan command timeout: $PythonTimeoutSeconds second(s)."
$summary.notes += "TMP/TEMP/TMPDIR are redirected to reports/.cache/tmp during scan to avoid AppData permission issues."
$summary.notes += "HTTP proxy variables are cleared during scan to avoid stale local proxy settings."
if ($errors.Count -gt 0) {
    foreach ($message in $errors) {
        $summary.notes += $message
    }
}

$prunedRuns = Prune-OldSecurityRuns `
    -ReportsRoot $reportsRoot `
    -CurrentRunRoot $runRoot `
    -RunsToKeep $KeepLatestRuns `
    -Warnings $errors
if ($prunedRuns -gt 0) {
    $summary.notes += "Pruned $prunedRuns old security report run(s); keeping newest $KeepLatestRuns."
}
if ($ClearCache) {
    $summary.notes += "Cleared reports/.cache before scan."
}
if ($errors.Count -gt 0) {
    $summary.notes += "One or more cleanup warnings occurred; see notes above."
}

$summaryPath = Join-Path $runRoot "summary.json"
$summary | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host ""
Write-Host "Security scan complete."
Write-Host "Summary: $summaryPath"
Write-Host "Python vulnerabilities: $($summary.totals.python_vulnerabilities)"
Write-Host "Node vulnerabilities: $($summary.totals.node_vulnerabilities)"
Write-Host "Unknown parse count: $($summary.totals.unknown_count)"
Write-Host "Command errors: $($summary.totals.command_errors)"

if ($summary.totals.command_errors -gt 0 -or $errors.Count -gt 0) {
    exit 2
}

if (($summary.totals.python_vulnerabilities + $summary.totals.node_vulnerabilities) -gt 0) {
    exit 3
}

exit 0
