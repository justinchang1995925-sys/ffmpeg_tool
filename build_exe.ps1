$ErrorActionPreference = "Stop"

$python = "D:/python3.13.12/python3.13t.exe"

& $python -m pip install -r requirements.txt

& $python -m PyInstaller `
  --clean `
  --noconfirm `
  --onefile `
  --name FFmpegTool `
  --exclude-module cryptography `
  --exclude-module numpy `
  --exclude-module pandas `
  --exclude-module scipy `
  --add-data "templates;templates" `
  --add-data "static;static" `
  app.py

Write-Host ""
Write-Host "Build complete: dist/FFmpegTool.exe"
