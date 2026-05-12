from __future__ import annotations

import base64
import json
import html
import re
import smtplib
import unicodedata
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from pdf_export import export_friendly_pdf as export_friendly_pdf_es, export_technical_pdf
from pdf_export_en import export_friendly_pdf as export_friendly_pdf_en
from recommendation_engine import build_engine_config
from roadmap_core import build_roadmap, load_profile_data, save_traceability_csv, save_traceability_json, save_txt
from security_config import load_security_config, validate_smtp_config


ROOT = Path(__file__).resolve().parent
OUTPUT_UI_DIR = ROOT / "outputs" / "ui"
BUDGET_OPTIONS = [
    "up_to_1m",
    "between_1m_5m",
    "from_5m",
]
BUDGET_LABELS_BY_LANG = {
    "es": {
        "up_to_1m": "Hasta CLP 1.000.000",
        "between_1m_5m": "Desde CLP 1.000.001 a CLP 4.999.999",
        "from_5m": "CLP 5.000.000 o más",
    },
    "en": {
        "up_to_1m": "Up to CLP 1,000,000",
        "between_1m_5m": "From CLP 1,000,001 to CLP 4,999,999",
        "from_5m": "CLP 5,000,000 or more",
    },
}
BUDGET_TO_CLP = {
    "up_to_1m": 1_000_000.0,
    "between_1m_5m": 4_999_999.0,
    "from_5m": 5_000_000.0,
}
RUT_WIDGET_KEY = "company_rut_input"
FLAGS_DIR = ROOT / "assets" / "localization" / "flags"
FLAG_ES_PATH = FLAGS_DIR / "es_flag.png"
FLAG_EN_PATH = FLAGS_DIR / "en_flag.png"

UI_TEXTS = {
    "es": {
        "page_title": "Generador de Roadmap Personalizado | Captura",
        "setup_header": "Configuración inicial",
        "company_data_header": "Datos de la empresa",
        "company_type": "Tipo de empresa*",
        "company_type_select": "------Seleccione------",
        "company_small": "Pequeña empresa",
        "company_medium": "Mediana empresa",
        "company_name": "Nombre empresa*",
        "company_name_placeholder": "Ingrese nombre empresa",
        "email": "Correo*",
        "target_level": "Nivel objetivo",
        "improvement_budget": "Presupuesto para mejoras*",
        "required_note": "* Campos obligatorios",
        "invalid_rut": "RUT inválido. Verifica el dígito verificador.",
        "missing_required_warning": "Completa los campos obligatorios del panel izquierdo antes de responder el cuestionario.",
        "missing_prefix": "Faltan:",
        "questions": "Preguntas",
        "profile": "Perfil",
        "target_level_card": "Nivel Objetivo",
        "questionnaire": "Cuestionario",
        "answer": "Respuesta",
        "generate": "Generar Roadmap",
        "generating": "Generando roadmap y archivos de salida...",
        "generated_ok": "Roadmap generado correctamente.",
        "current_score": "Puntaje actual",
        "target_score": "Puntaje objetivo",
        "actions": "Acciones",
        "email_label": "Correo",
        "email_not_sent": "No enviado",
        "download_es": "Descargar Roadmap PDF (ES)",
        "download_en": "Descargar Roadmap PDF (EN)",
        "select_company_type": "Seleccione el tipo de empresa en el panel de la izquierda para continuar.",
        "cannot_load_profile": "No se pudo cargar el perfil",
        "roadmap_error": "No se pudo generar el roadmap",
        "language_button": "English",
        "title_company_default": "Empresa",
        "main_title": "Generador de Roadmap Personalizado | Captura de Datos",
        "missing_company_type": "Tipo de empresa",
        "missing_company_name": "Nombre empresa",
        "missing_rut": "RUT",
        "missing_valid_rut": "RUT válido",
        "missing_email": "Correo",
        "smtp_missing_email": "Por favor ingresa un correo válido en Datos de la empresa (campo Correo).",
        "email_subject": "Roadmap customizado {company}",
        "email_body": "Estimado/a,\nSe adjunta el Roadmap customizado para la empresa {company}.\n*Este es un correo automático. No responder.",
        "not_sent_prefix": "No enviado",
        "sent_prefix": "Enviado a",
        "question_fallback": "Pregunta {qnum}",
        "friendly_label_es": "PDF amigable ES",
        "friendly_label_en": "PDF friendly EN",
    },
    "en": {
        "page_title": "Customized Roadmap Generator | Capture",
        "setup_header": "Initial Setup",
        "company_data_header": "Company Data",
        "company_type": "Company type*",
        "company_type_select": "------Select------",
        "company_small": "Small enterprise",
        "company_medium": "Medium-sized enterprise",
        "company_name": "Company name*",
        "company_name_placeholder": "Enter company name",
        "email": "Email*",
        "target_level": "Target level",
        "improvement_budget": "Improvement budget*",
        "required_note": "* Required fields",
        "invalid_rut": "Invalid RUT. Please verify the check digit.",
        "missing_required_warning": "Complete the required fields in the left panel before answering the questionnaire.",
        "missing_prefix": "Missing:",
        "questions": "Questions",
        "profile": "Profile",
        "target_level_card": "Target Level",
        "questionnaire": "Questionnaire",
        "answer": "Answer",
        "generate": "Generate Roadmap",
        "generating": "Generating roadmap and output files...",
        "generated_ok": "Roadmap generated successfully.",
        "current_score": "Current Score",
        "target_score": "Target Score",
        "actions": "Actions",
        "email_label": "Email",
        "email_not_sent": "Not sent",
        "download_es": "Download PDF Roadmap (ES)",
        "download_en": "Download PDF Roadmap (EN)",
        "select_company_type": "Select a company type to continue.",
        "cannot_load_profile": "Unable to load profile",
        "roadmap_error": "The roadmap could not be generated",
        "language_button": "Español",
        "title_company_default": "Company",
        "main_title": "Customized Roadmap Generator | Company Data Capture",
        "missing_company_type": "Company type",
        "missing_company_name": "Company name",
        "missing_rut": "RUT",
        "missing_valid_rut": "Valid RUT",
        "missing_email": "Email",
        "smtp_missing_email": "Please provide a valid email address in Company Data (Email field).",
        "email_subject": "Customized Roadmap {company}",
        "email_body": "Dear Recipient,\nPlease find attached the customized roadmap for {company}.\n*This is an automated email. Please do not reply.",
        "not_sent_prefix": "Not sent",
        "sent_prefix": "Sent to",
        "question_fallback": "Question {qnum}",
        "friendly_label_es": "Friendly PDF ES",
        "friendly_label_en": "Friendly PDF EN",
    },
}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return clean or "company"


