$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Operum - Inicializacao rapida" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPython = Join-Path $projectDir ".venv\Scripts\python.exe"
$backendLog = Join-Path $projectDir "backend-start.log"
$backendErrorLog = Join-Path $projectDir "backend-start.err.log"
$frontendLog = Join-Path $projectDir "frontend-start.log"
$frontendErrorLog = Join-Path $projectDir "frontend-start.err.log"
$ollamaLog = Join-Path $projectDir "ollama-start.log"
$ollamaErrorLog = Join-Path $projectDir "ollama-start.err.log"

function Stop-PortProcess {
    param([int]$Port)

    $processIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "  Porta $Port liberada (PID $processId)" -ForegroundColor Yellow
        }
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$MaxRetries = 30,
        [int]$RetryDelaySeconds = 2,
        [System.Diagnostics.Process]$Process = $null
    )

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        if ($Process -and $Process.HasExited) {
            return $false
        }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {
            if ($attempt -lt $MaxRetries) {
                Write-Host "  Aguardando servico ($attempt/$MaxRetries)..." -ForegroundColor DarkYellow
            }
        }
        Start-Sleep -Seconds $RetryDelaySeconds
    }

    return $false
}

function Repair-ProjectVenv {
    if (-not (Test-Path $projectPython)) {
        $venvDir = Join-Path $projectDir ".venv"
        $venvArgs = if (Test-Path $venvDir) { @("-3", "-m", "venv", "--clear", $venvDir) } else { @("-3", "-m", "venv", $venvDir) }
        Write-Host "  Ambiente Python ausente ou incompleto; criando .venv..." -ForegroundColor Yellow
        $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            & $pyLauncher.Source @venvArgs
        } else {
            $pythonBootstrap = Get-Command "python.exe" -ErrorAction SilentlyContinue
            if (-not $pythonBootstrap) {
                throw "Python 3 nao foi encontrado. Instale-o e execute o script novamente."
            }
            $venvArgs = $venvArgs | Where-Object { $_ -ne "-3" }
            & $pythonBootstrap.Source @venvArgs
        }
    }

    $checkCommand = "import click, fastapi, pandas, requests, uvicorn; assert hasattr(click, 'Choice')"
    & $projectPython -c $checkCommand 2>$null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Write-Host "  Dependencias Python invalidas; reparando .venv automaticamente..." -ForegroundColor Yellow
    & $projectPython -m ensurepip --upgrade
    & $projectPython -m pip install --upgrade pip
    & $projectPython -m pip install --force-reinstall --no-cache-dir -r (Join-Path $projectDir "requirements.txt")
    & $projectPython -c $checkCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel reparar as dependencias Python. Consulte a saida acima."
    }
}

Set-Location $projectDir
Repair-ProjectVenv
Stop-PortProcess -Port 8001
Stop-PortProcess -Port 8000
Stop-PortProcess -Port 5173
Start-Sleep -Seconds 1

if (-not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    $ollamaCommand = Get-Command "ollama.exe" -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        Write-Host "[0/2] Iniciando Ollama local..." -ForegroundColor Green
        Remove-Item $ollamaLog, $ollamaErrorLog -ErrorAction SilentlyContinue
        Start-Process `
            -FilePath $ollamaCommand.Source `
            -ArgumentList "serve" `
            -WorkingDirectory $projectDir `
            -RedirectStandardOutput $ollamaLog `
            -RedirectStandardError $ollamaErrorLog `
            -WindowStyle Hidden | Out-Null
        if (Wait-HttpReady -Url "http://127.0.0.1:11434/api/tags" -MaxRetries 10 -RetryDelaySeconds 1) {
            Write-Host "  Ollama OK (porta 11434)" -ForegroundColor Green
        } else {
            Write-Host "  AVISO: Ollama indisponivel; o agente usara a base editorial." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[0/2] Ollama nao encontrado; o agente usara a base editorial." -ForegroundColor Yellow
    }
}

Write-Host "[1/2] Iniciando backend (FastAPI)..." -ForegroundColor Green
Remove-Item $backendLog, $backendErrorLog -ErrorAction SilentlyContinue
$env:PYTHONUNBUFFERED = "1"
$backendProcess = Start-Process `
    -FilePath $projectPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "info", "--reload", "--reload-dir", (Join-Path $projectDir "app") `
    -WorkingDirectory $projectDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrorLog `
    -WindowStyle Hidden `
    -PassThru

if (-not (Wait-HttpReady -Url "http://127.0.0.1:8001/api/health" -Process $backendProcess)) {
    Write-Host "  ERRO: Backend nao iniciou. Consulte os logs abaixo." -ForegroundColor Red
    if (Test-Path $backendLog) { Get-Content $backendLog -Tail 30 }
    if (Test-Path $backendErrorLog) { Get-Content $backendErrorLog -Tail 30 }
    exit 1
}
Write-Host "  Backend OK (porta 8001, PID $($backendProcess.Id))" -ForegroundColor Green

Write-Host "[2/2] Iniciando frontend (Vite)..." -ForegroundColor Green
Remove-Item $frontendLog, $frontendErrorLog -ErrorAction SilentlyContinue
$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--strictPort" `
    -WorkingDirectory $projectDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErrorLog `
    -WindowStyle Hidden `
    -PassThru

if (-not (Wait-HttpReady -Url "http://127.0.0.1:5173/" -MaxRetries 90 -RetryDelaySeconds 1 -Process $frontendProcess)) {
    Write-Host "  ERRO: Frontend nao iniciou ou nao alcancou o backend." -ForegroundColor Red
    if (Test-Path $frontendLog) { Get-Content $frontendLog -Tail 30 }
    if (Test-Path $frontendErrorLog) { Get-Content $frontendErrorLog -Tail 30 }
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "  Frontend OK (porta 5173, PID $($frontendProcess.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8001" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs:" -ForegroundColor Gray
Write-Host "  $backendLog" -ForegroundColor Gray
Write-Host "  $backendErrorLog" -ForegroundColor Gray
Write-Host "  $frontendLog" -ForegroundColor Gray
Write-Host "  $frontendErrorLog" -ForegroundColor Gray
Write-Host "  $ollamaLog" -ForegroundColor Gray
Write-Host "  $ollamaErrorLog" -ForegroundColor Gray
