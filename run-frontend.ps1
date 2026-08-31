$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "frontend")

$PortableNode = Join-Path $PSScriptRoot ".tools\node-v24.20.0-win-x64"
$PortableNpm = Join-Path $PortableNode "npm.cmd"
if (Test-Path -LiteralPath $PortableNpm) {
    $env:PATH = "$PortableNode;$env:PATH"
    $Npm = $PortableNpm
}
elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    $Npm = "npm"
}
else {
    throw "Node.js LTS est requis. Installez-le ou placez sa version portable dans .tools."
}

if (-not (Test-Path -LiteralPath "node_modules")) {
    & $Npm ci
}

& $Npm run dev -- --host 127.0.0.1 --port 5173
