param(
    [Parameter(Position = 0)]
    [string]$CollectionName,
    [Parameter(Mandatory = $true)]
    [string]$Query,
    [int]$Limit = 10,
    [string]$Archetype,
    [string]$FileName,
    [string]$FileType,
    [string]$OutputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Get-LatestCollectionDirectory {
    param(
        [string]$RootPath
    )

    return Get-ChildItem -Path $RootPath -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            (Test-Path (Join-Path $_.FullName "catalog.json")) -and
            (Test-Path (Join-Path $_.FullName "collection_metadata.json"))
        } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$defaultProcessedRoot = Join-Path $projectRoot "data\processed"
$processedRoot = Resolve-WorkingPath -BasePath $projectRoot -Value $OutputDir
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $processedRoot = $defaultProcessedRoot
}

if (-not (Test-Path $processedRoot)) {
    throw "Pasta de colecoes nao encontrada: $processedRoot"
}

if ([string]::IsNullOrWhiteSpace($CollectionName)) {
    $collectionItem = Get-LatestCollectionDirectory -RootPath $processedRoot
    if ($null -eq $collectionItem) {
        throw "Nenhuma colecao encontrada em $processedRoot"
    }
}
else {
    $candidatePath = Resolve-WorkingPath -BasePath $processedRoot -Value $CollectionName
    if (-not (Test-Path $candidatePath)) {
        throw "Colecao nao encontrada: $candidatePath"
    }

    $collectionItem = Get-Item -LiteralPath $candidatePath
    if (-not $collectionItem.PSIsContainer) {
        throw "O caminho informado nao e uma pasta de colecao: $candidatePath"
    }
}

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

$cliArgs = @("-m", "index_all.main", $collectionItem.FullName, "--query", $Query, "--limit", $Limit)
if (-not [string]::IsNullOrWhiteSpace($Archetype)) {
    $cliArgs += @("--archetype", $Archetype)
}
if (-not [string]::IsNullOrWhiteSpace($FileName)) {
    $cliArgs += @("--file-name", $FileName)
}
if (-not [string]::IsNullOrWhiteSpace($FileType)) {
    $cliArgs += @("--file-type", $FileType)
}

Write-Host "Consultando colecao:" -ForegroundColor Green
Write-Host "  $($collectionItem.FullName)"
Write-Host ""
Write-Host "Comando:" -ForegroundColor Cyan
Write-Host "  $pythonExe $($cliArgs -join ' ')"
Write-Host ""

& $pythonExe @cliArgs
exit $LASTEXITCODE
