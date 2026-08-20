# Starts ShieldAI backend (FastAPI) and frontend (Vite) in separate PowerShell windows.
# From repo root:  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Test-Path (Join-Path $root ".env"))) {
  Write-Host "Missing .env — copy from .env.example or run setup once." -ForegroundColor Yellow
}

# Default 8888 — many Windows setups block 8010/8000 (WinError 10013). Match app/dashboard .env VITE_SHIELD_API_URL.
$apiPort = 8888
Write-Host "Backend: http://127.0.0.1:$apiPort/docs" -ForegroundColor Cyan
Write-Host "Dashboard: http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "Set UPSTREAM_API_KEY (or OPENAI_API_KEY) in .env for live upstream calls." -ForegroundColor Yellow

Start-Process powershell -WorkingDirectory $root -ArgumentList @(
  "-NoExit", "-Command",
  "python -m uvicorn app.proxy.main:app --reload --host 127.0.0.1 --port $apiPort"
)

Start-Process powershell -WorkingDirectory (Join-Path $root "app\dashboard") -ArgumentList @(
  "-NoExit", "-Command",
  "npm run dev -- --host 127.0.0.1 --port 5173"
)
