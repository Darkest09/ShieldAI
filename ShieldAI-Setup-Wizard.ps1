# ShieldAI Setup Wizard - an installer-style, step-by-step wizard that gets the
# project running. Each page CHECKS whether a step is already done (green) and,
# if not, gives you a button to DO it. Next unlocks once the step is satisfied.
#
# Launch via  ShieldAI-Setup.cmd , or:
#   powershell -NoProfile -ExecutionPolicy Bypass -STA -File .\ShieldAI-Setup-Wizard.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = "Stop"

$root     = $PSScriptRoot
$venvPy   = Join-Path $root ".venv\Scripts\python.exe"
$dashDir  = Join-Path $root "app\dashboard"
$apiPort  = 8888
$dashPort = 5173
$script:apiProc = $null
$script:dashProc = $null

# --- helpers ---------------------------------------------------------------
function Has-Cmd($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }
function Test-Port($port) {
  $c = New-Object System.Net.Sockets.TcpClient
  try { $iar = $c.BeginConnect('127.0.0.1',$port,$null,$null)
        if ($iar.AsyncWaitHandle.WaitOne(300) -and $c.Connected) { $c.EndConnect($iar); return $true } return $false }
  catch { return $false } finally { $c.Close() }
}
function Py-Ok($expr) {
  if (-not (Test-Path $venvPy)) { return $false }
  & $venvPy -c $expr 2>$null
  return ($LASTEXITCODE -eq 0)
}
function Console($cmd) {
  Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command',$cmd) -WorkingDirectory $root | Out-Null
}
function Start-Api {
  if (Test-Port $apiPort) { return }
  $script:apiProc = Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command',
    "& '$venvPy' -m uvicorn app.proxy.main:app --host 127.0.0.1 --port $apiPort") -WorkingDirectory $root -PassThru
}
function Start-Dash {
  if (Test-Port $dashPort) { return }
  $script:dashProc = Start-Process powershell -ArgumentList @('-NoProfile','-NoExit','-Command',
    "if (-not (Test-Path node_modules)) { npm install }; npm run dev -- --host 127.0.0.1 --port $dashPort") -WorkingDirectory $dashDir -PassThru
}
function Stop-All {
  foreach ($p in @($script:apiProc,$script:dashProc)) {
    if ($p -and -not $p.HasExited) { try { taskkill /PID $p.Id /T /F 2>&1 | Out-Null } catch {} }
  }
}

