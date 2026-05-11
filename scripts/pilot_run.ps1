param(
    [string]$CasesFile = "examples\pilot_cases_template.json",
    [switch]$WithPdf
)

$ErrorActionPreference = "Stop"

Write-Host "[REL-02] Ejecutando piloto batch con casos:" $CasesFile
$cmd = @(
    "pilot_batch.py",
    "--cases-file", $CasesFile,
    "--strict-catalog"
)
if ($WithPdf) {
    $cmd += "--with-pdf"
}

python @cmd
Write-Host "[REL-02] Piloto completado."
