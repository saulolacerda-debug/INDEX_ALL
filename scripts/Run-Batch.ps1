param(
    [Parameter(Position = 0)]
    [string]$BatchName,
    [switch]$NoEmbeddings,
    [string]$Query,
    [switch]$Answer,
    [int]$Limit = 10,
    [ValidateSet("legal", "generic")]
    [string]$RankingProfile = "legal",
    [string]$OutputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToSafeName {
    param(
        [string]$Value
    )

    $sanitized = [regex]::Replace($Value.Trim(), "[^a-zA-Z0-9._-]+", "_")
    $sanitized = $sanitized.Trim("._")
    if ([string]::IsNullOrWhiteSpace($sanitized)) {
        return "item"
    }

    return $sanitized
}

function Resolve-WorkingPath {
    param(
        [string]$BasePath,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $BasePath
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }

    return Join-Path $BasePath $Value
}

function Get-LatestBatchDirectory {
    param(
        [string]$RootPath
    )

    return Get-ChildItem -Path $RootPath -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1
}

function Get-LatestCollectionDirectory {
    param(
        [string]$RootPath,
        [string]$BatchFolderName
    )

    $collectionPrefix = "{0}_collection*" -f (Convert-ToSafeName -Value $BatchFolderName)

    return Get-ChildItem -Path $RootPath -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like $collectionPrefix -and
            (Test-Path (Join-Path $_.FullName "catalog.json")) -and
            (Test-Path (Join-Path $_.FullName "collection_metadata.json"))
        } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

function Resolve-PythonExecutable {
    param(
        [string]$ProjectRoot
    )

    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv/bin/python")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return (Get-Command python -ErrorAction Stop).Source
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "data\raw"
$defaultProcessedRoot = Join-Path $projectRoot "data\processed"
$processedRoot = Resolve-WorkingPath -BasePath $projectRoot -Value $OutputDir
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $processedRoot = $defaultProcessedRoot
}

if (-not (Test-Path $rawRoot)) {
    throw "Pasta de entrada nao encontrada: $rawRoot"
}

if (-not (Test-Path $processedRoot)) {
    New-Item -ItemType Directory -Path $processedRoot -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($BatchName)) {
    $latestBatch = Get-LatestBatchDirectory -RootPath $rawRoot
    if ($null -eq $latestBatch) {
        throw "Nenhum lote encontrado em $rawRoot"
    }

    $batchDir = $latestBatch.FullName
    $resolvedBatchName = $latestBatch.Name
}
else {
    $candidatePath = Resolve-WorkingPath -BasePath $rawRoot -Value $BatchName
    if (-not (Test-Path $candidatePath)) {
        throw "Lote nao encontrado: $candidatePath"
    }

    $batchItem = Get-Item -LiteralPath $candidatePath
    if (-not $batchItem.PSIsContainer) {
        throw "O caminho informado nao e uma pasta de lote: $candidatePath"
    }

    $batchDir = $batchItem.FullName
    $resolvedBatchName = $batchItem.Name
}

$pythonExe = Resolve-PythonExecutable -ProjectRoot $projectRoot

$cliArgs = @("-m", "index_all.main", $batchDir, "--output-dir", $processedRoot)
if (-not $NoEmbeddings) {
    $cliArgs += "--build-embeddings"
}
if (-not [string]::IsNullOrWhiteSpace($Query)) {
    $cliArgs += @("--query", $Query, "--limit", $Limit, "--ranking-profile", $RankingProfile)
    if ($Answer) {
        $cliArgs += "--answer"
    }
}

Write-Host "Processando lote:" -ForegroundColor Green
Write-Host "  $batchDir"
Write-Host ""
Write-Host "Comando:" -ForegroundColor Cyan
Write-Host "  $pythonExe $($cliArgs -join ' ')"
Write-Host ""

& $pythonExe @cliArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$collectionDir = Get-LatestCollectionDirectory -RootPath $processedRoot -BatchFolderName $resolvedBatchName
if ($null -ne $collectionDir) {
    Write-Host ""
    Write-Host "Colecao mais recente:" -ForegroundColor Green
    Write-Host "  $($collectionDir.FullName)"
    Write-Host "Relatorio HTML:" -ForegroundColor Cyan
    Write-Host "  $(Join-Path $collectionDir.FullName 'collection_report.html')"
    Write-Host "Consulta posterior sem reprocessar:" -ForegroundColor Cyan
    Write-Host "  .\scripts\Query-Collection.ps1 -CollectionName $($collectionDir.Name) -Query ""termo procurado"""
    $collectionDir.FullName
}
