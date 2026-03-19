param(
    [switch]$NoEmbeddings,
    [string]$Query,
    [int]$Limit = 10,
    [string]$OutputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "data\raw"
$inboxDir = Join-Path $rawRoot "entrada_atual"
$stagingDir = Join-Path $rawRoot "_staging"
$processarScript = Join-Path $PSScriptRoot "Processar-Lote-Atual.ps1"

$ignoredNames = @(".gitkeep", ".DS_Store", "Thumbs.db")

# Buscar ARQUIVOS em entrada_atual (nao pastas), ordenados por nome
$files = Get-ChildItem -LiteralPath $inboxDir -File |
    Where-Object { $_.Name -notin $ignoredNames } |
    Sort-Object Name

if (-not $files) {
    throw "Nenhum arquivo encontrado em $inboxDir"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Processamento sequencial por arquivo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Arquivos encontrados ($($files.Count)):" -ForegroundColor Yellow
foreach ($f in $files) {
    Write-Host "  - $($f.Name)"
}
Write-Host ""

# Mover todos os arquivos para staging
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
foreach ($f in $files) {
    Move-Item -LiteralPath $f.FullName -Destination $stagingDir -Force
}
Write-Host "Arquivos movidos para staging temporario." -ForegroundColor DarkGray
Write-Host ""

$total = $files.Count
$current = 0
$failed = @()

foreach ($file in $files) {
    $current++
    $fileName = $file.Name
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($fileName)
    # Extrair nome sem prefixo numerico (ex: "01_guia_pratico.docx" -> "guia_pratico")
    $batchLabel = $baseName -replace "^\d+_", ""

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " [$current/$total] Processando: $fileName" -ForegroundColor Green
    Write-Host " Lote: $batchLabel" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host ""

    $stagedFile = Join-Path $stagingDir $fileName

    # Copiar o arquivo para entrada_atual
    Copy-Item -LiteralPath $stagedFile -Destination $inboxDir -Force

    # Montar parametros para Processar-Lote-Atual.ps1
    $params = @{ Name = $batchLabel }
    if ($NoEmbeddings) { $params.NoEmbeddings = $true }
    if (-not [string]::IsNullOrWhiteSpace($Query)) {
        $params.Query = $Query
        $params.Limit = $Limit
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputDir)) {
        $params.OutputDir = $OutputDir
    }

    try {
        & $processarScript @params
        if ($LASTEXITCODE -ne 0) {
            throw "Processar-Lote-Atual.ps1 retornou codigo $LASTEXITCODE"
        }
        Write-Host ""
        Write-Host " OK - $fileName concluido com sucesso." -ForegroundColor Green
    }
    catch {
        Write-Host ""
        Write-Host " ERRO - $fileName falhou: $_" -ForegroundColor Red
        $failed += $fileName
    }

    # Limpar entrada_atual para o proximo arquivo
    Get-ChildItem -LiteralPath $inboxDir -Force |
        Where-Object { $_.Name -notin $ignoredNames } |
        Remove-Item -Recurse -Force

    Write-Host ""
}

# Limpar staging
Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Processamento concluido!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total: $total arquivos" -ForegroundColor Yellow
Write-Host "Sucesso: $($total - $failed.Count)" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "Falhas: $($failed.Count)" -ForegroundColor Red
    foreach ($f in $failed) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    exit 1
}
