param(
    [string]$BatchDate = (Get-Date -Format "yyyy-MM-dd"),
    [string]$SourceRoot,
    [string]$RawRoot,
    [switch]$ResetExisting
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Remove-Diacritics {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrEmpty($Value)) {
        return ""
    }

    $normalized = $Value.Normalize([Text.NormalizationForm]::FormD)
    $builder = New-Object System.Text.StringBuilder

    foreach ($char in $normalized.ToCharArray()) {
        if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($char) -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
            [void]$builder.Append($char)
        }
    }

    return $builder.ToString().Normalize([Text.NormalizationForm]::FormC)
}

function Convert-ToSlug {
    param(
        [AllowNull()]
        [string]$Value
    )

    $ascii = Remove-Diacritics -Value $Value
    $ascii = $ascii.ToLowerInvariant()
    $ascii = [regex]::Replace($ascii, "[^a-z0-9]+", "_")
    $ascii = $ascii.Trim("_")
    if ([string]::IsNullOrWhiteSpace($ascii)) {
        return "item"
    }

    return $ascii
}

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
        generated_text_files = 0
        converted_docx_files = 0
        preserved_unindexed_files = 0
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

function Write-TextArtifact {
    param(
        [string]$DestinationPath,
        [string]$Content,
        [System.Collections.IDictionary]$BatchRecord
    )

    Ensure-ParentDirectory -FilePath $DestinationPath
    Set-Content -LiteralPath $DestinationPath -Value $Content -Encoding utf8
    $BatchRecord.generated_text_files++
}

function Read-TextFileSafe {
    param(
        [string]$Path
    )

    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding utf8
    }
    catch {
        return Get-Content -LiteralPath $Path -Raw
    }
}

function Convert-MarkdownFileToText {
    param(
        [System.IO.FileInfo]$SourceFile,
        [string]$DestinationPath,
        [System.Collections.IDictionary]$BatchRecord,
        [string]$Title,
        [string]$Category
    )

    $body = Read-TextFileSafe -Path $SourceFile.FullName
    $header = @(
        "Titulo: $Title"
        "Categoria: $Category"
        "Fonte original: $($SourceFile.FullName)"
        ""
    ) -join [Environment]::NewLine

    Write-TextArtifact -DestinationPath $DestinationPath -Content ($header + $body) -BatchRecord $BatchRecord
}

function Try-OpenWordApplication {
    try {
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        $word.DisplayAlerts = 0
        return $word
    }
    catch {
        return $null
    }
}

