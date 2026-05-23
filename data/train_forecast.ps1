$p = Start-Process -NoNewWindow -PassThru -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8030"
Start-Sleep -Seconds 10

$tickers = @("PETR4","VALE3","ITUB4","BBDC4","ABEV3","WEGE3","B3SA3","BBAS3")
$results = @()

foreach ($t in $tickers) {
    try {
        $url = "http://127.0.0.1:8030/api/models/train/forecast/$t"
        $r = Invoke-WebRequest -Uri $url -Method POST -UseBasicParsing
        $j = $r.Content | ConvertFrom-Json
        $line = "$t : $($j.status) r2_train=$($j.train_r2) r2_test=$($j.test_r2) samples=$($j.train_samples)"
        $results += $line
        Write-Host $line
    } catch {
        $line = "$t : ERROR - $($_.Exception.Message)"
        $results += $line
        Write-Host $line
    }
}

Write-Host "`n=== Training Summary ==="
$results | ForEach-Object { Write-Host $_ }

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
