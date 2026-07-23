$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"

foreach ($port in 8100, 5174) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing process and run this script again."
    }
}

if (-not (Test-Path $venv)) { python -m venv $venv }
& "$venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements.txt"
Push-Location "$root\frontend"
try { npm ci } finally { Pop-Location }

Write-Host "Starting Python Agent on http://127.0.0.1:8100" -ForegroundColor Green
$backendArgs = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8100")
if (Test-Path "$root\backend\.env") {
    $backendArgs += @("--env-file", ".env")
}
$backend = Start-Process -FilePath "$venv\Scripts\python.exe" -ArgumentList $backendArgs -WorkingDirectory "$root\backend" -PassThru
foreach ($service in @(
    @{ Name = "Python Agent"; Url = "http://127.0.0.1:8100/health" }
)) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-RestMethod $service.Url
            if ($response.status -eq "ok") { $ready = $true; break }
        }
        catch { [System.Threading.Thread]::Sleep(250) }
    }
    if (-not $ready) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
        throw "$($service.Name) did not become ready."
    }
}

Write-Host "Starting Vue on http://127.0.0.1:5174/?scoutTheme=light" -ForegroundColor Green
Push-Location "$root\frontend"
try { npm run dev -- --host 127.0.0.1 --port 5174 --strictPort }
finally {
    Pop-Location
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}