Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Operum - Inicializacao rapida" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any existing process on port 8000
$oldPid = netstat -ano | Select-String ":8000 " | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -ne '0' } | Select-Object -First 1
if ($oldPid) {
    taskkill /F /PID $oldPid 2>$null
    Write-Host "Porta 8000 liberada" -ForegroundColor Yellow
}

# Start backend in new window
Write-Host "[1/2] Iniciando backend (FastAPI)..." -ForegroundColor Green
cmd /c "start ""Operum Backend"" cmd /k python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level error"
Start-Sleep -Seconds 5

# Test backend
try {
    $test = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "  Backend OK (porta 8000)" -ForegroundColor Green
} catch {
    Write-Host "  ERRO: Backend nao iniciou" -ForegroundColor Red
    exit 1
}

# Start frontend
Write-Host "[2/2] Iniciando frontend (Vite)..." -ForegroundColor Green
cmd /c "start ""Operum Frontend"" cmd /k npm run dev"

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para parar, feche as janelas ou use:" -ForegroundColor Gray
Write-Host "  taskkill /F /PID (PID do python)" -ForegroundColor Gray
