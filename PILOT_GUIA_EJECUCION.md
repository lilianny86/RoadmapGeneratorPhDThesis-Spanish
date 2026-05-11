# Guía De Piloto (REL-02)

## Objetivo
Ejecutar un piloto controlado de 3 a 5 empresas para validar:
- calidad del roadmap generado,
- consistencia de presupuesto/recomendaciones,
- legibilidad de entregables para decisión.

## 1) Preparar casos
1. Copiar `examples/pilot_cases_template.json`.
2. Reemplazar empresas de ejemplo por casos reales.
3. Verificar `company_type` (`small` o `medium`) y `target_level`.
4. Cargar respuestas por archivo (`answers_file`) o en línea (`answers`).

## 2) Ejecutar piloto batch
```powershell
python pilot_batch.py --cases-file examples/pilot_cases_template.json --strict-catalog
```

Opcional:
```powershell
python pilot_batch.py --cases-file examples/pilot_cases_template.json --strict-catalog --with-pdf
```

## 3) Revisar salidas
Se generan en `outputs/pilot`:
- `pilot_summary.json`
- `pilot_summary.txt`
- `pilot_summary.csv`
- `*_result.json` y `*_result.txt` por caso
- `*_tecnico.pdf` y `*_amigable.pdf` por caso (si usas `--with-pdf`)

## 4) Criterios de aceptación sugeridos
- 0 errores de catálogo (`catalog_errors=0`).
- 100% de casos ejecutados sin fallas (`status=ok`).
- Cobertura de acciones en corto/mediano/largo plazo.
- Informe amigable entendible por negocio (validación cualitativa).

## 5) Cierre del piloto
1. Consolidar observaciones por empresa.
2. Ajustar pesos/límites del motor si se detectan sesgos.
3. Congelar baseline y publicar versión candidata.
