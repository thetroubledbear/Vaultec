<#
  Vaultec one-shot launcher.
  Starts the Docker core stack (db, api, worker, caddy) and the SvelteKit
  frontend dev server, waits for the API to be healthy, then opens the browser.

  Usage:
    Right-click run.ps1 -> Run with PowerShell
    or:  powershell -ExecutionPolicy Bypass -File run.ps1
    Flags:
      -WithAi       also start the ollama service (heavy; needs the models)
      -WithScanner  also start the scanner-ftp service (Brother MFC-L2700W drop)
      -NoFrontend   skip the npm dev server (use Caddy static build only)
#>
param(
  [switch]$WithAi,
  [switch]$WithScanner,
  [switch]$NoFrontend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Info($m) { Write-Host "[vaultec] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[vaultec] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[vaultec] $m" -ForegroundColor Yellow }

# --- 1. Docker must be running -------------------------------------------
Info "Checking Docker..."
try { docker info *> $null } catch {
  Warn "Docker not running. Start Docker Desktop, then re-run."
  exit 1
}

# --- 2. .env must exist ---------------------------------------------------
if (-not (Test-Path "$root\.env")) {
  Info ".env missing; copying from .env.example"
  Copy-Item "$root\.env.example" "$root\.env"
}

# --- 3. Build + start the core stack -------------------------------------
$services = @('db','api','worker','caddy')
if ($WithAi)      { $services += 'ollama' }
Info "Starting core stack: $($services -join ', ')"
docker compose up -d --build @services
if ($WithScanner) {
  Info "Starting scanner-ftp (scanner profile)"
  docker compose --profile scanner up -d scanner-ftp
}

# --- 4. Wait for the API to answer /health -------------------------------
Info "Waiting for API health on :8000..."
$healthy = $false
foreach ($i in 1..30) {
  try {
    $r = Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $healthy = $true; Ok "API healthy: $($r.Content)"; break }
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $healthy) { Warn "API did not become healthy in time; check: docker compose logs api" }

# --- 5. Frontend dev server ----------------------------------------------
if (-not $NoFrontend) {
  if (-not (Test-Path "$root\frontend\node_modules")) {
    Info "Installing frontend deps (first run)..."
    Push-Location "$root\frontend"; npm install; Pop-Location
  }
  # Skip if something is already serving 5173
  $up = $false
  try { Invoke-WebRequest -Uri http://localhost:5173 -UseBasicParsing -TimeoutSec 2 *> $null; $up = $true } catch {}
  if ($up) {
    Info "Frontend already running on :5173"
  } else {
    Info "Starting frontend dev server on :5173"
    Start-Process powershell -ArgumentList @(
      '-NoExit','-Command',
      "Set-Location '$root\frontend'; npm run dev"
    )
  }
}

# --- 6. Report + open browser --------------------------------------------
Write-Host ""
docker compose ps
Write-Host ""
Ok "Vaultec is up."
Write-Host "  Frontend (dev)   : http://localhost:5173"
Write-Host "  Frontend (caddy) : https://localhost"
Write-Host "  API              : http://localhost:8000  (health / docs at /docs)"
Write-Host ""

# Vault state hint
try {
  $h = (Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing).Content | ConvertFrom-Json
  if (-not $h.initialized) {
    Warn "Vault not initialized. Run first-time /setup (see backend/README.md)."
  } elseif (-not $h.unlocked) {
    Warn "Vault is LOCKED. Unlock via the frontend, or:"
    Write-Host '    curl.exe -X POST http://localhost:8000/unlock -H "Content-Type: application/json" -d "{\"passphrase\":\"YOUR_PASSPHRASE\"}"'
  } else {
    Ok "Vault is unlocked and ready."
  }
} catch {}

if (-not $NoFrontend) { Start-Process "http://localhost:5173" }
