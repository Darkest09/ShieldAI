# ShieldAI Launcher — one-window control panel (Windows / PowerShell + WinForms).
#
# Run it via the double-clickable wrapper  ShieldAI.cmd , or directly:
#   powershell -NoProfile -ExecutionPolicy Bypass -STA -File .\ShieldAI-Launcher.ps1
#
# It can install deps, start/stop the API + dashboard, open the demo pages,
# verify the audit hash chain, and run the test suite — no terminal needed.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'

# --- Paths & config -------------------------------------------------------
$root      = $PSScriptRoot
$venvPy    = Join-Path $root '.venv\Scripts\python.exe'
$dashDir   = Join-Path $root 'app\dashboard'
$apiPort   = 8888
$dashPort  = 5173
$chatUrl   = "http://127.0.0.1:$apiPort/chat"
$docsUrl   = "http://127.0.0.1:$apiPort/docs"
$dashUrl   = "http://127.0.0.1:$dashPort"

# Tracked child processes (the launched PowerShell windows)
$script:apiProc  = $null
$script:dashProc = $null

function Get-InternalToken {
  $envFile = Join-Path $root '.env'
  if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
      if ($line -match '^\s*SHIELD_INTERNAL_TOKEN\s*=\s*(.+?)\s*$') { return $Matches[1] }
    }
  }
  return 'dev-internal'
}

function Test-Port($port) {
  $c = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(300) -and $c.Connected) { $c.EndConnect($iar); return $true }
    return $false
  } catch { return $false } finally { $c.Close() }
}

function Stop-Tree($proc) {
  if ($proc -and -not $proc.HasExited) {
    try { taskkill /PID $proc.Id /T /F 2>&1 | Out-Null } catch {}
  }
}

# --- Form ----------------------------------------------------------------
$form               = New-Object System.Windows.Forms.Form
$form.Text          = 'ShieldAI Launcher'
$form.Size          = New-Object System.Drawing.Size(560, 620)
$form.StartPosition = 'CenterScreen'
$form.Font          = New-Object System.Drawing.Font('Segoe UI', 9)
$form.BackColor     = [System.Drawing.Color]::FromArgb(24, 24, 27)
$form.ForeColor     = [System.Drawing.Color]::FromArgb(228, 228, 231)

$title              = New-Object System.Windows.Forms.Label
$title.Text         = 'ShieldAI — Privacy Proxy Control Panel'
$title.Font         = New-Object System.Drawing.Font('Segoe UI Semibold', 13)
$title.AutoSize     = $true
$title.Location     = New-Object System.Drawing.Point(18, 16)
$form.Controls.Add($title)

# Status lights
$lblApi             = New-Object System.Windows.Forms.Label
$lblApi.AutoSize    = $true
$lblApi.Location    = New-Object System.Drawing.Point(20, 52)
$form.Controls.Add($lblApi)

$lblDash            = New-Object System.Windows.Forms.Label
$lblDash.AutoSize   = $true
$lblDash.Location   = New-Object System.Drawing.Point(280, 52)
$form.Controls.Add($lblDash)

# Log box
$log                = New-Object System.Windows.Forms.TextBox
$log.Multiline      = $true
$log.ReadOnly       = $true
$log.ScrollBars     = 'Vertical'
$log.BackColor      = [System.Drawing.Color]::FromArgb(15, 15, 17)
$log.ForeColor      = [System.Drawing.Color]::FromArgb(190, 220, 190)
$log.Font           = New-Object System.Drawing.Font('Consolas', 9)
$log.Location       = New-Object System.Drawing.Point(20, 360)
$log.Size           = New-Object System.Drawing.Size(505, 210)
$form.Controls.Add($log)

function Write-Log($msg) {
  $ts = (Get-Date).ToString('HH:mm:ss')
  $log.AppendText("[$ts] $msg`r`n")
}

# Button factory
$btnIndex = 0
function New-Btn($text, $x, $y, $w, $onClick) {
  $b = New-Object System.Windows.Forms.Button
  $b.Text     = $text
  $b.Location = New-Object System.Drawing.Point($x, $y)
  $b.Size     = New-Object System.Drawing.Size($w, 40)
  $b.FlatStyle = 'Flat'
  $b.BackColor = [System.Drawing.Color]::FromArgb(39, 39, 42)
  $b.ForeColor = [System.Drawing.Color]::FromArgb(244, 244, 245)
  $b.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(63, 63, 70)
  $b.Add_Click($onClick)
  $form.Controls.Add($b)
  return $b
}

# --- Actions -------------------------------------------------------------
$doSetup = {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Log 'Python not found on PATH. Install Python 3.11+ (check "Add to PATH").'
    return
  }
  if (-not (Test-Path (Join-Path $root '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
    Write-Log 'Created .env from .env.example — set UPSTREAM_API_KEY in it for live calls.'
  }
  Write-Log 'Launching setup in a new window (venv + deps + spaCy model). This can take minutes…'
  $cmd = @"
Set-Location '$root'
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -c "import spacy; spacy.load('en_core_web_lg')" 2>`$null
if (`$LASTEXITCODE -ne 0) { .\.venv\Scripts\python.exe -m spacy download en_core_web_lg }
Write-Host ''
Write-Host 'Setup complete. You can close this window and click Start API.' -ForegroundColor Green
"@
  Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command', $cmd) -WorkingDirectory $root | Out-Null
}

