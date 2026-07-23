param(
    [string]$Ticker = "AAPL",
    [string]$FromDate = "2024-01-01",
    [string]$ToDate = "2024-12-31"
)

$ErrorActionPreference = "Stop"
$Root = (Get-Item $PSScriptRoot).FullName
$LogDir = "$Root\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Services = @(
    @{Name="stock-price"; Script="run_stock_price.py"; Port=8081; Health="/health"},
    @{Name="features"; Script="run_features.py"; Port=8082; Health="/health"},
    @{Name="correlation"; Script="run_correlation.py"; Port=8083; Health="/symbols"},
    @{Name="simulator"; Script="run_simulator.py"; Port=8085; Health="/health"}
)

$Jobs = @{}
try {
    # --- Start all services in background ---
    foreach ($svc in $Services) {
        $logFile = "$LogDir\$($svc.Name).log"
        Write-Host "Starting $($svc.Name) on port $($svc.Port)..."
        if ($svc.Script -eq "run_correlation.py") {
            # run_correlation.py doesn't call uvicorn.run; use CLI instead
            $job = Start-Job -ScriptBlock {
                param($r, $p)
                cd $r
            python -m uvicorn vinu_initial_analysis.server.app:create_app --host 127.0.0.1 --port $p --log-level warning 2>&1
            } -ArgumentList $Root, $svc.Port
        } else {
            $job = Start-Job -ScriptBlock {
                param($r, $s, $p)
                cd $r
                python $s 2>&1
            } -ArgumentList $Root, $svc.Script, $svc.Port
        }
        $Jobs[$svc.Name] = $job
    }

    # --- Wait for all services to be ready ---
    foreach ($svc in $Services) {
        $url = "http://127.0.0.1:$($svc.Port)$($svc.Health)"
        Write-Host "Waiting for $($svc.Name) at $url ..."
        $ready = $false
        $deadline = (Get-Date).AddSeconds(30)
        while (-not $ready -and (Get-Date) -lt $deadline) {
            try {
                $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
                if ($r.StatusCode -lt 500) { $ready = $true }
            } catch { Start-Sleep -Milliseconds 1000 }
        }
        if (-not $ready) { throw "$($svc.Name) not ready after 30s" }
        Write-Host "  $($svc.Name) is ready." -ForegroundColor Green
    }

    Write-Host "`n=== All services ready. Starting research for $Ticker ===" -ForegroundColor Cyan

    # --- Run research via CLI ---
    cd $Root\vinu-research
    python -m vinu_research run `
        --idea "SMA crossover on $Ticker" `
        --symbol $Ticker `
        --from $FromDate `
        --to $ToDate `
        --max-iterations 3 `
        --verbose 2>&1

} finally {
    # --- Cleanup: stop all background jobs ---
    Write-Host "`nStopping services..."
    foreach ($name in $Jobs.Keys) {
        $job = $Jobs[$name]
        if ($job.State -eq "Running") { Stop-Job $job }
        Remove-Job $job -ErrorAction SilentlyContinue
    }
    Write-Host "Done."
}
