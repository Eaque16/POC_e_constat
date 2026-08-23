[CmdletBinding()]
param(
    [switch]$InstallAI,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location -LiteralPath $ProjectRoot

$PythonCommand = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $PythonCommand) {
    throw "Python 3.11 est introuvable. Installez Python 3.11 x64 puis relancez ce script."
}

$VersionOutput = if ($PythonCommand.Name -eq "py.exe") {
    & $PythonCommand.Source -3.11 --version 2>&1
} else {
    & $PythonCommand.Source --version 2>&1
}
if ($VersionOutput -notmatch "Python 3\.11\.") {
    throw "Python 3.11.x est requis. Version détectée : $VersionOutput"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Création de l'environnement .venv avec Python 3.11..."
    if ($PythonCommand.Name -eq "py.exe") {
        & $PythonCommand.Source -3.11 -m venv .venv
    } else {
        & $PythonCommand.Source -m venv .venv
    }
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.lock
& $VenvPython -m pip install -e . --no-deps

if (-not $InstallAI -and -not $NonInteractive) {
    $Answer = Read-Host "Installer la pile IA CPU (volumineuse) ? [o/N]"
    $InstallAI = $Answer -match "^(o|oui|y|yes)$"
}

if ($InstallAI) {
    Write-Host "Installation explicite des versions PyTorch CPU appariées..."
    & $VenvPython -m pip install `
        torch==2.4.1+cpu torchaudio==2.4.1+cpu `
        --index-url https://download.pytorch.org/whl/cpu
    & $VenvPython -m pip install `
        ctranslate2==4.4.0 faster-whisper==1.0.3 `
        huggingface-hub==0.24.6 pyannote.audio==3.3.2
    Write-Host "Aucun modèle n'a été téléchargé automatiquement."
}

@("data\uploads", "data\recordings", "generated", "models") | ForEach-Object {
    New-Item -ItemType Directory -Path (Join-Path $ProjectRoot $_) -Force | Out-Null
}

& $VenvPython -m pip check
& $VenvPython scripts\diagnose.py
Write-Host "Installation terminée. Utilisez toujours .\.venv\Scripts\python.exe."
