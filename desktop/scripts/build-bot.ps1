$ErrorActionPreference = "Stop"

$desktopRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $desktopRoot
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$entrypoint = Join-Path $projectRoot "main.py"
$output = Join-Path $desktopRoot "src-tauri\binaries"
$work = Join-Path $desktopRoot ".pyinstaller"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found at $python. Create venv and install requirements first."
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing. Run: .\venv\Scripts\python.exe -m pip install pyinstaller"
}

New-Item -ItemType Directory -Force -Path $output | Out-Null

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name dragonmine-bot `
    --distpath $output `
    --workpath (Join-Path $work "work") `
    --specpath $work `
    $entrypoint

if ($LASTEXITCODE -ne 0) {
    throw "The DragonMine bot runtime could not be packaged."
}

Write-Host "Bundled bot runtime: $(Join-Path $output 'dragonmine-bot.exe')"
