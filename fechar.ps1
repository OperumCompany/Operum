$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Operum - Encerramento rapido" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Stop-PortProcess {
    param(
        [int]$Port,
        [string]$Name
    )

    $processIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $processIds) {
        Write-Host "  $Name nao esta em execucao na porta $Port." -ForegroundColor DarkGray
        return
    }

    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne $PID) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "  $Name encerrado (porta $Port, PID $processId)." -ForegroundColor Yellow
        }
    }
}

Stop-PortProcess -Port 5173 -Name "Frontend"
Stop-PortProcess -Port 8001 -Name "Backend"
Stop-PortProcess -Port 8000 -Name "Backend alternativo"

Write-Host ""
Write-Host "Operum encerrado." -ForegroundColor Green
