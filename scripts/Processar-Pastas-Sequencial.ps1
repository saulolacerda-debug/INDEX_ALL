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

# Buscar subpastas numeradas em entrada_atual
$folders = Get-ChildItem -LiteralPath $inboxDir -Directory |
    Where-Object { $_.Name -notin $ignoredNames } |
    Sort-Object Name

if (-not $folders) {
    throw "Nenhuma subpasta encontrada em $inboxDir"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Processamento sequencial por pasta" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pastas encontradas ($($folders.Count)):" -ForegroundColor Yellow
foreach ($f in $folders) {
    Write-Host "  - $($f.Name)"
}
Write-Host ""

# Mover todas as subpastas para staging
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
foreach ($f in $folders) {
    Move-Item -LiteralPath $f.FullName -Destination $stagingDir -Force
}
Write-Host "Pastas movidas para staging temporario." -ForegroundColor DarkGray
Write-Host ""

$total = $folders.Count
$current = 0
$failed = @()

foreach ($folder in $folders) {
    $current++
    $folderName = $folder.Name
    # Extrair nome sem prefixo numerico (ex: "01_guia_pratico" -> "guia_pratico")
    $batchLabel = $folderName -replace "^\d+_", ""

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " [$current/$total] Processando: $folderName" -ForegroundColor Green
    Write-Host " Lote: $batchLabel" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host ""

    $stagedFolder = Join-Path $stagingDir $folderName

    # Copiar conteudo da pasta para entrada_atual
    $items = Get-ChildItem -LiteralPath $stagedFolder -Force |
        Where-Object { $_.Name -notin $ignoredNames }

    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $inboxDir -Recurse -Force
    }

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
        Write-Host " OK - $folderName concluido com sucesso." -ForegroundColor Green
    }
    catch {
        Write-Host ""
        Write-Host " ERRO - $folderName falhou: $_" -ForegroundColor Red
        $failed += $folderName
    }

    # Limpar entrada_atual para o proximo lote
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
Write-Host "Total: $total pastas" -ForegroundColor Yellow
Write-Host "Sucesso: $($total - $failed.Count)" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "Falhas: $($failed.Count)" -ForegroundColor Red
    foreach ($f in $failed) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    exit 1
}
