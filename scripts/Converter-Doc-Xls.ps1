param(
    [Parameter(Position = 0)]
    [string]$InputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InputDir)) {
    throw "Informe o diretorio de entrada. Ex: .\scripts\Converter-Doc-Xls.ps1 'C:\caminho\pasta'"
}

if (-not (Test-Path $InputDir)) {
    throw "Diretorio nao encontrado: $InputDir"
}

# Encontrar todos os .doc e .xls recursivamente
$docFiles = Get-ChildItem -Path $InputDir -Recurse -Include "*.doc" | Where-Object { $_.Extension -eq ".doc" }
$xlsFiles = Get-ChildItem -Path $InputDir -Recurse -Include "*.xls" | Where-Object { $_.Extension -eq ".xls" }

$totalDoc = @($docFiles).Count
$totalXls = @($xlsFiles).Count

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Conversao de formatos antigos" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Arquivos .doc encontrados: $totalDoc" -ForegroundColor Yellow
Write-Host "Arquivos .xls encontrados: $totalXls" -ForegroundColor Yellow
Write-Host ""

$convertedCount = 0
$failedFiles = @()

# Converter .doc -> .docx usando Word COM
if ($totalDoc -gt 0) {
    Write-Host "Abrindo Microsoft Word..." -ForegroundColor DarkGray
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0  # wdAlertsNone

    foreach ($file in $docFiles) {
        $sourcePath = $file.FullName
        $destPath = $sourcePath + "x"  # .doc -> .docx

        Write-Host "  Convertendo: $($file.Name) -> $($file.Name)x" -ForegroundColor Gray
        try {
            $doc = $word.Documents.Open($sourcePath, $false, $true)
            # wdFormatXMLDocument = 12
            $doc.SaveAs([ref]$destPath, [ref]12)
            $doc.Close($false)
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($doc) | Out-Null
            $convertedCount++

            # Remover arquivo original apos conversao bem-sucedida
            Remove-Item -LiteralPath $sourcePath -Force
        }
        catch {
            Write-Host "    ERRO: $_" -ForegroundColor Red
            $failedFiles += $sourcePath
        }
    }

    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    Write-Host "Word fechado." -ForegroundColor DarkGray
    Write-Host ""
}

# Converter .xls -> .xlsx usando Excel COM
if ($totalXls -gt 0) {
    Write-Host "Abrindo Microsoft Excel..." -ForegroundColor DarkGray
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    foreach ($file in $xlsFiles) {
        $sourcePath = $file.FullName
        $destPath = $sourcePath + "x"  # .xls -> .xlsx

        Write-Host "  Convertendo: $($file.Name) -> $($file.Name)x" -ForegroundColor Gray
        try {
            $wb = $excel.Workbooks.Open($sourcePath, 0, $true)
            # xlOpenXMLWorkbook = 51
            $wb.SaveAs($destPath, 51)
            $wb.Close($false)
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($wb) | Out-Null
            $convertedCount++

            # Remover arquivo original apos conversao bem-sucedida
            Remove-Item -LiteralPath $sourcePath -Force
        }
        catch {
            Write-Host "    ERRO: $_" -ForegroundColor Red
            $failedFiles += $sourcePath
        }
    }

    $excel.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
    Write-Host "Excel fechado." -ForegroundColor DarkGray
    Write-Host ""
}

# Forcar limpeza COM
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Conversao concluida!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Convertidos com sucesso: $convertedCount" -ForegroundColor Green

if ($failedFiles.Count -gt 0) {
    Write-Host "Falhas: $($failedFiles.Count)" -ForegroundColor Red
    foreach ($f in $failedFiles) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    exit 1
}
