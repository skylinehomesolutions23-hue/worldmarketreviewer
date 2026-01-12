param(
    [int]$MaxParallel = 4,
    [int]$MaxAttempts = 1,
    [switch]$Force,
    [switch]$All = $true,
    [string]$Tickers = ""
)

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $baseDir

$logFile = Join-Path $baseDir ("phase2_rerun_pro_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
"Starting Phase2 rerun. Log=$logFile" | Tee-Object -FilePath $logFile -Append | Out-Null

$cmd = @("python", ".\phase2_parallel_runner.py", "--max-parallel", "$MaxParallel")
if ($Force) { $cmd += "--force" }

if ($Tickers -and $Tickers.Trim().Length -gt 0) {
    $cmd += @("--tickers", $Tickers)
} else {
    $cmd += "--all"
}

("Command: " + ($cmd -join " ")) | Tee-Object -FilePath $logFile -Append | Out-Null
& $cmd 2>&1 | Tee-Object -FilePath $logFile -Append
Pause
