# Interactive pipeline for transfection timeseries, plots, AUC, and fit.
# Run from repo: scripts live under scripts/; run from bundle: same folder as pyproject.toml and .uv/

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Wait-PressAnyKeyToExit {
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor DarkGray
    try {
        if (-not [Environment]::UserInteractive -or [Console]::IsInputRedirected) {
            Read-Host "Press Enter to exit"
            return
        }
        while ([Console]::KeyAvailable) {
            [void][Console]::ReadKey($true)
        }
        [void][Console]::ReadKey($true)
    } catch {
        Read-Host "Press Enter to exit"
    }
}

function Exit-Script {
    param([int]$ExitCode = 0)
    Wait-PressAnyKeyToExit
    exit $ExitCode
}

trap {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    Wait-PressAnyKeyToExit
    exit 1
}

$RepoRoot = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "pyproject.toml")) {
    $PSScriptRoot
} else {
    Split-Path -Parent $PSScriptRoot
}

$BundledUv = Join-Path $RepoRoot (Join-Path ".uv" "uv.exe")
if (Test-Path -LiteralPath $BundledUv) {
    $UvExe = $BundledUv
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    $UvExe = "uv"
} else {
    Write-Host "Neither $BundledUv nor 'uv' on PATH was found. Run install.ps1 or install uv." -ForegroundColor Red
    Exit-Script 1
}

# Defaults for `transfection fit` (defined here; always passed explicitly from this script).
$DefaultFitJobs = [Math]::Max(1, [Environment]::ProcessorCount)
$DefaultMaxOnsetMinutes = 0.0

function Read-RequiredNonEmpty {
    param([string]$Prompt)
    while ($true) {
        $line = Read-Host $Prompt
        if ($null -ne $line -and $line.Trim() -ne "") { return $line.Trim() }
        Write-Host "Value required." -ForegroundColor Yellow
    }
}

function Read-RequiredPositiveDouble {
    param([string]$Prompt)
    while ($true) {
        $line = Read-Host $Prompt
        if ($null -eq $line) { continue }
        $t = $line.Trim()
        if ($t -eq "") {
            Write-Host "Value required." -ForegroundColor Yellow
            continue
        }
        $x = 0.0
        if ([double]::TryParse($t, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$x) -and $x -gt 0) {
            return $x
        }
        Write-Host "Enter a number greater than 0 (use . for decimals)." -ForegroundColor Yellow
    }
}

function Read-PositiveIntWithDefault {
    param(
        [string]$Prompt,
        [int]$Default
    )
    $defaultStr = "$Default"
    while ($true) {
        Write-Host "$Prompt [default: $defaultStr]"
        $line = Read-Host "Value (Enter for default)"
        if ($null -eq $line) { continue }
        $t = $line.Trim()
        if ($t -eq "") { return $Default }
        $n = 0
        if ([int]::TryParse($t, [ref]$n) -and $n -ge 1) { return $n }
        Write-Host "Enter an integer >= 1." -ForegroundColor Yellow
    }
}

function Read-NonNegativeDoubleWithDefault {
    param(
        [string]$Prompt,
        [double]$Default
    )
    while ($true) {
        $dStr = $Default.ToString([System.Globalization.CultureInfo]::InvariantCulture)
        Write-Host "$Prompt [default: $dStr; 0 = translation_onset fixed at 0]"
        $line = Read-Host "Value (Enter for default)"
        if ($null -eq $line) { continue }
        $t = $line.Trim()
        if ($t -eq "") { return $Default }
        $x = 0.0
        if ([double]::TryParse($t, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$x) -and $x -ge 0) {
            return $x
        }
        Write-Host "Enter a number >= 0 (use . for decimals)." -ForegroundColor Yellow
    }
}

