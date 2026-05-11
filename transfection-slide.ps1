# Interactive helper to build --sample and run `transfection slide config`.
# Run from repo: scripts live under scripts/; run from bundle: same folder as pyproject.toml and .uv/

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
    exit 1
}

function Read-RequiredNonEmpty {
    param(
        [string]$Prompt
    )
    while ($true) {
        $line = Read-Host $Prompt
        if ($null -ne $line -and $line.Trim() -ne "") {
            return $line.Trim()
        }
        Write-Host "Value required." -ForegroundColor Yellow
    }
}

function Read-RequiredNonNegativeInt {
    param(
        [string]$Prompt
    )
    while ($true) {
        $line = Read-Host $Prompt
        if ($null -eq $line) {
            continue
        }
        $t = $line.Trim()
        if ($t -eq "") {
            Write-Host "Value required." -ForegroundColor Yellow
            continue
        }
        $n = 0
        if ([int]::TryParse($t, [ref]$n) -and $n -ge 0) {
            return $n
        }
        Write-Host "Enter a non-negative integer." -ForegroundColor Yellow
    }
}

Write-Host @"

transfection slide
------------------
Slide channel ids are assigned automatically (0, 1, 2, … in entry order; not part of --sample text).
Each mapping: sample_name, then image channel, then positions (e.g. 10,11 or 0:12 for a range).
Compact fragments look like positions@image_channel#sample_name and are joined with | for --sample.
Do not use | # @ in the sample_name (they are syntax characters).

"@

$segments = New-Object System.Collections.Generic.List[string]
$nextSlideCh = 0

Write-Host "Add one or more slide channel mappings. Blank sample_name when done.`n"

while ($true) {
    $nameLine = Read-Host "Sample name (blank when done)"
    $name = if ($null -eq $nameLine) { "" } else { $nameLine.Trim() }
    if ($name -eq "") {
        if ($segments.Count -eq 0) {
            Write-Host "Add at least one mapping before finishing." -ForegroundColor Yellow
            continue
        }
        break
    }
    if ($name -match '[|#@]') {
        Write-Host "sample_name must not contain | # or @" -ForegroundColor Yellow
        continue
    }

    $imageCh = Read-RequiredNonNegativeInt "Image channel"
    $positions = Read-RequiredNonEmpty "Positions (e.g. 10,11 or 0:12 for a range)"

    $slideCh = $nextSlideCh
    $nextSlideCh++
    $compact = "${positions}@${imageCh}#${name}"
    $segments.Add($compact)
    Write-Host "Added slide_channel=$slideCh | positions=$positions | image_channel=$imageCh | sample_name=$name" -ForegroundColor Green
    Write-Host "  (compact --sample fragment: $compact)`n" -ForegroundColor DarkGray
}

$sampleArg = $segments -join "|"

$outputRaw = Read-RequiredNonEmpty "Output path for slide.json"
$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($outputRaw)

$forceArgs = @()
if (Test-Path -LiteralPath $outputPath) {
    $ow = Read-Host "Output exists. Overwrite? [y/N]"
    if ($ow -eq "y" -or $ow -eq "Y") {
        $forceArgs += "--force"
    }
}

Write-Host "`nRunning: & `"$UvExe`" run transfection slide config ...`n" -ForegroundColor Cyan

Push-Location $RepoRoot
try {
    $arguments = @(
        "run", "transfection", "slide", "config",
        "--sample", $sampleArg,
        "--output", $outputPath
    ) + $forceArgs
    & $UvExe @arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
