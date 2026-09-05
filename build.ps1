$ErrorActionPreference = "Stop"
python -m pip install pyinstaller
pyinstaller --onefile --name fdm --clean --paths src fdm_entry.py
Copy-Item dist\fdm.exe dist\fdm-windows-x64.exe -Force
Write-Host "Built dist\fdm-windows-x64.exe"
