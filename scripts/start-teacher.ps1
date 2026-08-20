# One-window helper for grading: venv + deps + spaCy + uvicorn, then open demo chat.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File .\scripts\start-teacher.ps1

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

$apiPort = 8888
$url = "http://127.0.0.1:$apiPort/chat"

if (-not (Test-Path (Join-Path $root ".env"))) {
  Write-Host "No .env found — copying .env.example. Edit .env (UPSTREAM_* keys) then run this script again." -ForegroundColor Yellow
  Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
  exit 1
}

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "Creating .venv …" -ForegroundColor Cyan
  python -m venv (Join-Path $root ".venv")
}

Write-Host "Installing Python deps (editable) …" -ForegroundColor Cyan
& $venvPy -m pip install -q -U pip
& $venvPy -m pip install -q -e ".[dev]"

Write-Host "Checking spaCy model …" -ForegroundColor Cyan
& $venvPy -c "import spacy; spacy.load('en_core_web_lg')" 2>$null
if ($LASTEXITCODE -ne 0) {
  & $venvPy -m spacy download en_core_web_lg
}

Write-Host ""
Write-Host "Starting API on http://127.0.0.1:$apiPort" -ForegroundColor Green
Write-Host "Demo chat: $url" -ForegroundColor Green
Write-Host "API docs:  http://127.0.0.1:$apiPort/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

Start-Sleep -Milliseconds 800
Start-Process $url

& $venvPy -m uvicorn app.proxy.main:app --host 127.0.0.1 --port $apiPort
