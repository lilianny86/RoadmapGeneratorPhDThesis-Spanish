# RoGen (Roadmap Generator) - Directions

RoGen is a decision-support framework for planning technology adoption in small and medium-sized agricultural enterprises. It combines questionnaires tailored to each enterprise profile, a maturity assessment, a solution catalog, and a recommendation engine that links identified gaps to proposed actions.

## Components and Scope

| Component | Version or location |
| --- | --- |
| Assessment instrument | Version `2026.07`, in [`questionnaire_instrument.py`](questionnaire_instrument.py). It covers 21 key performance indicators (KPIs) for small enterprises and 22 for medium-sized enterprises. |
| Maturity matrices and KPI weights | [`assets/modelo_de_madurez/`](assets/modelo_de_madurez/) |
| Solution catalog | Version v4, in [`assets/catalogo_soluciones/`](assets/catalogo_soluciones/) |
| Recommendation engine | `eng_v2.0`, in [`recommendation_engine.py`](recommendation_engine.py) |

The engine matches solutions by enterprise profile, domain, key decision area (KDA), KPI, and maturity transition. It prioritizes actions compatible with the budget capacity defined for the enterprise profile. If no compatible action is selected for a transition, the engine may propose an alternative subject to economic effort, a quotation, or co-financing. The budget range declared in Chilean pesos determines the capacity category. The engine does not estimate total costs or confirm that funding is available.

## Running RoGen

RoGen requires Python 3.10 or later and the model and catalog files included in the repository. From the repository root, preferably in an active virtual environment, install the dependencies:

```sh
python -m pip install -r requirements.txt
```

### Interactive Application

```sh
python -m streamlit run streamlit_app.py
```

Streamlit prints the local address in the terminal. To test the application without sending real emails, use synthetic data and leave SMTP credentials unconfigured. Without a pseudonymization key, RoGen generates the PDFs but does not produce the statistical CSV files.

### Reproducible Command-Line Example

This example creates 21 synthetic responses for a small enterprise, sets the target maturity level to 3, and selects the low budget-capacity category. It does not require informed consent, email, or real company identifiers. The value `1` denotes the **position** of the selected option for each question, not a maturity level entered directly in the file.

```sh
python -c "import json; from pathlib import Path; p = Path('outputs/revision'); p.mkdir(parents=True, exist_ok=True); (p / 'respuestas_sinteticas.json').write_text(json.dumps([1] * 21), encoding='utf-8')"
python roadmap_core.py --company-type small --target-level 3 --answers-file outputs/revision/respuestas_sinteticas.json --budget-capacity small_low --language en --output-pdf outputs/revision/roadmap_en.pdf --strict-catalog
```

**Expected output with the files in this version:** 212 catalog records processed, 0 catalog errors, 84 candidate solutions, 28 selected actions, and one English-language PDF. These counts apply only to the synthetic example.

The budget-capacity codes are `small_low`, `small_medium`, and `small_high` for small enterprises, and `medium_low`, `medium_medium`, and `medium_high` for medium-sized enterprises. Use `--language es` to generate the roadmap in Spanish. Use `--skip-pdf` to run the assessment without generating a PDF.

## Documents

### Application Outputs

RoGen stores assessment files in separate subfolders under `outputs/ui/`.

| Document | Generation and access |
| --- | --- |
| Roadmap PDFs in Spanish and English | Both versions are available for download. When email delivery is configured, the participant receives the roadmap in the language used for the assessment. |
| Informed consent receipt (PDF) | Generated in the language in which consent was given. It is available for download and accompanies the roadmap in the participant's email. |
| Statistical summary, KPI-level detail, and variable guide (CSV) | When pseudonymization is configured, the application saves these files before attempting to email them. They are internal research records and are not available for download by participants. |

The statistical summary and KPI-level detail distinguish transitions with compatible actions from those with only conditional alternatives. To calculate overall roadmap coverage, add the number of transitions with a compatible action and the number with a conditional alternative, then divide by the number of required transitions, provided that this number is greater than zero.

### Command-Line JSON Files

- `--answers-file` reads the responses from a JSON file. It accepts either a list in questionnaire order or an object that maps question numbers to selected option positions. Either format may be nested under the `answers` key.
- `--engine-config-file` accepts an optional JSON file for overriding engine parameters. The example uses the default configuration and does not require this file.
- `--output-json` optionally exports the assessment and traceability records. Without this flag, no results JSON file is written. The export may contain the company name, Chilean taxpayer identification number (RUT), and email address if supplied on the command line. It should not be treated as pseudonymized.

The interactive application does not generate JSON files for individual assessments. The command-line interface generates one PDF in the selected language unless `--skip-pdf` is used. It does not generate consent receipts or statistical CSVs, and it does not send emails.

## Confidentiality and Pseudonymization

To generate statistical CSVs in Streamlit, set `ROADMAP_PARTICIPANT_SALT` as an environment variable or as a secret in `.streamlit/secrets.toml`. RoGen uses HMAC-SHA256 to derive a stable company code from the RUT. Use the same key to link repeated assessments of a company over the course of the study. Do not publish the key or SMTP credentials.

The statistical CSVs do not contain company names, RUTs, or email addresses, but they do include a stable company code and the date and time of generation. PDFs, company-named folders, and internal emails may contain identifiable information.




# RoGen (Roadmap Generator) - Instrucciones

RoGen es un marco de apoyo a la toma de decisiones para planificar la adopción tecnológica en pequeñas y medianas empresas agrícolas. Integra cuestionarios específicos por perfil, un diagnóstico de madurez, un catálogo de soluciones y un motor que vincula las brechas detectadas con acciones recomendadas.