$doStartApi = {
  if (Test-Port $apiPort) { Write-Log "API already running on $apiPort."; return }
  if (-not (Test-Path $venvPy)) { Write-Log 'No .venv yet — click "1. Setup / Install" first.'; return }
  Write-Log "Starting API on http://127.0.0.1:$apiPort …"
  $cmd = "& '$venvPy' -m uvicorn app.proxy.main:app --reload --host 127.0.0.1 --port $apiPort"
  $script:apiProc = Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command', $cmd) -WorkingDirectory $root -PassThru
}

$doStartDash = {
  if (Test-Port $dashPort) { Write-Log "Dashboard already running on $dashPort."; return }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Log 'npm not found — install Node.js 20+.'; return }
  Write-Log "Starting dashboard on $dashUrl (npm install runs first if needed)…"
  $cmd = "if (-not (Test-Path node_modules)) { npm install }; npm run dev -- --host 127.0.0.1 --port $dashPort"
  $script:dashProc = Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command', $cmd) -WorkingDirectory $dashDir -PassThru
}

$doStopApi  = { Stop-Tree $script:apiProc;  $script:apiProc  = $null; Write-Log 'Stopped API.' }
$doStopDash = { Stop-Tree $script:dashProc; $script:dashProc = $null; Write-Log 'Stopped dashboard.' }

$doVerify = {
  if (-not (Test-Port $apiPort)) { Write-Log 'API not running — start it first.'; return }
  try {
    $tok = Get-InternalToken
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/internal/audit/verify" -Headers @{ 'X-Shield-Internal-Token' = $tok } -TimeoutSec 5
    if ($r.ok) {
      Write-Log "Audit chain INTACT — $($r.rows_checked) rows verified."
    } else {
      Write-Log "Audit chain BROKEN at row #$($r.broken_at_id): $($r.reason)"
    }
  } catch { Write-Log "Verify failed: $($_.Exception.Message)" }
}

$doTests = {
  if (-not (Test-Path $venvPy)) { Write-Log 'No .venv yet — run Setup first.'; return }
  Write-Log 'Running pytest in a new window…'
  $cmd = "& '$venvPy' -m pytest tests -q; Write-Host ''; Write-Host 'Done. Close this window.' -ForegroundColor Cyan"
  Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command', $cmd) -WorkingDirectory $root | Out-Null
}

$doStopAll = { & $doStopApi; & $doStopDash }

# --- Layout buttons ------------------------------------------------------
$col1 = 20; $col2 = 280; $wFull = 505; $wHalf = 245
New-Btn '1. Setup / Install deps'   $col1 90  $wFull $doSetup        | Out-Null
New-Btn 'Start API'                 $col1 138 $wHalf $doStartApi     | Out-Null
New-Btn 'Stop API'                  $col2 138 $wHalf $doStopApi      | Out-Null
New-Btn 'Start Dashboard'           $col1 186 $wHalf $doStartDash    | Out-Null
New-Btn 'Stop Dashboard'            $col2 186 $wHalf $doStopDash     | Out-Null
New-Btn 'Open Chat'                 $col1 234 160   { Start-Process $chatUrl } | Out-Null
New-Btn 'Open Dashboard'            190   234 160   { Start-Process $dashUrl } | Out-Null
New-Btn 'Open API Docs'             360   234 165   { Start-Process $docsUrl } | Out-Null
New-Btn 'Verify Audit Chain'        $col1 282 $wHalf $doVerify       | Out-Null
New-Btn 'Run Tests'                 $col2 282 $wHalf $doTests        | Out-Null
$btnStopAll = New-Btn 'Stop Everything' $col1 326 $wFull $doStopAll
$btnStopAll.BackColor = [System.Drawing.Color]::FromArgb(80, 30, 30)

# --- Status timer --------------------------------------------------------
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 2500
$timer.Add_Tick({
  if (Test-Port $apiPort) {
    $lblApi.Text = "API  ●  running ($apiPort)"
    $lblApi.ForeColor = [System.Drawing.Color]::FromArgb(110, 220, 130)
  } else {
    $lblApi.Text = 'API  ●  stopped'
    $lblApi.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 165)
  }
  if (Test-Port $dashPort) {
    $lblDash.Text = "Dashboard  ●  running ($dashPort)"
    $lblDash.ForeColor = [System.Drawing.Color]::FromArgb(110, 220, 130)
  } else {
    $lblDash.Text = 'Dashboard  ●  stopped'
    $lblDash.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 165)
  }
})
$timer.Start()

$form.Add_Shown({
  Write-Log 'Ready. First time? Click "1. Setup / Install deps", then "Start API".'
  Write-Log "Repo: $root"
})

# Offer to stop servers on close
$form.Add_FormClosing({
  if (($script:apiProc -and -not $script:apiProc.HasExited) -or ($script:dashProc -and -not $script:dashProc.HasExited)) {
    $r = [System.Windows.Forms.MessageBox]::Show(
      'Stop the running API / dashboard before exiting?',
      'ShieldAI Launcher', 'YesNoCancel', 'Question')
    if ($r -eq 'Cancel') { $_.Cancel = $true; return }
    if ($r -eq 'Yes') { & $doStopAll }
  }
})

[void]$form.ShowDialog()