def _lang(lang: str) -> str:
    return "en" if str(lang).lower() == "en" else "es"


def _t(lang: str, key: str, **kwargs: object) -> str:
    data = UI_TEXTS[_lang(lang)].get(key, key)
    return data.format(**kwargs) if kwargs else data


def _budget_labels(lang: str) -> dict[str, str]:
    return BUDGET_LABELS_BY_LANG[_lang(lang)]


@st.cache_data(show_spinner=False)
def _img_data_url(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif suffix == ".svg":
        mime = "image/svg+xml"
    elif suffix == ".webp":
        mime = "image/webp"
    else:
        mime = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _render_language_flag(language: str) -> None:
    current = _lang(language)
    target = "en" if current == "es" else "es"
    target_label = "English" if target == "en" else "Español"
    target_code = "EN" if target == "en" else "ES"
    flag_path = FLAG_EN_PATH if current == "es" else FLAG_ES_PATH
    data_url = _img_data_url(str(flag_path))
    if not data_url:
        if st.button(target_label, key="lang_text_fallback", use_container_width=True):
            st.session_state["ui_language"] = target
            st.rerun()
        return
    st.markdown(
        f"""
<div style="display:flex; justify-content:flex-end; align-items:center; margin-top:2.4rem;">
  <form action="" method="get" style="margin:0; padding:0; display:inline-flex; align-items:center; gap:0.20rem;">
    <input type="hidden" name="ui_lang" value="{target}" />
    <button type="submit" title="{html.escape(target_label)}"
      style="display:inline-flex; width:22px; height:14px; align-items:center; justify-content:center; border:1px solid rgba(31,79,47,0.35); border-radius:2px; overflow:hidden; box-shadow:0 2px 6px rgba(0,0,0,0.12); background:transparent; padding:0; margin:0; cursor:pointer;">
      <img src="{data_url}" alt="{html.escape(target_label)}"
           style="display:block; width:22px; height:14px; object-fit:cover;" />
    </button>
    <span class="lang-code-chip">
      {target_code}
    </span>
  </form>
</div>
        """,
        unsafe_allow_html=True,
    )


def _apply_no_translate_guard(language: str) -> None:
    lang = _lang(language)
    nonce = datetime.now().strftime("%Y%m%d%H%M%S%f")
    components.html(
        f"""
<script>
(function () {{
  try {{
    const doc = window.parent && window.parent.document;
    if (!doc) return;

    const html = doc.documentElement;
    const body = doc.body;
    if (html) {{
      html.setAttribute("lang", "{lang}");
      html.setAttribute("translate", "no");
      html.classList.add("notranslate");
    }}
    if (body) {{
      body.setAttribute("translate", "no");
      body.classList.add("notranslate");
    }}

    const app = doc.querySelector(".stApp");
    if (app) {{
      app.setAttribute("translate", "no");
      app.classList.add("notranslate");
    }}

    let gMeta = doc.querySelector('meta[name="google"]');
    if (!gMeta) {{
      gMeta = doc.createElement("meta");
      gMeta.setAttribute("name", "google");
      doc.head.appendChild(gMeta);
    }}
    gMeta.setAttribute("content", "notranslate");

    let gbMeta = doc.querySelector('meta[name="googlebot"]');
    if (!gbMeta) {{
      gbMeta = doc.createElement("meta");
      gbMeta.setAttribute("name", "googlebot");
      doc.head.appendChild(gbMeta);
    }}
    gbMeta.setAttribute("content", "notranslate");

    const keep = [
      ".stApp",
      '[data-testid="stAppViewContainer"]',
      '[data-testid="stHeader"]',
      '[data-testid="stSidebar"]',
      '[data-testid="stMainBlockContainer"]',
      ".lang-code-chip"
    ];
    keep.forEach((selector) => {{
      doc.querySelectorAll(selector).forEach((el) => {{
        el.setAttribute("translate", "no");
        el.classList.add("notranslate");
      }});
    }});

    doc.querySelectorAll('input[aria-label^="RUT"], input[placeholder*="12.345.678-5"]').forEach((el) => {{
      el.setAttribute("translate", "no");
      el.classList.add("notranslate");
    }});

    doc.querySelectorAll("label, span, p, div").forEach((el) => {{
      const txt = (el.textContent || "").trim().toUpperCase();
      if (txt === "RUT" || txt === "RUT*" || txt.startsWith("RUT INV")) {{
        el.setAttribute("translate", "no");
        el.classList.add("notranslate");
      }}
    }});
  }} catch (e) {{
    console.warn("No-translate guard error:", e);
  }}
}})();
</script>
<div style="display:none" aria-hidden="true">{nonce}</div>
        """,
        height=0,
        width=0,
        scrolling=False,
    )


def _company_name_for_filename(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "", text)
    text = re.sub(r"\s+", "_", text).strip("._-")
    return (text or "Company").upper()


def _friendly_pdf_filename(company_type: str, company_name: str, generated_at: datetime, language: str) -> str:
    prefix = "ME" if str(company_type) == "medium" else "PE"
    stamp = generated_at.strftime("%Y%m%d_%H%M")
    lang_tag = "EN" if _lang(language) == "en" else "ES"
    return f"Roadmap_{prefix}_{_company_name_for_filename(company_name)}_{stamp}_{lang_tag}.pdf"


def _normalize_rut(raw: str) -> str:
    return re.sub(r"[^0-9kK]", "", str(raw or "")).upper()


def _rut_dv(number: str) -> str:
    factors = [2, 3, 4, 5, 6, 7]
    total = 0
    for index, char in enumerate(reversed(number)):
        total += int(char) * factors[index % len(factors)]
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)


