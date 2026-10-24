$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskTemp = Join-Path $PSScriptRoot '.build-temp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies.' }
Write-Host 'Ready. Launch Run OpenLUFS.cmd.'