# --- steps -----------------------------------------------------------------
# Each: Title, Desc, Check (returns @{ok=;msg=}), optional Action(s) = @{L=;A=}, Optional
$steps = @(
  @{ Title = "Welcome";
     Desc  = "This wizard will check your setup and get ShieldAI running, one step at a time. Green means a step is already done - just click Next. Click 'Do it' only when a step is not yet satisfied.";
     Check = { @{ ok = $true; msg = "Ready to begin. Click Next." } };
     Acts  = @() },

  @{ Title = "Step 1 of 6  -  Prerequisites";
     Desc  = "ShieldAI needs Python 3.11+ (required) and Node.js (only for the web dashboard). This checks they are installed.";
     Check = {
        $py = Has-Cmd "python"; $node = Has-Cmd "npm"
        $msg = "Python: " + (&{ if($py){"found"}else{"MISSING - install from python.org"} }) + "   |   Node/npm: " + (&{ if($node){"found"}else{"missing (dashboard only)"} })
        @{ ok = $py; msg = $msg } };
     Acts  = @( @{ L="Open python.org"; A={ Start-Process "https://www.python.org/downloads/" } } ) },

  @{ Title = "Step 2 of 6  -  Python packages";
     Desc  = "Creates the .venv virtual environment and installs the backend (FastAPI, Presidio, etc.). Takes a few minutes the first time. Click 'Re-check' after the install window finishes.";
     Check = {
        $ok = Py-Ok "import fastapi, presidio_analyzer, cryptography"
        @{ ok = $ok; msg = (&{ if($ok){"Backend packages installed."}else{"Not installed yet - click 'Install backend'."} }) } };
     Acts  = @( @{ L="Install backend"; A={ Console "if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }; & '.\.venv\Scripts\python.exe' -m pip install -U pip; & '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'; Write-Host ''; Write-Host 'DONE - go back to the wizard and click Re-check.' -ForegroundColor Green" } } ) },

  @{ Title = "Step 3 of 6  -  AI language model";
     Desc  = "Presidio needs the spaCy 'en_core_web_lg' model (~400 MB) to detect names. This downloads it if missing.";
     Check = {
        $ok = Py-Ok "import spacy; spacy.load('en_core_web_lg')"
        @{ ok = $ok; msg = (&{ if($ok){"spaCy model present."}else{"Not downloaded yet - click 'Download model'."} }) } };
     Acts  = @( @{ L="Download model"; A={ Console "& '.\.venv\Scripts\python.exe' -m spacy download en_core_web_lg; Write-Host ''; Write-Host 'DONE - click Re-check in the wizard.' -ForegroundColor Green" } } ) },

  @{ Title = "Step 4 of 6  -  Hugging Face model (optional)";
     Desc  = "The primary detector is a Hugging Face transformer (best accuracy, ~3-4 GB). OPTIONAL: if you skip this, the app auto-falls back to the fast spaCy model. You can Next past this either way.";
     Optional = $true;
     Check = {
        $ok = Py-Ok "import torch, transformers, spacy_huggingface_pipelines"
        @{ ok = $ok; msg = (&{ if($ok){"Transformers backend ready (primary mode)."}else{"Not installed - app will use the fast spaCy fallback. Optional."} }) } };
     Acts  = @( @{ L="Install transformers (big)"; A={ Console "& '.\.venv\Scripts\python.exe' -m pip install torch --index-url https://download.pytorch.org/whl/cpu; & '.\.venv\Scripts\python.exe' -m pip install -e '.[transformers]'; Write-Host ''; Write-Host 'DONE - click Re-check.' -ForegroundColor Green" } } ) },

  @{ Title = "Step 5 of 6  -  Configuration (.env)";
     Desc  = "ShieldAI reads settings from a .env file. This creates one from the template if missing. (Add your upstream LLM key to .env for live chat; not needed for tests.)";
     Check = {
        $ok = Test-Path (Join-Path $root ".env")
        @{ ok = $ok; msg = (&{ if($ok){".env exists."}else{"No .env yet - click 'Create .env'."} }) } };
     Acts  = @( @{ L="Create .env"; A={ Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env") -ErrorAction SilentlyContinue } } ) },

  @{ Title = "Step 6 of 6  -  Run it";
     Desc  = "Start the API (and optionally the dashboard), then open the app in your browser. First API start takes ~10s while the model loads. The status line above shows when each is running.";
     Check = {
        $api = Test-Port $apiPort
        @{ ok = $api; msg = (&{ if($api){"API is running. Open the chat / dashboard below."}else{"Click 'Start API', wait for the light above to turn green."} }) } };
     Acts  = @(
        @{ L="Start API"; A={ Start-Api } },
        @{ L="Start Dashboard"; A={ Start-Dash } },
        @{ L="Open Chat"; A={ Start-Process "http://127.0.0.1:$apiPort/chat" } },
        @{ L="Open Dashboard"; A={ Start-Process "http://127.0.0.1:$dashPort" } },
        @{ L="Open API Docs"; A={ Start-Process "http://127.0.0.1:$apiPort/docs" } }
     ) },

  @{ Title = "All done!";
     Desc  = "ShieldAI is set up. Use the buttons on the previous step to open the app any time. To present it to your teacher, run ShieldAI-Demo.cmd (guided walkthrough). To stop the servers, click below.";
     Check = { @{ ok = $true; msg = "Setup complete." } };
     Acts  = @( @{ L="Stop servers"; A={ Stop-All } } ) }
)
$script:idx = 0

# --- UI --------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "ShieldAI - Setup Wizard"
$form.Size = New-Object System.Drawing.Size(720, 600)
$form.StartPosition = "CenterScreen"
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$form.BackColor = [System.Drawing.Color]::FromArgb(24,24,27)
$form.ForeColor = [System.Drawing.Color]::FromArgb(228,228,231)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.AutoSize = $true; $lblStatus.Location = New-Object System.Drawing.Point(20,12)
$form.Controls.Add($lblStatus)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 15)
$lblTitle.Location = New-Object System.Drawing.Point(20,40); $lblTitle.Size = New-Object System.Drawing.Size(670,30)
$form.Controls.Add($lblTitle)

$txtDesc = New-Object System.Windows.Forms.TextBox
$txtDesc.Multiline=$true; $txtDesc.ReadOnly=$true; $txtDesc.BorderStyle="None"
$txtDesc.BackColor=[System.Drawing.Color]::FromArgb(24,24,27); $txtDesc.ForeColor=[System.Drawing.Color]::FromArgb(210,210,215)
$txtDesc.Font=New-Object System.Drawing.Font("Segoe UI",10.5)
$txtDesc.Location=New-Object System.Drawing.Point(20,76); $txtDesc.Size=New-Object System.Drawing.Size(670,90)
$form.Controls.Add($txtDesc)

$lblState = New-Object System.Windows.Forms.Label
$lblState.Location = New-Object System.Drawing.Point(20,176); $lblState.Size = New-Object System.Drawing.Size(670,48)
$lblState.Font = New-Object System.Drawing.Font("Segoe UI Semibold",10.5)
$form.Controls.Add($lblState)

$flow = New-Object System.Windows.Forms.FlowLayoutPanel
$flow.Location = New-Object System.Drawing.Point(18,232); $flow.Size = New-Object System.Drawing.Size(680,180); $flow.AutoScroll=$true
$form.Controls.Add($flow)

$btnRecheck = New-Object System.Windows.Forms.Button
$btnRecheck.Text="Re-check"; $btnRecheck.Size=New-Object System.Drawing.Size(120,38)
$btnRecheck.Location=New-Object System.Drawing.Point(290,500); $btnRecheck.FlatStyle="Flat"
$btnRecheck.BackColor=[System.Drawing.Color]::FromArgb(39,39,42); $btnRecheck.ForeColor=[System.Drawing.Color]::White
$form.Controls.Add($btnRecheck)

$btnBack = New-Object System.Windows.Forms.Button
$btnBack.Text="< Back"; $btnBack.Size=New-Object System.Drawing.Size(110,38)
$btnBack.Location=New-Object System.Drawing.Point(20,500); $btnBack.FlatStyle="Flat"
$btnBack.BackColor=[System.Drawing.Color]::FromArgb(39,39,42); $btnBack.ForeColor=[System.Drawing.Color]::White
$form.Controls.Add($btnBack)

$btnNext = New-Object System.Windows.Forms.Button
$btnNext.Text="Next >"; $btnNext.Size=New-Object System.Drawing.Size(150,38)
$btnNext.Location=New-Object System.Drawing.Point(540,500); $btnNext.FlatStyle="Flat"
$btnNext.BackColor=[System.Drawing.Color]::FromArgb(34,80,120); $btnNext.ForeColor=[System.Drawing.Color]::White
$form.Controls.Add($btnNext)

function Render {
  $s = $steps[$script:idx]
  $lblTitle.Text = $s.Title
  $txtDesc.Text = $s.Desc
  $flow.Controls.Clear()
  foreach ($a in $s.Acts) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text=$a.L; $b.AutoSize=$true; $b.Height=38; $b.Margin=New-Object System.Windows.Forms.Padding(4)
    $b.FlatStyle="Flat"; $b.BackColor=[System.Drawing.Color]::FromArgb(45,45,50); $b.ForeColor=[System.Drawing.Color]::White
    $act = $a.A
    $b.Add_Click({ & $act; Run-Check }.GetNewClosure())
    $flow.Controls.Add($b)
  }
  $btnBack.Enabled = ($script:idx -gt 0)
  $btnRecheck.Visible = ($null -ne $s.Check)
  $btnNext.Text = "Next >"; if ($script:idx -eq $steps.Count - 1) { $btnNext.Text = "Finish" }
  Run-Check
}

function Run-Check {
  $s = $steps[$script:idx]
  $green=[System.Drawing.Color]::FromArgb(110,220,130); $amber=[System.Drawing.Color]::FromArgb(230,180,90)
  if ($null -ne $s.Check) {
    $r = & $s.Check
    if ($r.ok) { $lblState.ForeColor=$green; $lblState.Text=("OK  -  " + $r.msg) }
    else       { $lblState.ForeColor=$amber; $lblState.Text=("TODO  -  " + $r.msg) }
    $btnNext.Enabled = ($r.ok -or $s.Optional)
  } else { $lblState.Text=""; $btnNext.Enabled=$true }
}

$btnRecheck.Add_Click({ Run-Check })
$btnBack.Add_Click({ if ($script:idx -gt 0) { $script:idx--; Render } })
$btnNext.Add_Click({
  if ($script:idx -lt $steps.Count - 1) { $script:idx++; Render } else { $form.Close() }
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 2000
$timer.Add_Tick({
  $a = "stopped"; if (Test-Port $apiPort) { $a = "running" }
  $d = "stopped"; if (Test-Port $dashPort) { $d = "running" }
  $lblStatus.Text = "API: $a    Dashboard: $d"
})
$timer.Start()

$form.Add_FormClosing({
  if (($script:apiProc -and -not $script:apiProc.HasExited) -or ($script:dashProc -and -not $script:dashProc.HasExited)) {
    $r=[System.Windows.Forms.MessageBox]::Show("Stop the API / dashboard before exiting?","Setup Wizard","YesNoCancel","Question")
    if ($r -eq "Cancel") { $_.Cancel=$true; return }
    if ($r -eq "Yes") { Stop-All }
  }
})

Render
[void]$form.ShowDialog()
