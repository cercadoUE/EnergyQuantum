$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = Join-Path (Split-Path $projectDir) '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Cree el entorno virtual siguiendo README.md.' }
Set-Location -LiteralPath $projectDir
& $pythonExe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8510
