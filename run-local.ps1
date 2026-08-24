$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [int]$Attempts = 90
    )
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            $Response = Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -UseBasicParsing
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Le service $Uri n'a pas répondu après $Attempts secondes."
}

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Environnement .venv absent. Exécutez setup.ps1 d'abord."
}

# Mode POC sans WSL2, Docker ni droits administrateur.
$env:DATABASE_URL = "sqlite:///./econstat-local.db"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:ECONSTA_BASE_URL = "http://127.0.0.1:8001"
$env:ECONSTAT_API_URL = "http://127.0.0.1:8000/api"
$env:ECONSTAT_UI_PORT = "7860"
$env:GRADIO_ANALYTICS_ENABLED = "False"
$env:RECORDINGS_DIR = "data/recordings"
$env:APP_ENV = "local"
$env:ENABLE_LLM = "false"
$env:DISABLE_AUTH = "false"

& $VenvPython -m econstat.local_bootstrap

$mock = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "econstat.mock_server:app", "--host", "127.0.0.1", "--port", "8001" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$api = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "econstat.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$ui = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "econstat.ui.app" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru

try {
    Wait-HttpEndpoint -Uri "http://127.0.0.1:8001/openapi.json" -Attempts 30
    Wait-HttpEndpoint -Uri "http://127.0.0.1:8000/health" -Attempts 30
    Wait-HttpEndpoint -Uri "http://127.0.0.1:7860" -Attempts 90
}
catch {
    Stop-Process -Id $mock.Id, $api.Id, $ui.Id -ErrorAction SilentlyContinue
    throw
}
$health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2

Write-Host "E-Constat IA est lancé sans droits administrateur."
Write-Host "Interface : http://127.0.0.1:7860"
Write-Host "API       : http://127.0.0.1:8000/docs"
Write-Host "Mock      : http://127.0.0.1:8001/docs"
Write-Host "Santé     : $($health.status)"
Write-Host "Processus : mock=$($mock.Id), api=$($api.Id), ui=$($ui.Id)"
