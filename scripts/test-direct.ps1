$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendPort = 8110
$frontendPort = 5184
$backend = $null
$frontend = $null

function Stop-PortProcess([int]$port) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Http([string]$url, [string]$name) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest $url -UseBasicParsing
            if ($response.StatusCode -eq 200) { return }
        }
        catch { [System.Threading.Thread]::Sleep(250) }
    }
    throw "$name did not become ready at $url"
}

try {
    Stop-PortProcess $backendPort
    Stop-PortProcess $frontendPort

    if (-not (Test-Path "$root\.venv")) {
        python -m venv "$root\.venv"
    }
    & "$root\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements-dev.txt"
    Push-Location "$root\backend"
    try {
        & "$root\.venv\Scripts\python.exe" -m pytest tests -q
    }
    finally { Pop-Location }

    Push-Location "$root\frontend"
    try {
        npm ci
        npx playwright install chromium
    }
    finally { Pop-Location }

    $previousOrigin = $env:FRONTEND_ORIGIN
    $env:FRONTEND_ORIGIN = "http://127.0.0.1:$frontendPort"
    $backend = Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList @(
        "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$backendPort"
    ) -WorkingDirectory "$root\backend" -PassThru
    $env:FRONTEND_ORIGIN = $previousOrigin
    Wait-Http "http://127.0.0.1:$backendPort/health" "Python Agent"

    $previousAgentUrl = $env:VITE_AGENT_URL
    $env:VITE_AGENT_URL = "http://127.0.0.1:$backendPort"
    $frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @(
        "run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort", "--strictPort"
    ) -WorkingDirectory "$root\frontend" -PassThru
    $env:VITE_AGENT_URL = $previousAgentUrl
    Wait-Http "http://127.0.0.1:$frontendPort/?scoutTheme=light" "Vue"

    $env:E2E_BASE_URL = "http://127.0.0.1:$frontendPort"
    Push-Location "$root\frontend"
    try { npm run test:e2e } finally { Pop-Location }
}
finally {
    Remove-Item Env:E2E_BASE_URL -ErrorAction SilentlyContinue
    Stop-PortProcess $frontendPort
    Stop-PortProcess $backendPort
    if ($frontend) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    if ($backend) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
}