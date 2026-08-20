# Smoke-tests every ShieldAI / PPAG feature against a RUNNING server.
# Start the API first (see header of the printout), then:
#   powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
# Optional: -Port 8888  -Token dev-internal

param(
  [int]$Port = 8888,
  [string]$Token = "dev-internal"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$base = "http://127.0.0.1:$Port"
$pass = 0; $fail = 0

function Check($name, [scriptblock]$test) {
  try {
    $ok = & $test
    if ($ok) { Write-Host ("  PASS  " + $name) -ForegroundColor Green; $script:pass++ }
    else     { Write-Host ("  FAIL  " + $name) -ForegroundColor Red;   $script:fail++ }
  } catch {
    Write-Host ("  FAIL  " + $name + "  -> " + $_.Exception.Message) -ForegroundColor Red
    $script:fail++
  }
}

function Internal($path) {
  Invoke-RestMethod -Uri "$base$path" -Headers @{ "X-Shield-Internal-Token" = $Token }
}

Write-Host "Testing ShieldAI at $base" -ForegroundColor Cyan
Write-Host ""

Check "health endpoint" { (Invoke-RestMethod "$base/health").status -eq "ok" }

Check "internal auth rejects no-token (401)" {
  try { Invoke-RestMethod "$base/internal/metrics" | Out-Null; $false }
  catch { $_.Exception.Response.StatusCode.value__ -eq 401 }
}

Check "compliance report returns coverage" {
  (Internal "/internal/compliance/report").summary.controls_total -gt 0
}

Check "audit hash-chain verifies intact" { (Internal "/internal/audit/verify").ok -eq $true }

Check "security correlations endpoint" {
  $null -ne (Internal "/internal/correlations").window_seconds
}

Check "SIEM CEF export" {
  $cef = Invoke-RestMethod -Uri "$base/internal/siem/export?fmt=cef&limit=1" -Headers @{ "X-Shield-Internal-Token" = $Token }
  ($cef -is [string]) -and ($cef.StartsWith("CEF:0|ShieldAI") -or $cef -eq "")
}

# --- Auth + MFA flow ---
$script:jwt = $null
Check "login (admin) returns a JWT" {
  $r = Invoke-RestMethod -Method Post "$base/v1/auth/token" -ContentType "application/json" `
        -Body '{"username":"admin","password":"admin123"}'
  $script:jwt = $r.access_token
  ($r.role -eq "admin") -and $r.access_token
}

Check "bad login rejected (401)" {
  try { Invoke-RestMethod -Method Post "$base/v1/auth/token" -ContentType "application/json" `
          -Body '{"username":"admin","password":"wrong"}' | Out-Null; $false }
  catch { $_.Exception.Response.StatusCode.value__ -eq 401 }
}

Check "token introspection (/me)" {
  (Invoke-RestMethod "$base/v1/auth/me" -Headers @{ Authorization = "Bearer $script:jwt" }).role -eq "admin"
}

Check "MFA enroll + verify" {
  $e = Invoke-RestMethod -Method Post "$base/v1/auth/mfa/enroll" -Headers @{ Authorization = "Bearer $script:jwt" }
  $secret = $e.secret
  $code = (& $venvPy -c "from app.proxy.identity import totp_now; print(totp_now('$secret'))").Trim()
  $v = Invoke-RestMethod -Method Post "$base/v1/auth/mfa/verify" -Headers @{ Authorization = "Bearer $script:jwt" } `
        -ContentType "application/json" -Body ("{""totp_code"":""" + $code + """}")
  $v.mfa_enrolled -eq $true
}

Write-Host ""
$color = "Green"; if ($fail -gt 0) { $color = "Red" }
Write-Host ("Result: {0} passed, {1} failed" -f $pass, $fail) -ForegroundColor $color
if ($fail -gt 0) { exit 1 }
