param(
    [string]$BatchDate = (Get-Date -Format "yyyy-MM-dd"),
    [string]$SourceRoot,
    [string]$RawRoot,
    [switch]$ResetExisting
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-CleanDirectory {
    param(
        [string]$Path,
        [switch]$AllowReset
    )

    if (Test-Path -LiteralPath $Path) {
        if (-not $AllowReset) {
            throw "A pasta ja existe. Use -ResetExisting para recriar: $Path"
        }
        Remove-Item -LiteralPath $Path -Recurse -Force
    }

    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Ensure-ParentDirectory {
    param(
        [string]$FilePath
    )

    $parent = Split-Path -Parent $FilePath
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

function New-BatchRecord {
    param(
        [string]$Name,
        [string]$Path
    )

    return @{
        name = $Name
        path = $Path
        copied_files = 0
        warnings = @()
    }
}

function Add-BatchWarning {
    param(
        [System.Collections.IDictionary]$BatchRecord,
        [string]$Message
    )

    $BatchRecord.warnings = @($BatchRecord.warnings + $Message)
}

function Copy-FileToBatch {
    param(
        [System.IO.FileInfo]$SourceFile,
        [string]$DestinationPath,
        [System.Collections.IDictionary]$BatchRecord
    )

    Ensure-ParentDirectory -FilePath $DestinationPath
    Copy-Item -LiteralPath $SourceFile.FullName -Destination $DestinationPath -Force
    $BatchRecord.copied_files++
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Join-Path $projectRoot "data\raw\entrada_atual\iob-invest"
}
if ([string]::IsNullOrWhiteSpace($RawRoot)) {
    $RawRoot = Join-Path $projectRoot "data\raw"
}

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "Pasta de origem nao encontrada: $SourceRoot"
}

if (-not (Test-Path -LiteralPath $RawRoot)) {
    throw "Pasta raw nao encontrada: $RawRoot"
}

$batchNames = @{
    icms_guias = "${BatchDate}_iob_invest_icms_guias"
    perguntas_respostas = "${BatchDate}_iob_invest_perguntas_respostas"
}

$manifest = @{
    batch_date = $BatchDate
    generated_at = (Get-Date).ToString("o")
    source_root = $SourceRoot
    raw_root = $RawRoot
    batches = @{}
}

$batchPaths = @{}
foreach ($entry in $batchNames.GetEnumerator()) {
    $batchPath = Join-Path $RawRoot $entry.Value
    Ensure-CleanDirectory -Path $batchPath -AllowReset:$ResetExisting
    $batchPaths[$entry.Key] = $batchPath
    $manifest.batches[$entry.Key] = New-BatchRecord -Name $entry.Value -Path $batchPath
}

$files = Get-ChildItem -LiteralPath $SourceRoot -File -Filter "*.pdf" | Sort-Object Name
foreach ($file in $files) {
    if ($file.Name -like "ICMS-ES - *") {
        $destination = Join-Path $batchPaths.icms_guias $file.Name
        Copy-FileToBatch -SourceFile $file -DestinationPath $destination -BatchRecord $manifest.batches.icms_guias
        continue
    }

    if ($file.Name -like "PR - *") {
        $destination = Join-Path $batchPaths.perguntas_respostas $file.Name
        Copy-FileToBatch -SourceFile $file -DestinationPath $destination -BatchRecord $manifest.batches.perguntas_respostas
        continue
    }
}

$expectedMissing = Join-Path $SourceRoot "IOB Online.pdf"
if (-not (Test-Path -LiteralPath $expectedMissing)) {
    Add-BatchWarning -BatchRecord $manifest.batches.icms_guias -Message "Arquivo ausente na origem e nao copiado: IOB Online.pdf"
}

$manifestPath = Join-Path $RawRoot ("{0}_iob_invest_preparacao_manifest.json" -f $BatchDate)
$manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host ""
Write-Host "Lotes IOB INVEST preparados com sucesso." -ForegroundColor Green
Write-Host "Manifesto:" -ForegroundColor Cyan
Write-Host "  $manifestPath"
Write-Host ""

foreach ($entry in $manifest.batches.GetEnumerator()) {
    Write-Host ($entry.Value.name) -ForegroundColor Yellow
    Write-Host ("  Pasta: {0}" -f $entry.Value.path)
    Write-Host ("  Copiados: {0}" -f $entry.Value.copied_files)
    if ($entry.Value.warnings.Count -gt 0) {
        Write-Host ("  Avisos: {0}" -f $entry.Value.warnings.Count) -ForegroundColor DarkYellow
    }
    Write-Host ""
}

$manifestPath
