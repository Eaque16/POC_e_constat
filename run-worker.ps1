$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$WorkerModule = Join-Path $ProjectRoot "econstat\worker.py"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Environnement .venv absent. Exécutez .\setup.ps1."
}
if (-not (Test-Path -LiteralPath $WorkerModule)) {
    throw "Worker non encore livré : la file SQL sera implémentée en phase 5."
}

Set-Location -LiteralPath $ProjectRoot
& $VenvPython -m econstat.worker