function Get-TimeseriesMetricsCount {
    param([string]$WorkspacePath)
    $tsDir = Join-Path $WorkspacePath "timeseries"
    if (-not (Test-Path -LiteralPath $tsDir -PathType Container)) { return 0 }
    return @(
        Get-ChildItem -LiteralPath $tsDir -File -Filter "*.csv" |
            Where-Object { $_.BaseName -match '^sc\d+_ch\d+$' }
    ).Count
}

function Find-ResultsAucCsv {
    param([string]$WorkspacePath)
    $results = Join-Path $WorkspacePath "results"
    if (-not (Test-Path -LiteralPath $results -PathType Container)) { return $null }
    $direct = Join-Path $results "auc.csv"
    if (Test-Path -LiteralPath $direct) { return (Resolve-Path -LiteralPath $direct).Path }
    $c = @(
        Get-ChildItem -LiteralPath $results -Filter "*_auc.csv" -File -ErrorAction SilentlyContinue |
            Sort-Object Name
    )
    if ($c.Length -ge 1) { return $c[0].FullName }
    return $null
}

function Find-ResultsFitCsv {
    param([string]$WorkspacePath)
    $results = Join-Path $WorkspacePath "results"
    if (-not (Test-Path -LiteralPath $results -PathType Container)) { return $null }
    $direct = Join-Path $results "fit.csv"
    if (Test-Path -LiteralPath $direct) { return (Resolve-Path -LiteralPath $direct).Path }
    $c = @(
        Get-ChildItem -LiteralPath $results -Filter "*_fit.csv" -File -ErrorAction SilentlyContinue |
            Sort-Object Name
    )
    if ($c.Length -ge 1) { return $c[0].FullName }
    return $null
}

