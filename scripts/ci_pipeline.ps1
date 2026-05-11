param(
    [switch]$UpdatePdfBaseline
)

$ErrorActionPreference = "Stop"

Write-Host "[CI] Ejecutando tests unitarios e integracion..."
python run_tests.py

Write-Host "[CI] Ejecutando smoke con seguridad y catalogo estricto..."
python run_roadmap.py `
  --company-type small `
  --target-level 3 `
  --answers-file examples\answers_small.json `
  --company-name "CI Small" `
  --security-check `
  --strict-catalog `
  --output-json outputs\ci_small.json `
  --output-txt outputs\ci_small.txt `
  --output-pdf-tech outputs\ci_small_tecnico.pdf `
  --output-pdf-friendly outputs\ci_small_amigable.pdf

if ($UpdatePdfBaseline) {
    Write-Host "[CI] Actualizando baseline PDF..."
    python qa_pdf_regression.py --update-baseline
} else {
    Write-Host "[CI] Validando regresion PDF..."
    python qa_pdf_regression.py
}

Write-Host "[CI] OK"
