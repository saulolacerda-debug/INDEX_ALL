param(
    [Parameter(Mandatory)]
    [string]$TargetCollection,
    [Parameter(Mandatory)]
    [string]$SourceCollection
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$processedRoot = Join-Path $projectRoot "data\processed"

$targetDir = Join-Path $processedRoot $TargetCollection
$sourceDir = Join-Path $processedRoot $SourceCollection

if (-not (Test-Path $targetDir)) { throw "Colecao destino nao encontrada: $targetDir" }
if (-not (Test-Path $sourceDir)) { throw "Colecao origem nao encontrada: $sourceDir" }

$jsonFiles = @(
    "catalog.json",
    "chunks.json",
    "master_index.json",
    "search_index.json",
    "embeddings_index.json",
    "retrieval_preview.json"
)

Write-Host "Mesclando colecao:" -ForegroundColor Cyan
Write-Host "  Origem:  $sourceDir" -ForegroundColor Gray
Write-Host "  Destino: $targetDir" -ForegroundColor Gray
Write-Host ""

foreach ($jsonFile in $jsonFiles) {
    $targetFile = Join-Path $targetDir $jsonFile
    $sourceFile = Join-Path $sourceDir $jsonFile

    if (-not (Test-Path $sourceFile)) {
        Write-Host "  Pulando $jsonFile (nao existe na origem)" -ForegroundColor Yellow
        continue
    }
    if (-not (Test-Path $targetFile)) {
        Write-Host "  Copiando $jsonFile (nao existe no destino)" -ForegroundColor Yellow
        Copy-Item -LiteralPath $sourceFile -Destination $targetFile
        continue
    }

    $targetData = Get-Content -LiteralPath $targetFile -Raw | ConvertFrom-Json
    $sourceData = Get-Content -LiteralPath $sourceFile -Raw | ConvertFrom-Json

    if ($targetData -is [System.Array] -and $sourceData -is [System.Array]) {
        $merged = @($targetData) + @($sourceData)
        $merged | ConvertTo-Json -Depth 20 -Compress | Set-Content -LiteralPath $targetFile -Encoding UTF8
        Write-Host "  $jsonFile : $($targetData.Count) + $($sourceData.Count) = $($merged.Count) entradas" -ForegroundColor Green
    }
    else {
        Write-Host "  Pulando $jsonFile (formato nao e array)" -ForegroundColor Yellow
    }
}

# Atualizar metadata
$metaFile = Join-Path $targetDir "collection_metadata.json"
if (Test-Path $metaFile) {
    $meta = Get-Content -LiteralPath $metaFile -Raw | ConvertFrom-Json
    $sourceMeta = Get-Content -LiteralPath (Join-Path $sourceDir "collection_metadata.json") -Raw | ConvertFrom-Json
    if ($meta.PSObject.Properties["document_count"] -and $sourceMeta.PSObject.Properties["document_count"]) {
        $meta.document_count = $meta.document_count + $sourceMeta.document_count
        $meta | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $metaFile -Encoding UTF8
        Write-Host "  collection_metadata.json : document_count atualizado para $($meta.document_count)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Mesclagem concluida!" -ForegroundColor Green
