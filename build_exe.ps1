# Builds border-markers/dist/BorderMarkers.exe, a single file that needs no Python.
#
# Run it from Windows PowerShell, from anywhere:
#     powershell -ExecutionPolicy Bypass -File Border-markersRS3\build_exe.ps1
#
# PyInstaller goes into a throwaway venv under Border-markersRS3\build, so nothing is
# added to your main Python install. Delete Border-markersRS3\build to reclaim the space.
# The app itself still uses only the standard library; PyInstaller is a build tool.

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $here "build"
$venv = Join-Path $build "venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating a build venv..."
    python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create a venv. Is Python installed?" }
}

Write-Host "Installing PyInstaller..."
& $python -m pip install --quiet --disable-pip-version-check pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }

# PyInstaller refuses to run from some folders, so always work from the source folder.
Push-Location $here
try {
    Write-Host "Building the exe..."
    & $python -m PyInstaller `
        --noconfirm `
        --onefile `
        --windowed `
        --name BorderMarkers `
        --distpath (Join-Path $here "dist") `
        --workpath (Join-Path $build "work") `
        --specpath $build `
        --paths $here `
        (Join-Path $here "app.py")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
}
finally {
    Pop-Location
}

$exe = Join-Path $here "dist\BorderMarkers.exe"
$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $exe ($size MB)"
