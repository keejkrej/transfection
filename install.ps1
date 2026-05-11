$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$UvDir = Join-Path $Root ".uv"
$VenvDir = Join-Path $Root ".venv"
$Arch = "x86_64-pc-windows-msvc"

$UvExe = Join-Path $UvDir "uv.exe"

if (-not (Test-Path $UvExe)) {
    New-Item -ItemType Directory -Force -Path $UvDir | Out-Null
    $ZipName = "uv-$Arch.zip"
    $Url = "https://github.com/astral-sh/uv/releases/latest/download/$ZipName"
    $ZipPath = Join-Path $UvDir $ZipName
    Write-Host "Downloading uv (latest release)..."
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $UvDir -Force
    $Nested = Get-ChildItem -Path $UvDir -Recurse -Filter "uv.exe" | Select-Object -First 1
    if ($Nested) {
        Move-Item -Path $Nested.FullName -Destination $UvExe -Force
        $NestedDir = $Nested.DirectoryName
        if ($NestedDir -ne $UvDir) {
            Remove-Item -Path $NestedDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $ZipPath
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating venv..."
    & $UvExe venv $VenvDir
}

Write-Host "Installing package..."
& $UvExe sync

Write-Host "Done."
Write-Host ""
Write-Host "Run transfection with:"
Write-Host "  .\$([IO.Path]::Combine('.uv', 'uv.exe')) run transfection ..."
