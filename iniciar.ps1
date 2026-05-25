Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Operum - Inicializacao rapida" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any existing process on port 8001 (or port 8000 legacy)
$oldPid = netstat -ano | Select-String ":8001 " | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -ne '0' } | Select-Object -First 1
if (-not $oldPid) {
    $oldPid = netstat -ano | Select-String ":8000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -ne '0' } | Select-Object -First 1
}
if ($oldPid) {
    taskkill /F /PID $oldPid 2>$null
    Write-Host "Porta liberada" -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

# Start backend in new window
Write-Host "[1/2] Iniciando backend (FastAPI)..." -ForegroundColor Green
cmd /c "start ""Operum Backend"" cmd /k python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level error"

# Retry health check until backend is ready (lifespan pode levar ~15s)
$maxRetries = 15
$retryDelay = 2
$backendOk = $false
for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds $retryDelay
    try {
        $test = Invoke-WebRequest -Uri "http://localhost:8001/api/health" -UseBasicParsing -TimeoutSec 3
        if ($test.StatusCode -eq 200) {
            Write-Host "  Backend OK (porta 8001, tentativa $i)" -ForegroundColor Green
            $backendOk = $true
            break
        }
    } catch {
        if ($i -lt $maxRetries) {
            Write-Host "  Aguardando backend ($i/$maxRetries)..." -ForegroundColor DarkYellow
        }
    }
}
if (-not $backendOk) {
    Write-Host "  ERRO: Backend nao iniciou apos $($maxRetries * $retryDelay)s" -ForegroundColor Red
    exit 1
}

# Start frontend
Write-Host "[2/2] Iniciando frontend (Vite)..." -ForegroundColor Green
cmd /c "start ""Operum Frontend"" cmd /k npm run dev"

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8001" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para parar, feche as janelas ou use:" -ForegroundColor Gray
Write-Host "  taskkill /F /PID (PID do python)" -ForegroundColor Gray
