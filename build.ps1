# Builds dist\Chess2D\Chess2D.exe (PyInstaller) and dist\Chess2D-Setup-<version>.exe (Inno Setup).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1 [-SkipInstaller]
param([switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$version = (& $py -c "import chess2d; print(chess2d.VERSION)").Trim()
Write-Host "Building Chess2D $version" -ForegroundColor Cyan

& $py -m pip install --quiet -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE) { throw "pip install failed" }

& $py -m PyInstaller --noconfirm --clean --windowed --name Chess2D --icon chess.ico `
    --add-data "pieces;pieces" --add-data "sound;sound" --add-data "stockfish;stockfish" `
    --add-data "chess.ico;." --collect-submodules anthropic `
    --exclude-module pytest --exclude-module numpy `
    Chess2D.py
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# Smoke-test the frozen app without opening a window.
$exe = "dist\Chess2D\Chess2D.exe"
$proc = Start-Process $exe -ArgumentList "--selftest" -Wait -PassThru
Get-Content "dist\Chess2D\selftest.log"
Remove-Item "dist\Chess2D\selftest.log" -ErrorAction SilentlyContinue
if ($proc.ExitCode -ne 0) { throw "Self-test of the built exe failed" }

if ($SkipInstaller) { return }
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$version" "installer\Chess2D.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }
Write-Host "Installer: dist\Chess2D-Setup-$version.exe" -ForegroundColor Green
