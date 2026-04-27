# Jarvis — one-shot Windows setup script
# Run from an elevated PowerShell in the repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1

$ErrorActionPreference = "Stop"

function Need($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "Missing: $name" -ForegroundColor Red
        return $false
    }
    return $true
}

Write-Host "--- Jarvis Windows installer ---" -ForegroundColor Cyan

# 1. Python
if (-not (Need python)) {
    Write-Host "Install Python 3.11 from https://www.python.org/downloads/ then rerun." -ForegroundColor Yellow
    exit 1
}

$py = python --version 2>&1
Write-Host "Python: $py"

# 2. ffmpeg (required by pydub for MP3 playback from ElevenLabs)
if (-not (Need ffmpeg)) {
    Write-Host "ffmpeg not found. Installing via winget..." -ForegroundColor Yellow
    try {
        winget install --id Gyan.FFmpeg -e --silent --accept-source-agreements --accept-package-agreements
    } catch {
        Write-Host "winget install failed. Please install ffmpeg manually and add it to PATH." -ForegroundColor Red
    }
}

# 3. Virtual env
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..."
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip wheel
pip install -e ".[dev]"

# 4. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "`nCreated .env from template. Open it and fill in:" -ForegroundColor Green
    Write-Host "  OPENAI_API_KEY=..."
    Write-Host "  ELEVENLABS_API_KEY=..."
}

Write-Host "`nDone. Activate the venv and run:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python -m jarvis text     # test without mic"
Write-Host "  python -m jarvis          # full voice loop (say 'hey jarvis')"