## Componentes y alcance

| Componente | Versión o ubicación |
| --- | --- |
| Instrumento de diagnóstico | Versión `2026.07`, en [`questionnaire_instrument.py`](questionnaire_instrument.py). Incluye 21 indicadores clave de desempeño (KPI) para pequeñas empresas y 22 para medianas. |
| Matrices de madurez y ponderaciones | [`assets/modelo_de_madurez/`](assets/modelo_de_madurez/) |
| Catálogo de soluciones | Versión v4, en [`assets/catalogo_soluciones/`](assets/catalogo_soluciones/) |
| Motor de recomendaciones | `eng_v2.0`, en [`recommendation_engine.py`](recommendation_engine.py) |

El motor busca coincidencias por perfil empresarial, dominio, área clave de decisión (KDA), KPI y transición de madurez. Prioriza acciones compatibles con la capacidad presupuestaria relativa al perfil. Si no selecciona una acción compatible para una transición, puede proponer una alternativa condicionada al esfuerzo económico, a cotización o a cofinanciamiento. El rango declarado en pesos chilenos se utiliza para determinar la categoría de capacidad; el motor no calcula un costo total ni confirma que exista financiamiento.

## Ejecución

Requisitos: Python 3.10 o posterior y los archivos del modelo y del catálogo incluidos en el repositorio. Desde la raíz del repositorio, preferiblemente en un entorno virtual activo:

```sh
python -m pip install -r requirements.txt
```

### Aplicación interactiva

```sh
python -m streamlit run streamlit_app.py
```

La aplicación muestra la dirección local en la consola. 
Para una prueba de revisión sin correos reales, use datos ficticios y no configure credenciales SMTP. Sin una clave de seudonimización, se generan los PDF, pero no los CSV estadísticos.

### Ejemplo reproducible por consola

El ejemplo genera 21 respuestas sintéticas para una pequeña empresa, selecciona el nivel objetivo 3 y usa la categoría presupuestaria baja. No requiere consentimiento, correo ni identificadores reales. La opción `1` se refiere a la **posición** de la alternativa en cada pregunta, no a un nivel escrito directamente en el archivo.

```sh
python -c "import json; from pathlib import Path; p = Path('outputs/revision'); p.mkdir(parents=True, exist_ok=True); (p / 'respuestas_sinteticas.json').write_text(json.dumps([1] * 21), encoding='utf-8')"
python roadmap_core.py --company-type small --target-level 3 --answers-file outputs/revision/respuestas_sinteticas.json --budget-capacity small_low --language en --output-pdf outputs/revision/roadmap_en.pdf --strict-catalog
```

**Resultado esperado con los archivos de esta versión:** 212 registros del catálogo procesados, 0 errores de catálogo, 84 soluciones candidatas, 28 seleccionadas y un PDF en inglés. Estas cifras corresponden únicamente al caso sintético.

Los códigos de capacidad son `small_low`, `small_medium` y `small_high` para pequeñas empresas; `medium_low`, `medium_medium` y `medium_high` para medianas. `--language es` genera el roadmap en español. `--skip-pdf` ejecuta el diagnóstico sin generar el PDF.

## Documentos

### Salidas de la aplicación

Las evaluaciones se guardan en subcarpetas de `outputs/ui/`.

| Documento | Generación y acceso |
| --- | --- |
| Roadmap PDF en español e inglés | Ambos se pueden descargar. Si el envío está configurado, se adjunta al correo del participante el PDF en el idioma de la evaluación. |
| Comprobante de consentimiento PDF | Se genera en el idioma en que se aceptó el consentimiento. Está disponible para descarga y acompaña el roadmap en el correo del participante. |
| Resumen estadístico, detalle por KPI y guía de variables (CSV) | Se guardan antes del intento de envío si la seudonimización está configurada. Son archivos internos de investigación, sin botón de descarga para el participante. |

El resumen y el detalle por KPI distinguen las transiciones con acciones compatibles de las que solo tienen alternativas condicionadas. Para calcular la cobertura total del roadmap, sume las transiciones con acción compatible y las que tienen alternativa condicionada, y divida el total por las transiciones requeridas cuando el denominador sea mayor que cero.

### Uso de JSON en la consola

- `--answers-file` lee las respuestas en JSON. Acepta una lista en orden de pregunta o un objeto que asocie los números de pregunta con las posiciones seleccionadas. Ambos formatos pueden ir bajo la clave `answers`.
- `--engine-config-file` admite un JSON opcional para reemplazar parámetros del motor. El ejemplo de revisión utiliza la configuración predeterminada y no necesita ese archivo.
- `--output-json` es una exportación opcional del diagnóstico y la trazabilidad. Sin esa opción no se escribe un JSON de resultados. El archivo puede incluir nombre, RUT y correo si se proporcionan al ejecutar la consola; no debe tratarse como una salida seudonimizada.

La aplicación no genera JSON por evaluación. La consola genera un único PDF en el idioma solicitado, salvo que se use `--skip-pdf`, y no genera comprobantes, CSV estadísticos ni correos.

## Confidencialidad y seudonimización

Para generar los CSV en Streamlit, configure `ROADMAP_PARTICIPANT_SALT` como variable de entorno o como secreto en `.streamlit/secrets.toml`. RoGen deriva el código estable de empresa del RUT mediante HMAC-SHA256. Mantenga la misma clave para relacionar mediciones de una empresa a lo largo del estudio. No publique la clave ni las credenciales SMTP.

Los CSV no contienen nombre, RUT ni correo, pero incluyen un código estable y la fecha y hora de generación. Los PDF, las carpetas nombradas por empresa y el correo interno pueden contener información identificable.



