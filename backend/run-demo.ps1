$ErrorActionPreference = "Stop"

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
}

python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
