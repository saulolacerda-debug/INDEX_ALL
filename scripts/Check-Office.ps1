$ErrorActionPreference = "Stop"
try {
    $w = New-Object -ComObject Word.Application
    Write-Host "WORD_OK"
    $w.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($w) | Out-Null
} catch {
    Write-Host "WORD_FAIL"
}
try {
    $e = New-Object -ComObject Excel.Application
    Write-Host "EXCEL_OK"
    $e.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($e) | Out-Null
} catch {
    Write-Host "EXCEL_FAIL"
}