def _format_rut(raw: str) -> str:
    normalized = _normalize_rut(raw)
    if len(normalized) < 2:
        return normalized
    body = normalized[:-1]
    dv = normalized[-1]
    reversed_body = body[::-1]
    chunks = [reversed_body[i : i + 3] for i in range(0, len(reversed_body), 3)]
    body_formatted = ".".join(chunk[::-1] for chunk in chunks[::-1])
    return f"{body_formatted}-{dv}"


def _is_valid_rut(raw: str) -> bool:
    normalized = _normalize_rut(raw)
    if len(normalized) < 2 or not normalized[:-1].isdigit():
        return False
    return _rut_dv(normalized[:-1]) == normalized[-1]


def _on_rut_change() -> None:
    st.session_state[RUT_WIDGET_KEY] = _format_rut(str(st.session_state.get(RUT_WIDGET_KEY, "")))


@st.cache_data(show_spinner=False)
def _load_profile_cached(root: str, company_type: str, language: str) -> dict[str, object]:
    return load_profile_data(Path(root), company_type, language=_lang(language))


def _render_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bitter:wght@600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {
  --primary-color: #2f6d3c;
  --agri-leaf-900: #1f4f2f;
  --agri-leaf-700: #2f6d3c;
  --agri-leaf-500: #6f8f4e;
  --agri-earth-700: #7a4f2c;
  --agri-earth-500: #a3703f;
  --agri-wheat-100: #f5edd5;
  --agri-sky-100: #dbe9dd;
  --agri-paper: #f8f4e9;
  --agri-ink: #27372e;
  --agri-moss-100: #e8efe2;
  --agri-moss-300: #c9d8bf;
  --agri-moss-700: #355e3b;
  --agri-clay-500: #8a6744;
}

.stApp {
  font-family: "Source Sans 3", sans-serif;
  color: var(--agri-ink);
}

.notranslate, [translate="no"] {
  -webkit-user-select: text;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 12% 12%, rgba(111, 143, 78, 0.22), transparent 32%),
    radial-gradient(circle at 90% 4%, rgba(163, 112, 63, 0.16), transparent 28%),
    linear-gradient(180deg, #e7f0e2 0%, #f8f4e9 52%, #f3ebd6 100%);
}