function Convert-DocToDocx {
    param(
        [System.IO.FileInfo]$SourceFile,
        [string]$DestinationPath,
        $WordApplication
    )

    if ($null -eq $WordApplication) {
        return $false
    }

    Ensure-ParentDirectory -FilePath $DestinationPath

    $document = $null

    try {
        $document = $WordApplication.Documents.Open($SourceFile.FullName, $false, $true)
        $document.SaveAs([ref]$DestinationPath, [ref]12)
        $document.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
        return $true
    }
    catch {
        if ($null -ne $document) {
            try {
                $document.Close($false)
                [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
            }
            catch {
            }
        }

        return $false
    }
}

function Close-WordApplication {
    param(
        $WordApplication
    )

    if ($null -eq $WordApplication) {
        return
    }

    try {
        $WordApplication.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($WordApplication)
    }
    catch {
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

function Get-LegislationTargetFolder {
    param(
        [string]$FileName,
        [string]$SourceFolderName
    )

    $normalized = Convert-ToSlug -Value $FileName
    $sourceFolder = Convert-ToSlug -Value $SourceFolderName

    if ($sourceFolder -eq "normas_procedimento" -or $normalized -like "*norma_de_procedimento*") {
        return "normas_procedimento"
    }

    if ($normalized -like "*lei*") {
        return "leis"
    }

    if ($normalized -like "*decreto*") {
        return "decretos"
    }

    if ($normalized -like "*portaria*") {
        return "portarias"
    }

    if (
        $normalized -like "*resol*" -or
        $normalized -like "*sumula*" -or
        $normalized -match '(^|_)\d{1,4}_r($|_)'
    ) {
        return "resolucoes"
    }

    return "normas_mistas"
}

function Get-FormularioTargetFolder {
    param(
        [string]$FileName
    )

    $normalized = Convert-ToSlug -Value $FileName

    if ($normalized -like "*procura*") {
        return "procuracoes"
    }

    if ($normalized -like "*visita*tecnica*" -or $normalized -like "*solicitacao*de*visita*") {
        return "visitas_tecnicas"
    }

    if ($normalized -like "*aditivo*") {
        return "aditivos"
    }

    if ($normalized -like "*alteracao*projeto*" -or $normalized -like "*enquadramento*") {
        return "alteracao_projeto"
    }

    if ($normalized -like "*termo*de*acordo*" -and $normalized -notlike "*aditivo*") {
        return "termo_acordo"
    }

    return "requerimentos"
}

function Get-ReceitaCategoryFolder {
    param(
        [string]$RelativeDirectory
    )

    $normalized = Convert-ToSlug -Value $RelativeDirectory

    if ($normalized -like "01_01_*") {
        return "adesao"
    }

    if ($normalized -like "02_02_*") {
        return "recolhimento_icms"
    }

    if ($normalized -like "03_03_*") {
        return "apuracao_escrituracao"
    }

    if ($normalized -like "*indice*") {
        return "indice"
    }

    return "orientacoes_gerais"
}

function Convert-JsonFileToText {
    param(
        [System.IO.FileInfo]$SourceFile,
        [string]$DestinationPath,
        [System.Collections.IDictionary]$BatchRecord
    )

    $raw = Read-TextFileSafe -Path $SourceFile.FullName

    try {
        $parsed = $raw | ConvertFrom-Json
        $pretty = $parsed | ConvertTo-Json -Depth 100
    }
    catch {
        $pretty = $raw
    }

    $content = @(
        "Arquivo JSON convertido para texto"
        "Fonte original: $($SourceFile.FullName)"
        ""
        $pretty
    ) -join [Environment]::NewLine

    Write-TextArtifact -DestinationPath $DestinationPath -Content $content -BatchRecord $BatchRecord
}

function Get-RelativePathSafe {
    param(
        [string]$BasePath,
        [string]$FullPath
    )

    return [System.IO.Path]::GetRelativePath($BasePath, $FullPath)
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Join-Path $projectRoot "data\raw\entrada_atual"
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

$batchNames = [ordered]@{
    jurisprudencia_cerf = "${BatchDate}_invest_jurisprudencia_cerf"
    jurisprudencia_getri = "${BatchDate}_invest_jurisprudencia_getri"
    pareceres_sefaz = "${BatchDate}_invest_pareceres_sefaz"
    legislacao_normas = "${BatchDate}_invest_legislacao_normas"
    orientacoes_receita = "${BatchDate}_invest_orientacoes_receita"
    formularios_modelos = "${BatchDate}_invest_formularios_modelos"
    paginas_servicos_sedes = "${BatchDate}_invest_paginas_servicos_sedes"
    catalogos_metadados = "${BatchDate}_invest_catalogos_metadados"
}

$manifest = [ordered]@{
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

$word = Try-OpenWordApplication
if ($null -eq $word) {
    Add-BatchWarning -BatchRecord $manifest.batches.formularios_modelos -Message "Microsoft Word nao disponivel. Os .doc serao tratados com fallback para .txt quando houver .md correspondente."
}

try {
    $cerfRoot = Join-Path $SourceRoot "cerf_invest_julgamentos\acordaos"
    if (Test-Path -LiteralPath $cerfRoot) {
        Get-ChildItem -LiteralPath $cerfRoot -Recurse -File -Filter "*.html" | ForEach-Object {
            $relative = Get-RelativePathSafe -BasePath $cerfRoot -FullPath $_.FullName
            $destination = Join-Path $batchPaths.jurisprudencia_cerf $relative
            Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.jurisprudencia_cerf
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.jurisprudencia_cerf -Message "Pasta CERF nao encontrada."
    }

    $getriRoot = Join-Path $SourceRoot "getri_invest_julgamentos"
    if (Test-Path -LiteralPath $getriRoot) {
        Get-ChildItem -LiteralPath $getriRoot -Recurse -File -Filter "*.pdf" | ForEach-Object {
            $relative = Get-RelativePathSafe -BasePath $getriRoot -FullPath $_.FullName
            $destination = Join-Path $batchPaths.jurisprudencia_getri $relative
            Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.jurisprudencia_getri
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.jurisprudencia_getri -Message "Pasta GETRI nao encontrada."
    }

    $pareceresRoot = Join-Path $SourceRoot "sefaz_invest_pareceres"
    if (Test-Path -LiteralPath $pareceresRoot) {
        Get-ChildItem -LiteralPath $pareceresRoot -Recurse -File -Filter "*.pdf" | ForEach-Object {
            $yearMatch = [regex]::Match($_.BaseName, '(19|20)\d{2}')
            $targetFolder = if ($yearMatch.Success) { $yearMatch.Value } else { "sem_ano_definido" }
            $destination = Join-Path (Join-Path $batchPaths.pareceres_sefaz $targetFolder) $_.Name
            Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.pareceres_sefaz
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.pareceres_sefaz -Message "Pasta de pareceres SEFAZ nao encontrada."
    }

    foreach ($sourceLeaf in @("legislacao_normas", "normas_procedimento")) {
        $sourceDir = Join-Path $SourceRoot ("sedes_invest_conteudo\" + $sourceLeaf)
        if (-not (Test-Path -LiteralPath $sourceDir)) {
            Add-BatchWarning -BatchRecord $manifest.batches.legislacao_normas -Message "Pasta nao encontrada: $sourceDir"
            continue
        }

        Get-ChildItem -LiteralPath $sourceDir -Recurse -File -Filter "*.pdf" | ForEach-Object {
            $targetFolder = Get-LegislationTargetFolder -FileName $_.BaseName -SourceFolderName $sourceLeaf
            $destination = Join-Path (Join-Path $batchPaths.legislacao_normas $targetFolder) $_.Name
            Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.legislacao_normas
        }
    }

    $receitaRoot = Join-Path $SourceRoot "receita_orienta_invest"
    if (Test-Path -LiteralPath $receitaRoot) {
        Get-ChildItem -LiteralPath $receitaRoot -Recurse -File | ForEach-Object {
            if ($_.Extension -eq ".md") {
                if ($_.BaseName -like "*indice*") {
                    $targetFolder = "indice"
                }
                else {
                    $relativeDir = Split-Path (Get-RelativePathSafe -BasePath $receitaRoot -FullPath $_.DirectoryName) -Parent
                    if ([string]::IsNullOrWhiteSpace($relativeDir) -or $relativeDir -eq ".") {
                        $relativeDir = $_.Directory.Name
                    }
                    $targetFolder = Get-ReceitaCategoryFolder -RelativeDirectory $relativeDir
                }
                $destination = Join-Path (Join-Path $batchPaths.orientacoes_receita $targetFolder) ($_.BaseName + ".txt")
                Convert-MarkdownFileToText -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.orientacoes_receita -Title $_.BaseName -Category $targetFolder
            }
            elseif ($_.Extension -eq ".html") {
                $destination = Join-Path (Join-Path $batchPaths.orientacoes_receita "pagina_origem") $_.Name
                Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.orientacoes_receita
            }
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.orientacoes_receita -Message "Pasta receita_orienta_invest nao encontrada."
    }

    $formulariosRoot = Join-Path $SourceRoot "sedes_invest_conteudo\formularios_modelos"
    if (Test-Path -LiteralPath $formulariosRoot) {
        $sourceFiles = Get-ChildItem -LiteralPath $formulariosRoot -File
        foreach ($file in $sourceFiles) {
            $targetFolder = Get-FormularioTargetFolder -FileName $file.BaseName

            switch ($file.Extension.ToLowerInvariant()) {
                ".docx" {
                    $destination = Join-Path (Join-Path $batchPaths.formularios_modelos $targetFolder) $file.Name
                    Copy-FileToBatch -SourceFile $file -DestinationPath $destination -BatchRecord $manifest.batches.formularios_modelos
                }
                ".doc" {
                    $destination = Join-Path (Join-Path $batchPaths.formularios_modelos $targetFolder) ($file.BaseName + ".docx")
                    $converted = Convert-DocToDocx -SourceFile $file -DestinationPath $destination -WordApplication $word
                    if ($converted) {
                        $manifest.batches.formularios_modelos.converted_docx_files++
                    }
                    else {
                        $markdownPath = Join-Path $file.DirectoryName ($file.BaseName + ".md")
                        if (Test-Path -LiteralPath $markdownPath) {
                            $markdownFile = Get-Item -LiteralPath $markdownPath
                            $textPath = Join-Path (Join-Path $batchPaths.formularios_modelos $targetFolder) ($file.BaseName + ".txt")
                            Convert-MarkdownFileToText -SourceFile $markdownFile -DestinationPath $textPath -BatchRecord $manifest.batches.formularios_modelos -Title $file.BaseName -Category $targetFolder
                            Add-BatchWarning -BatchRecord $manifest.batches.formularios_modelos -Message "Fallback para .txt usado em: $($file.Name)"
                        }
                        else {
                            $destinationDoc = Join-Path (Join-Path $batchPaths.formularios_modelos "__originais_nao_indexaveis") $file.Name
                            Copy-FileToBatch -SourceFile $file -DestinationPath $destinationDoc -BatchRecord $manifest.batches.formularios_modelos
                            $manifest.batches.formularios_modelos.preserved_unindexed_files++
                            Add-BatchWarning -BatchRecord $manifest.batches.formularios_modelos -Message "Nao foi possivel converter nem gerar fallback textual para: $($file.Name)"
                        }
                    }
                }
            }
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.formularios_modelos -Message "Pasta formularios_modelos nao encontrada."
    }

    $sedesMappings = @{
        "documentos_gerais" = "documentos_gerais"
        "pagina_principal" = "pagina_principal"
        "sistemas_e_servicos" = "sistemas_servicos"
    }
    foreach ($mapping in $sedesMappings.GetEnumerator()) {
        $sourceDir = Join-Path $SourceRoot ("sedes_invest_conteudo\" + $mapping.Key)
        if (-not (Test-Path -LiteralPath $sourceDir)) {
            Add-BatchWarning -BatchRecord $manifest.batches.paginas_servicos_sedes -Message "Pasta nao encontrada: $sourceDir"
            continue
        }

        Get-ChildItem -LiteralPath $sourceDir -Recurse -File -Filter "*.html" | ForEach-Object {
            $destination = Join-Path (Join-Path $batchPaths.paginas_servicos_sedes $mapping.Value) $_.Name
            Copy-FileToBatch -SourceFile $_ -DestinationPath $destination -BatchRecord $manifest.batches.paginas_servicos_sedes
        }
    }

    $inventarioRoot = Join-Path $SourceRoot "inventario_metadatos"
    if (Test-Path -LiteralPath $inventarioRoot) {
        Get-ChildItem -LiteralPath $inventarioRoot -File | ForEach-Object {
            $sourceFile = $_
            switch ($sourceFile.Extension.ToLowerInvariant()) {
                ".csv" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "catalogos_csv") $sourceFile.Name
                    Copy-FileToBatch -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
                ".xlsx" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "catalogos_xlsx") $sourceFile.Name
                    Copy-FileToBatch -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
                ".json" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "manifestos_json") ($sourceFile.BaseName + ".txt")
                    Convert-JsonFileToText -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
            }
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.catalogos_metadados -Message "Pasta inventario_metadatos nao encontrada."
    }

    $baseMestraRoot = Join-Path $SourceRoot "invest_es_base_mestra"
    if (Test-Path -LiteralPath $baseMestraRoot) {
        Get-ChildItem -LiteralPath $baseMestraRoot -File | ForEach-Object {
            $sourceFile = $_
            switch ($sourceFile.Extension.ToLowerInvariant()) {
                ".csv" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "bases_mestres") $sourceFile.Name
                    Copy-FileToBatch -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
                ".xlsx" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "bases_mestres") $sourceFile.Name
                    Copy-FileToBatch -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
                ".json" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "bases_mestres") ($sourceFile.BaseName + ".txt")
                    Convert-JsonFileToText -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados
                }
                ".md" {
                    $destination = Join-Path (Join-Path $batchPaths.catalogos_metadados "bases_mestres") ($sourceFile.BaseName + ".txt")
                    Convert-MarkdownFileToText -SourceFile $sourceFile -DestinationPath $destination -BatchRecord $manifest.batches.catalogos_metadados -Title $sourceFile.BaseName -Category "bases_mestres"
                }
            }
        }
    }
    else {
        Add-BatchWarning -BatchRecord $manifest.batches.catalogos_metadados -Message "Pasta invest_es_base_mestra nao encontrada."
    }
}
finally {
    Close-WordApplication -WordApplication $word
}

$manifestPath = Join-Path $RawRoot ("{0}_invest_preparacao_manifest.json" -f $BatchDate)
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host ""
Write-Host "Lotes INVEST preparados com sucesso." -ForegroundColor Green
Write-Host "Manifesto:" -ForegroundColor Cyan
Write-Host "  $manifestPath"
Write-Host ""

foreach ($entry in $manifest.batches.GetEnumerator()) {
    Write-Host ("{0}" -f $entry.Value.name) -ForegroundColor Yellow
    Write-Host ("  Pasta: {0}" -f $entry.Value.path)
    Write-Host ("  Copiados: {0}" -f $entry.Value.copied_files)
    Write-Host ("  Textos gerados: {0}" -f $entry.Value.generated_text_files)
    Write-Host ("  DOC/DOCX convertidos: {0}" -f $entry.Value.converted_docx_files)
    Write-Host ("  Originais nao indexaveis preservados: {0}" -f $entry.Value.preserved_unindexed_files)
    if ($entry.Value.warnings.Count -gt 0) {
        Write-Host ("  Avisos: {0}" -f $entry.Value.warnings.Count) -ForegroundColor DarkYellow
    }
    Write-Host ""
}

$manifestPath
