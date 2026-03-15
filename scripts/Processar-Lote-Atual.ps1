param(
    [Parameter(Position = 0)]
    [string]$Name = "lote",
    [switch]$NoEmbeddings,
    [string]$Query,
    [int]$Limit = 10,
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
        return "lote"
    }

    return $sanitized
}

$ignoredNames = @(".gitkeep", ".DS_Store", "Thumbs.db")
$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "data\raw"
$inboxDir = Join-Path $rawRoot "entrada_atual"

New-Item -ItemType Directory -Path $inboxDir -Force | Out-Null
$gitkeepPath = Join-Path $inboxDir ".gitkeep"
if (-not (Test-Path $gitkeepPath)) {
    New-Item -ItemType File -Path $gitkeepPath -Force | Out-Null
}

$items = Get-ChildItem -LiteralPath $inboxDir -Force |
    Where-Object { $_.Name -notin $ignoredNames }

if (-not $items) {
    throw "A pasta data\\raw\\entrada_atual esta vazia. Copie os arquivos do lote para la e rode novamente."
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$batchName = "{0}_{1}" -f $timestamp, (Convert-ToSafeName -Value $Name)
$batchDir = Join-Path $rawRoot $batchName
New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

foreach ($item in $items) {
    Move-Item -LiteralPath $item.FullName -Destination $batchDir -Force
}

Write-Host "Arquivos movidos para o lote:" -ForegroundColor Green
Write-Host "  $batchDir"
Write-Host ""
Write-Host "A pasta de entrada ficou pronta para o proximo uso:" -ForegroundColor Cyan
Write-Host "  $inboxDir"
Write-Host ""

$runScript = Join-Path $PSScriptRoot "Run-Batch.ps1"
$runParams = @{
    BatchName = $batchName
}
if ($NoEmbeddings) {
    $runParams.NoEmbeddings = $true
}
if (-not [string]::IsNullOrWhiteSpace($Query)) {
    $runParams.Query = $Query
    $runParams.Limit = $Limit
}
if (-not [string]::IsNullOrWhiteSpace($OutputDir)) {
    $runParams.OutputDir = $OutputDir
}

& $runScript @runParams
exit $LASTEXITCODE