[data-testid="stHeader"] {
  background:
    linear-gradient(90deg, #2f6f46 0%, #3d7d4a 55%, #8a6744 100%) !important;
  border-bottom: 1px solid rgba(25, 83, 56, 0.55);
}

[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stHeader"] [data-testid="stToolbar"] {
  color: #f7f3e8 !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button,
[data-testid="stHeader"] [data-testid="stToolbar"] button {
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  background: transparent !important;
  border: 0 !important;
  border-radius: 0 !important;
  min-width: 44px !important;
  min-height: 40px !important;
  box-shadow: none !important;
  opacity: 1 !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button {
  background: rgba(25, 83, 56, 0.62) !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button:hover,
[data-testid="stHeader"] [data-testid="stToolbar"] button:hover {
  background: rgba(25, 83, 56, 0.45) !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button:hover {
  background: rgba(17, 64, 44, 0.82) !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button svg,
[data-testid="stHeader"] [data-testid="stToolbar"] button svg {
  width: 20px !important;
  height: 20px !important;
  color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
  stroke-width: 2.2 !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] button svg path,
[data-testid="stHeader"] [data-testid="collapsedControl"] button svg line,
[data-testid="stHeader"] [data-testid="collapsedControl"] button svg polyline {
  stroke: #f7f3e8 !important;
  fill: #f7f3e8 !important;
}

[data-testid="stSidebarCollapsedControl"] button {
  background: rgba(25, 83, 56, 0.62) !important;
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  border: 0 !important;
  border-radius: 0 !important;
  min-width: 44px !important;
  min-height: 40px !important;
  box-shadow: none !important;
  opacity: 1 !important;
}

[data-testid="stSidebarCollapsedControl"] button:hover {
  background: rgba(17, 64, 44, 0.82) !important;
}

[data-testid="stSidebarCollapsedControl"] {
  opacity: 1 !important;
}

[data-testid="stSidebarCollapsedControl"] > div,
[data-testid="stSidebarCollapsedControl"] button > div,
[data-testid="stSidebarCollapsedControl"] button span,
[data-testid="stSidebarCollapsedControl"] button p {
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

[data-testid="stSidebarCollapsedControl"] button svg,
[data-testid="stSidebarCollapsedControl"] button svg path,
[data-testid="stSidebarCollapsedControl"] button svg line,
[data-testid="stSidebarCollapsedControl"] button svg polyline {
  color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
  stroke-width: 2.2 !important;
  opacity: 1 !important;
}

[data-testid="stSidebarCollapsedControl"] button *,
[data-testid="stHeader"] [data-testid="collapsedControl"] button *,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button * {
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
  opacity: 1 !important;
}

[data-testid="stSidebar"] {
  background:
    linear-gradient(180deg, #2f6f46 0%, #3d7d4a 58%, #8a6744 100%) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.10);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
  color: #f7f3e8 !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  padding-top: 0.5rem;
}

[data-testid="stSidebar"] hr {
  border: 0 !important;
  border-top: 1px solid rgba(25, 83, 56, 0.55) !important;
  margin-top: 0.95rem !important;
  margin-bottom: 1.15rem !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
  background: transparent !important;
  color: #f7f3e8 !important;
  border: 0 !important;
  box-shadow: none !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button svg {
  color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
}

.block-container {
  padding-top: 2.0rem;
  padding-bottom: 2.5rem;
}

h1, h2, h3 {
  font-family: "Bitter", serif;
  letter-spacing: 0.2px;
  color: var(--agri-leaf-900);
}

.app-card {
  background:
    linear-gradient(115deg, rgba(245, 237, 213, 0.88) 0%, rgba(248, 244, 233, 0.92) 58%, rgba(219, 233, 221, 0.88) 100%);
  border: 1px solid rgba(47, 109, 60, 0.28);
  border-left: 6px solid var(--agri-leaf-700);
  border-radius: 14px;
  box-shadow: 0 10px 24px rgba(47, 69, 50, 0.12);
  padding: 16px 18px;
  margin-bottom: 14px;
}

.app-tip {
  background: linear-gradient(90deg, rgba(201, 216, 191, 0.58), rgba(232, 239, 226, 0.80));
  border: 1px solid rgba(53, 94, 59, 0.28);
  border-left: 5px solid #355e3b;
  border-radius: 10px;
  color: #234730;
  font-family: "Source Sans 3", sans-serif;
  font-size: 1.06rem;
  font-weight: 600;
  line-height: 1.35;
  padding: 0.88rem 1rem;
  margin-bottom: 0.8rem;
}

.app-title {
  font-family: "Bitter", serif;
  font-weight: 800;
  color: var(--agri-leaf-900);
  margin-bottom: 5px;
}

.app-sub {
  color: #395748;
  font-size: 0.96rem;
  line-height: 1.45;
}

.summary-card {
  margin-top: 0.15rem;
  margin-bottom: 0.9rem;
  min-height: 104px;
}

.summary-label {
  font-family: "Bitter", serif;
  font-weight: 700;
  color: #2f4a3b;
  font-size: 1.02rem;
}

.summary-value {
  font-family: "Bitter", serif;
  font-weight: 800;
  color: var(--agri-earth-700);
  font-size: 2rem;
  line-height: 1.1;
  margin-top: 0.35rem;
}

.summary-value-text {
  font-size: 1.45rem;
  line-height: 1.2;
}

[data-testid="stMetric"] {
  background: rgba(248, 244, 233, 0.76);
  border: 1px solid rgba(111, 143, 78, 0.3);
  border-radius: 12px;
  padding: 10px 14px;
  box-shadow: 0 8px 18px rgba(47, 79, 61, 0.08);
}

[data-testid="stMetricValue"] {
  color: var(--agri-earth-700);
  font-family: "Bitter", serif;
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stRadio"] label,
[data-testid="stSlider"] div {
  font-family: "Source Sans 3", sans-serif;
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background-color: rgba(248, 244, 233, 0.9);
  border: 1px solid rgba(122, 79, 44, 0.3);
  border-radius: 10px;
  color: var(--agri-ink) !important;
  -webkit-text-fill-color: var(--agri-ink) !important;
}

[data-testid="stTextInput"] input::placeholder {
  color: #687a6d !important;
  opacity: 1;
}

[data-testid="stSidebar"] [data-testid="stTextInput"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background-color: #dfddd1 !important;
  border: 1px solid rgba(0, 0, 0, 0.08) !important;
  color: #2a322d !important;
  -webkit-text-fill-color: var(--agri-ink) !important;
  box-shadow: none !important;
}

[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] svg {
  color: #2a322d !important;
  fill: #2a322d !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
  border-color: var(--agri-leaf-700);
  box-shadow: 0 0 0 0.15rem rgba(47, 109, 60, 0.22);
}

[data-testid="stButton"] > button {
  border: 0;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--agri-leaf-700) 0%, var(--agri-leaf-500) 65%, #8ea763 100%);
  color: #fbf8ef;
  font-weight: 700;
  letter-spacing: 0.2px;
  padding-top: 0.65rem;
  padding-bottom: 0.65rem;
  box-shadow: 0 10px 20px rgba(47, 79, 61, 0.2);
  transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
}

[data-testid="stButton"] > button:hover {
  transform: translateY(-1px);
  filter: brightness(1.02);
  box-shadow: 0 14px 24px rgba(47, 79, 61, 0.24);
}

[data-testid="stDownloadButton"] > button {
  border-radius: 10px;
  border: 1px solid rgba(122, 79, 44, 0.32);
  background: rgba(245, 237, 213, 0.88);
  color: #4a3625;
  font-weight: 600;
}

[data-testid="stDownloadButton"] > button:hover {
  border-color: rgba(47, 109, 60, 0.48);
  color: var(--agri-leaf-900);
}

[data-testid="stRadio"] > div {
  background: rgba(248, 244, 233, 0.72);
  border: 1px solid rgba(111, 143, 78, 0.3);
  border-radius: 12px;
  padding: 6px 10px 4px;
}

[data-testid="stRadio"] label {
  border-radius: 8px;
  padding: 2px 4px;
  color: #2d4135 !important;
  font-weight: 600;
}

[data-testid="stRadio"] label p,
[data-testid="stRadio"] label span,
[data-testid="stRadio"] label div {
  color: #2d4135 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-weight: 600 !important;
}

[data-testid="stRadio"] label code {
  color: #2d4135 !important;
  background: transparent !important;
  border: 0 !important;
  padding: 0 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-weight: 600 !important;
}

[data-testid="stRadio"] [data-testid="stWidgetLabel"] p {
  color: #f7f3e8 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-weight: 700 !important;
}

[data-testid="stRadio"] label:has(input[type="radio"]:checked) {
  background: rgba(47, 109, 60, 0.14);
  border: 1px solid rgba(47, 109, 60, 0.42);
}

[data-testid="stRadio"] input[type="radio"] {
  accent-color: var(--agri-leaf-700) !important;
}

[data-testid="stSlider"] div[data-baseweb="slider"] [role="slider"] {
  background-color: var(--agri-leaf-700) !important;
  border-color: var(--agri-leaf-700) !important;
  box-shadow: 0 0 0 0.15rem rgba(47, 109, 60, 0.22) !important;
}

[data-testid="stSlider"] div[data-baseweb="slider"] > div > div {
  background: linear-gradient(to right, rgba(47, 109, 60, 0.9), rgba(111, 143, 78, 0.25)) !important;
}

[data-testid="stSlider"] div[data-baseweb="slider"] > div[data-testid="stTickBar"] {
  background: rgba(111, 143, 78, 0.28) !important;
}

.question-label {
  font-family: "Bitter", serif;
  font-weight: 700;
  font-size: 1.04rem;
  color: #1f3d2d;
  margin-top: 0.5rem;
}

.question-text {
  color: #2f4438;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.field-error {
  color: #ff7b72 !important;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.2;
  margin-top: -0.85rem;
  margin-bottom: 0.2rem;
  padding-left: 0.1rem;
}

[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.field-error) {
  margin-top: -0.95rem !important;
  margin-bottom: 0 !important;
  padding-top: 0 !important;
}

[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.field-error) [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.field-error) p {
  margin: 0 !important;
  padding: 0 !important;
}

.stCaption {
  color: #486351;
}

.lang-code-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  height: auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: #1f4f2f;
  font-family: "Source Sans 3", sans-serif;
  font-size: 0.60rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  line-height: 1;
  transform: translateY(0.5px);
}

.sidebar-field-label {
  color: #2d4135 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-weight: 700;
  font-size: 0.96rem;
  margin-top: 0.2rem;
  margin-bottom: 0.15rem;
}

.sidebar-required-note {
  color: #2d4135 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-size: 0.82rem;
  font-weight: 600;
  margin-top: 0.2rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(profile: dict[str, object], max_level: int, language: str) -> dict[str, object]:
    budget_labels = _budget_labels(language)
    st.sidebar.header(_t(language, "company_data_header"))
    company_name = st.sidebar.text_input(_t(language, "company_name"), value="", placeholder=_t(language, "company_name_placeholder"))
    if RUT_WIDGET_KEY not in st.session_state:
        st.session_state[RUT_WIDGET_KEY] = ""
    company_rut = st.sidebar.text_input(
        "RUT*",
        key=RUT_WIDGET_KEY,
        placeholder="12.345.678-5",
        max_chars=12,
        on_change=_on_rut_change,
    )
    company_rut = _format_rut(company_rut)
    if company_rut and not _is_valid_rut(company_rut):
        st.sidebar.markdown(
            """
<style>
 [data-testid="stSidebar"] input[aria-label^="RUT"] {
  border: 1px solid #ff7b72 !important;
  box-shadow: 0 0 0 0.12rem rgba(255, 123, 114, 0.28) !important;
}
</style>
            """,
            unsafe_allow_html=True,
        )
        st.sidebar.markdown(f"<div class='field-error'>{html.escape(_t(language, 'invalid_rut'))}</div>", unsafe_allow_html=True)
    company_email = st.sidebar.text_input(_t(language, "email"), value="")
    target_level = st.sidebar.slider(_t(language, "target_level"), min_value=1, max_value=max_level, value=min(3, max_level), step=1)
    budget_total_key = st.sidebar.radio(
        _t(language, "improvement_budget"),
        options=BUDGET_OPTIONS,
        index=1,
        format_func=lambda key: budget_labels.get(str(key), str(key)),
    )
    st.sidebar.markdown(f"<div class='sidebar-required-note'>{html.escape(_t(language, 'required_note'))}</div>", unsafe_allow_html=True)

    return {
        "company_name": company_name,
        "company_rut": company_rut,
        "company_email": company_email,
        "target_level": target_level,
        "budget_total_label": budget_labels.get(str(budget_total_key), str(budget_total_key)),
        "budget_total_clp": BUDGET_TO_CLP[str(budget_total_key)],
        "profile_label": profile.get("label", ""),
    }


def _collect_answers(company_type: str, questions: list[dict[str, Any]]) -> dict[int, int]:
    answers: dict[int, int] = {}
    for q in questions:
        qnum = int(q["number"])
        key = f"q_{company_type}_{qnum}"
        selected = int(st.session_state.get(key, 0))
        answers[qnum] = selected + 1
    return answers


def _build_overrides(ui_cfg: dict[str, object]) -> dict[str, Any]:
    return {
        "budget_total_clp": float(ui_cfg["budget_total_clp"]),
    }


def _missing_required_company_fields(company_type: str, ui_cfg: dict[str, object], language: str) -> list[str]:
    missing: list[str] = []
    if company_type == "__select__":
        missing.append(_t(language, "missing_company_type"))
    if not str(ui_cfg.get("company_name", "")).strip():
        missing.append(_t(language, "missing_company_name"))
    rut_value = str(ui_cfg.get("company_rut", "")).strip()
    if not rut_value:
        missing.append(_t(language, "missing_rut"))
    elif not _is_valid_rut(rut_value):
        missing.append(_t(language, "missing_valid_rut"))
    if not str(ui_cfg.get("company_email", "")).strip():
        missing.append(_t(language, "missing_email"))
    return missing


def _clean_prompt(prompt: str, qnum: int, language: str) -> str:
    text = str(prompt or "").strip()
    text = re.sub(rf"^\s*(?:pregunta|question)\s*{qnum}\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:pregunta|question)\s*\d+\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    return text or _t(language, "question_fallback", qnum=qnum)


def _send_pdfs_via_gmail(
    *,
    root: Path,
    company_name: str,
    company_email: str,
    pdf_paths: list[Path],
    language: str,
) -> list[str]:
    cfg, _ = load_security_config(root)
    if not cfg.smtp_host:
        cfg.smtp_host = "smtp.gmail.com"
    if cfg.smtp_port <= 0:
        cfg.smtp_port = 587

    errors = validate_smtp_config(cfg, strict=True)
    if errors:
        raise RuntimeError("Incomplete SMTP configuration: " + " | ".join(errors))

    targets: list[str] = []
    for raw in [str(company_email or "")]:
        parts = [x.strip() for x in raw.split(",") if x.strip()]
        for p in parts:
            if p not in targets:
                targets.append(p)
    if not targets:
        raise RuntimeError(_t(language, "smtp_missing_email"))

    msg = EmailMessage()
    msg["Subject"] = _t(language, "email_subject", company=company_name)
    msg["From"] = cfg.smtp_from
    msg["To"] = ", ".join(targets)
    msg.set_content(_t(language, "email_body", company=company_name))

    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            continue
        msg.add_attachment(
            pdf_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(cfg.smtp_user, cfg.smtp_password)
        smtp.send_message(msg)
    return targets


def _render_downloads(result: dict[str, object], language: str) -> None:
    files: dict[str, str] = result.get("files", {}) if isinstance(result, dict) else {}
    pdf_es: Path | None = None
    pdf_en: Path | None = None
    for path_str in files.values():
        path = Path(path_str)
        if not path.exists() or path.suffix.lower() != ".pdf":
            continue
        name_txt = path.name.lower()
        if name_txt.endswith("_es.pdf"):
            pdf_es = path
        if name_txt.endswith("_en.pdf"):
            pdf_en = path

    if pdf_es is None and pdf_en is None:
        return

    col_es, col_en = st.columns(2)
    if pdf_es is not None:
        with col_es:
            st.download_button(
                label=_t(language, "download_es"),
                data=pdf_es.read_bytes(),
                file_name=pdf_es.name,
                mime="application/pdf",
                use_container_width=True,
            )
    if pdf_en is not None:
        with col_en:
            st.download_button(
                label=_t(language, "download_en"),
                data=pdf_en.read_bytes(),
                file_name=pdf_en.name,
                mime="application/pdf",
                use_container_width=True,
            )


def _render_last_result_summary(last: dict[str, object], language: str) -> None:
    st.success(_t(language, "generated_ok"))
    m1, m2, m3 = st.columns(3)
    m1.metric(_t(language, "current_score"), last.get("current_score", 0))
    m2.metric(_t(language, "target_score"), last.get("target_score", 0))
    m3.metric(_t(language, "actions"), last.get("actions", 0))
    if str(last.get("email_status", "")).startswith(_t(language, "sent_prefix")):
        st.info(f"{_t(language, 'email_label')}: {last['email_status']}")
    else:
        st.warning(f"{_t(language, 'email_label')}: {last.get('email_status', _t(language, 'email_not_sent'))}")


def main() -> None:
    st.set_page_config(page_title="Generador de Roadmap Personalizado / Customized Roadmap Generator", layout="wide")
    _render_styles()

    if "ui_language" not in st.session_state:
        st.session_state["ui_language"] = "es"

    qp_lang = st.query_params.get("ui_lang")
    if qp_lang:
        st.session_state["ui_language"] = _lang(str(qp_lang))

    language = _lang(str(st.session_state.get("ui_language", "es")))
    _apply_no_translate_guard(language)

    top_left, top_right = st.columns([8, 2])
    with top_right:
        _render_language_flag(language)

    st.sidebar.header(_t(language, "setup_header"))
    company_type_labels = {
        "__select__": _t(language, "company_type_select"),
        "small": _t(language, "company_small"),
        "medium": _t(language, "company_medium"),
    }
    company_type = st.sidebar.selectbox(
        _t(language, "company_type"),
        options=["__select__", "small", "medium"],
        format_func=lambda x: company_type_labels.get(x, x),
    )
    st.sidebar.markdown("---")
    with top_left:
        if company_type == "__select__":
            st.title(_t(language, "main_title"))
        else:
            selected_company_type = company_type_labels.get(company_type, "")
            st.title(f"{_t(language, 'main_title')} {selected_company_type}")

    if company_type == "__select__":
        st.markdown(f"<div class='app-tip'>{html.escape(_t(language, 'select_company_type'))}</div>", unsafe_allow_html=True)
        return

    try:
        profile = _load_profile_cached(str(ROOT), company_type, language)
    except Exception as exc:
        st.error(f"{_t(language, 'cannot_load_profile')} '{company_type}': {exc}")
        return

    questions: list[dict[str, Any]] = [dict(x) for x in profile.get("questions", [])]
    max_level = max((len(q.get("level_labels", [])) for q in questions), default=5)
    ui_cfg = _render_sidebar(profile, max_level=max_level, language=language)
    missing_required = _missing_required_company_fields(company_type, ui_cfg, language)
    if missing_required:
        st.warning(_t(language, "missing_required_warning"))
        st.caption(_t(language, "missing_prefix") + " " + ", ".join(missing_required))
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">{_t(language, "questions")}</div>
  <div class="summary-value">{len(questions)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">{_t(language, "profile")}</div>
  <div class="summary-value summary-value-text">{html.escape(str(ui_cfg.get("profile_label", "")))}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">{_t(language, "target_level_card")}</div>
  <div class="summary-value">{int(ui_cfg["target_level"])}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader(_t(language, "questionnaire"))
    for q in sorted(questions, key=lambda row: int(row.get("number", 0))):
        qnum = int(q["number"])
        options = [str(x) for x in q.get("options", [])]
        prompt = _clean_prompt(str(q.get("prompt", "")), qnum, language)

        st.markdown(f"<div class='question-label'>{_t(language, 'question_fallback', qnum=qnum)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='question-text'>{html.escape(prompt)}</div>", unsafe_allow_html=True)
        st.radio(
            label=f"{_t(language, 'answer')} {qnum}",
            options=list(range(len(options))),
            format_func=lambda i, rows=options: rows[i],
            key=f"q_{company_type}_{qnum}",
            label_visibility="collapsed",
        )

    if st.button(_t(language, "generate"), type="primary", use_container_width=True):
        try:
            answers = _collect_answers(company_type, questions)
            engine_cfg = build_engine_config(None, _build_overrides(ui_cfg))

            with st.spinner(_t(language, "generating")):
                payload_es = build_roadmap(
                    root=ROOT,
                    company_type=company_type,
                    answers=answers,
                    target_level=int(ui_cfg["target_level"]),
                    company_name=str(ui_cfg["company_name"]),
                    company_rut=str(ui_cfg["company_rut"]),
                    company_email=str(ui_cfg["company_email"]),
                    engine_cfg=engine_cfg,
                    language="es",
                )
                payload_en = build_roadmap(
                    root=ROOT,
                    company_type=company_type,
                    answers=answers,
                    target_level=int(ui_cfg["target_level"]),
                    company_name=str(ui_cfg["company_name"]),
                    company_rut=str(ui_cfg["company_rut"]),
                    company_email=str(ui_cfg["company_email"]),
                    engine_cfg=engine_cfg,
                    language="en",
                )
                payload_selected = payload_en if language == "en" else payload_es

                generated_at = datetime.now()
                stamp = generated_at.strftime("%Y%m%d_%H%M%S")
                case_name = _slug(str(ui_cfg["company_name"]))
                run_dir = OUTPUT_UI_DIR / f"{case_name}_{stamp}"
                run_dir.mkdir(parents=True, exist_ok=True)

                result_json = run_dir / "roadmap_result.json"
                result_txt = run_dir / "roadmap_result.txt"
                result_trace_json = run_dir / "roadmap_traceability.json"
                result_trace_csv = run_dir / "roadmap_traceability.csv"
                result_pdf_tech = run_dir / "roadmap_tecnico.pdf"
                result_pdf_es = run_dir / _friendly_pdf_filename(
                    company_type=company_type,
                    company_name=str(ui_cfg["company_name"]),
                    generated_at=generated_at,
                    language="es",
                )
                result_pdf_en = run_dir / _friendly_pdf_filename(
                    company_type=company_type,
                    company_name=str(ui_cfg["company_name"]),
                    generated_at=generated_at,
                    language="en",
                )

                payload_export = dict(payload_selected)
                payload_export.pop("catalog_validation_report", None)
                result_json.write_text(json.dumps(payload_export, ensure_ascii=False, indent=2), encoding="utf-8")
                save_txt(payload_selected, result_txt)
                save_traceability_json(payload_selected, result_trace_json)
                save_traceability_csv(payload_selected, result_trace_csv)

                generated_files = {
                    "JSON": str(result_json),
                    "TXT": str(result_txt),
                    "Traceability JSON": str(result_trace_json),
                    "Traceability CSV": str(result_trace_csv),
                }

                export_technical_pdf(payload_selected, result_pdf_tech)
                export_friendly_pdf_es(payload_es, result_pdf_es)
                export_friendly_pdf_en(payload_en, result_pdf_en)
                generated_files["Technical PDF"] = str(result_pdf_tech)
                generated_files[_t(language, "friendly_label_es")] = str(result_pdf_es)
                generated_files[_t(language, "friendly_label_en")] = str(result_pdf_en)

                selected_pdf = result_pdf_en if language == "en" else result_pdf_es
                email_status = _t(language, "email_not_sent")
                try:
                    recipients = _send_pdfs_via_gmail(
                        root=ROOT,
                        company_name=str(ui_cfg["company_name"]),
                        company_email=str(ui_cfg["company_email"]),
                        pdf_paths=[selected_pdf],
                        language=language,
                    )
                    email_status = f"{_t(language, 'sent_prefix')}: {', '.join(recipients)}"
                except Exception as email_exc:
                    email_status = f"{_t(language, 'not_sent_prefix')}: {email_exc}"

                result = payload_selected.get("result", {})
                st.session_state["ui_last_result"] = {
                    "files": generated_files,
                    "generated_at": result.get("timestamp", ""),
                    "current_score": result.get("current_score", 0),
                    "target_score": result.get("target_score", 0),
                    "actions": len(result.get("roadmap_entries", [])),
                    "email_status": email_status,
                    "language": language,
                }

        except Exception as exc:
            st.error(f"{_t(language, 'roadmap_error')}: {exc}")

    if "ui_last_result" in st.session_state:
        current_lang = _lang(str(st.session_state["ui_last_result"].get("language", language)))
        _render_last_result_summary(st.session_state["ui_last_result"], current_lang)
        _render_downloads(st.session_state["ui_last_result"], current_lang)


if __name__ == "__main__":
    main()
