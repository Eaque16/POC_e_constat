$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Environnement .venv absent. Exécutez setup.ps1 d'abord."
}

# Mode POC sans WSL2, Docker ni droits administrateur.
$env:DATABASE_URL = "sqlite:///./econstat-local.db"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:ECONSTA_BASE_URL = "http://127.0.0.1:8081"
$env:ECONSTAT_API_URL = "http://127.0.0.1:8080/api"
$env:ECONSTAT_UI_PORT = "7861"
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:RECORDINGS_DIR = "data/recordings"
$env:APP_ENV = "local-no-admin"
$env:ENABLE_LLM = "false"
$env:DISABLE_AUTH = "true"

& $python -m econstat.local_bootstrap

$mock = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "econstat.mock_server:app", "--host", "127.0.0.1", "--port", "8081" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$api = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "econstat.main:app", "--host", "127.0.0.1", "--port", "8080" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$ui = Start-Process -FilePath $python `
    -ArgumentList "-m", "econstat.ui.app" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru

$health = $null
for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $health) {
    throw "L'API n'a pas répondu après 30 secondes."
}

Write-Host "E-Constat IA est lancé sans droits administrateur."
Write-Host "Interface : http://127.0.0.1:7861"
Write-Host "API       : http://127.0.0.1:8080/docs"
Write-Host "Mock      : http://127.0.0.1:8081/docs"
Write-Host "Santé     : $($health.status)"
Write-Host "Processus : mock=$($mock.Id), api=$($api.Id), ui=$($ui.Id)"
