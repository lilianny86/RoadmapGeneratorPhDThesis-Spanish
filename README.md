# RoadmapGenerator

Framework para capturar datos de empresa, procesar cuestionarios y generar roadmaps tecnol?gicos (JSON/TXT/PDF) para PyMEs agr?colas.

## Ejecuci?n local

```powershell
cd D:\!!!! TESIS\RoadmapGenerator
pip install -r requirements_ui.txt
python run_roadmap.py --company-type small --target-level 3 --answers-file examples\answers_small.json --company-name "Demo Small"
python run_roadmap.py --company-type medium --target-level 4 --answers-file examples\answers_medium.json --company-name "Demo Medium"
```

Interfaz Streamlit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_ui.ps1
```

URL local: `http://localhost:8501`

## Estructura de salidas
- `outputs\roadmap_result.json`
- `outputs\roadmap_result.txt`
- `outputs\roadmap_traceability.json`
- `outputs\roadmap_traceability.csv`
- `outputs\roadmap_tecnico.pdf`
- `outputs\roadmap_amigable.pdf`

## GitHub Pages (importante)
GitHub Pages **solo publica contenido est?tico** (HTML/CSS/JS).
La app Streamlit no corre directamente en GitHub Pages.

Recomendaci?n:
1. Usar GitHub Pages para landing/documentaci?n del proyecto.
2. Publicar la app en Streamlit Community Cloud (o Render/Railway).
3. Enlazar la app publicada desde `docs/index.html`.

## Deploy de landing en Pages
1. Mant?n `docs/index.html` versionado.
2. En GitHub: `Settings -> Pages`.
3. `Source`: `Deploy from a branch`.
4. `Branch`: `main` y carpeta `/docs`.
5. Guardar y esperar URL p?blica.

## Seguridad SMTP
- No subir `.env` a GitHub.
- Mantener `.env.example` sin secretos reales.

