param(
    [Parameter(Position = 0)]
    [string]$Name = "lote"
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

$projectRoot = Split-Path -Parent $PSScriptRoot
$rawRoot = Join-Path $projectRoot "data\raw"
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$batchName = "{0}_{1}" -f $timestamp, (Convert-ToSafeName -Value $Name)
$batchDir = Join-Path $rawRoot $batchName

New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

Write-Host "Lote criado em:" -ForegroundColor Green
Write-Host "  $batchDir"
Write-Host ""
Write-Host "Copie os arquivos PDF/CSV para essa pasta e processe com:" -ForegroundColor Cyan
Write-Host "  .\scripts\Run-Batch.ps1 -BatchName $batchName"

$batchDir
