Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "data\raw"
$processedRoot = Join-Path $projectRoot "data\processed"
$runScript = Join-Path $PSScriptRoot "Run-Batch.ps1"

# Lotes que tinham arquivos .doc/.xls ignorados
$batchFolders = Get-ChildItem -Path $rawRoot -Directory |
    Where-Object { $_.Name -match "^2026-03-19_09\d+_(notas_tecnicas|tabelas)" } |
    Sort-Object Name

if (-not $batchFolders) {
    throw "Nenhum lote encontrado para reprocessar."
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Reprocessando lotes com arquivos convertidos" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$total = $batchFolders.Count
$current = 0
$failed = @()

foreach ($batch in $batchFolders) {
    $current++
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " [$current/$total] $($batch.Name)" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    try {
        & $runScript -BatchName $batch.Name
        if ($LASTEXITCODE -ne 0) {
            throw "Run-Batch.ps1 retornou codigo $LASTEXITCODE"
        }
        Write-Host " OK" -ForegroundColor Green
    }
    catch {
        Write-Host " ERRO: $_" -ForegroundColor Red
        $failed += $batch.Name
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Reprocessamento concluido!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total: $total | Sucesso: $($total - $failed.Count) | Falhas: $($failed.Count)" -ForegroundColor Yellow

if ($failed.Count -gt 0) {
    foreach ($f in $failed) { Write-Host "  - $f" -ForegroundColor Red }
    exit 1
}
