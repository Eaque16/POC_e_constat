$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip==24.2
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if ($env:INSTALL_AI -eq "1") { & .\.venv\Scripts\python.exe -m pip install ".[ai]"; & .\.venv\Scripts\python.exe -m econstat.models_setup }
docker compose up -d postgres mock-econsta
& .\.venv\Scripts\alembic.exe upgrade head
& .\.venv\Scripts\python.exe -m econstat.seed
& .\.venv\Scripts\pytest.exe
Write-Host "Installation validée. Lancez: .\.venv\Scripts\uvicorn.exe econstat.main:app --reload"