function Invoke-Transfection {
    param([string[]]$ExprArgs)
    Push-Location $RepoRoot
    try {
        Write-Host "`n>> $UvExe run transfection $($ExprArgs -join ' ')`n" -ForegroundColor Cyan
        $allArgs = @("run", "transfection") + $ExprArgs
        # Avoid capturing process stdout as function output (would make $code an Object[]).
        & $UvExe @allArgs | Out-Host
        return [int]$LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Exit-IfFailed {
    param([int]$Code, [string]$Step)
    if ($Code -ne 0) {
        Write-Host "`nStopped: $Step failed (exit $Code)." -ForegroundColor Red
        Exit-Script $Code
    }
}

Write-Host @"

transfection
------------
Runs in order: timeseries (optional) -> plot-timeseries -> auc -> plot-auc -> fit -> plot-fit
Analyze timeseries and fit share --jobs; plot-timeseries, auc, fit, and plot-fit share --interval (minutes per frame); fit also receives --max-onset-minutes (defaults from this script, Enter to accept).
Requires roi/Pos* and slide.json when generating timeseries.

"@

$workspaceRaw = Read-RequiredNonEmpty "Workspace directory (dataset root)"
$workspace = (Resolve-Path -LiteralPath $workspaceRaw).Path

$metricCount = Get-TimeseriesMetricsCount $workspace
$runTimeseries = $true
if ($metricCount -gt 0) {
    Write-Host "timeseries/ already contains $metricCount workspace metrics CSV (sc*_ch*.csv)." -ForegroundColor Yellow
    while ($true) {
        $c = Read-Host "[D]elete timeseries/ and regenerate, or [S]kip timeseries (use existing)"
        $k = if ($null -eq $c) { "" } else { $c.Trim().ToUpperInvariant() }
        if ($k -eq "D") {
            $tsDir = Join-Path $workspace "timeseries"
            Remove-Item -LiteralPath $tsDir -Recurse -Force
            Write-Host "Removed timeseries/." -ForegroundColor Yellow
            $runTimeseries = $true
            break
        }
        if ($k -eq "S") {
            $runTimeseries = $false
            break
        }
        Write-Host "Enter D or S." -ForegroundColor Yellow
    }
}

$correctionArgs = @()
$interval = Read-RequiredPositiveDouble "Frame interval in minutes (for plot-timeseries, auc, fit, plot-fit)"
$intervalStr = $interval.ToString([System.Globalization.CultureInfo]::InvariantCulture)

# Single-quoted literals: PS 5.1 misparses & and (--foo) inside double-quoted strings (PS 7 is fine).
Write-Host ("`n" + 'Analyze timeseries & fit - set --jobs and (for fit) --max-onset-minutes (defaults from this script):') -ForegroundColor DarkGray
$fitJobs = Read-PositiveIntWithDefault -Prompt 'Worker processes for timeseries & fit (--jobs)' -Default $DefaultFitJobs
$fitMaxOnset = Read-NonNegativeDoubleWithDefault -Prompt 'Max onset minutes (--max-onset-minutes)' -Default $DefaultMaxOnsetMinutes
$fitMaxOnsetStr = $fitMaxOnset.ToString([System.Globalization.CultureInfo]::InvariantCulture)

if ($runTimeseries) {
    $slideDefault = Join-Path $workspace "slide.json"
    Write-Host "Slide mapping JSON path [default: $slideDefault]"
    $slideIn = Read-Host "Path (Enter for default)"
    $slidePathRaw = if ([string]::IsNullOrWhiteSpace($slideIn)) { $slideDefault } else { $slideIn.Trim() }
    $slidePath = (Resolve-Path -LiteralPath $slidePathRaw).Path
    Write-Host "Correction quartile for timeseries [0.25]"
    $qIn = Read-Host "Value (Enter for default)"
    if (-not [string]::IsNullOrWhiteSpace($qIn)) {
        $correctionArgs += @("--correction-quartile", $qIn.Trim())
    }

    $code = Invoke-Transfection (@(
        "timeseries", $workspace,
        "--sample", $slidePath,
        "--jobs", "$fitJobs"
    ) + $correctionArgs)
    Exit-IfFailed $code "analyze timeseries"
}

$tsDirForPlots = Join-Path $workspace "timeseries"
if (-not (Test-Path -LiteralPath $tsDirForPlots -PathType Container)) {
    Write-Host "No timeseries/ directory - run timeseries first." -ForegroundColor Red
    Exit-Script 1
}
if ((Get-TimeseriesMetricsCount $workspace) -lt 1) {
    Write-Host "timeseries/ has no workspace metrics CSVs (sc*_ch*.csv)." -ForegroundColor Red
    Exit-Script 1
}

$code = Invoke-Transfection @(
    "plot-timeseries", $tsDirForPlots,
    "--interval", $intervalStr
)
Exit-IfFailed $code "analyze plot-timeseries"

$code = Invoke-Transfection @(
    "auc", $workspace,
    "--interval", $intervalStr
)
Exit-IfFailed $code "analyze auc"

$aucCsv = Find-ResultsAucCsv $workspace
if ([string]::IsNullOrEmpty($aucCsv)) {
    Write-Host "Could not find auc.csv or *_auc.csv under results/." -ForegroundColor Red
    Exit-Script 1
}

$code = Invoke-Transfection @("plot-auc", $aucCsv)
Exit-IfFailed $code "analyze plot-auc"

$code = Invoke-Transfection @(
    "fit", $workspace,
    "--interval", $intervalStr,
    "--jobs", "$fitJobs",
    "--max-onset-minutes", $fitMaxOnsetStr
)
Exit-IfFailed $code "analyze fit"

$fitCsv = Find-ResultsFitCsv $workspace
if ([string]::IsNullOrEmpty($fitCsv)) {
    Write-Host "Could not find fit.csv or *_fit.csv under results/." -ForegroundColor Red
    Exit-Script 1
}

$code = Invoke-Transfection @(
    "plot-fit", $fitCsv,
    "--interval", $intervalStr
)
Exit-IfFailed $code "analyze plot-fit"

Write-Host "`nPipeline finished." -ForegroundColor Green
Exit-Script 0
