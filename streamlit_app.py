from __future__ import annotations

import base64
import json
import os
import html
import re
import smtplib
import ssl
import unicodedata
import uuid
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

from pdf_export import export_friendly_pdf as export_friendly_pdf_es, export_technical_pdf
from pdf_export_en import export_friendly_pdf as export_friendly_pdf_en
from consent_export import CONSENT_VERSION, build_consent_record, consent_sections, export_consent_pdf
from stats_export import (
    build_kpi_statistical_csv_bytes,
    build_kpi_statistical_records,
    build_statistical_csv_bytes,
    build_statistical_data_guide_csv_bytes,
    build_statistical_record,
)
from display_format import format_clp, format_decimal, format_integer, format_timestamp, to_float
from recommendation_engine import build_engine_config
from roadmap_core import build_roadmap, load_profile_data, save_traceability_csv, save_traceability_json, save_txt
from security_config import ENV_KEYS, load_security_config, validate_smtp_config


ROOT = Path(__file__).resolve().parent
OUTPUT_UI_DIR = ROOT / "outputs" / "ui"
BUDGET_OPTIONS_BY_COMPANY = {
    "small": [
        "up_to_1m",
        "between_1m_3m",
        "between_3m_5m",
    ],
    "medium": [
        "up_to_1m",
        "between_1m_5m",
        "between_5m_10m",
    ],
}
BUDGET_LABELS_BY_LANG = {
    "es": {
        "up_to_1m": "Hasta CLP $ 1.000.000,00",
        "between_1m_3m": "Desde CLP $ 1.000.001,00 hasta CLP $ 3.000.000,00",
        "between_3m_5m": "Desde CLP $ 3.000.001,00 hasta CLP $ 5.000.000,00",
        "between_1m_5m": "Desde CLP $ 1.000.001,00 hasta CLP $ 5.000.000,00",
        "between_5m_10m": "Desde CLP $ 5.000.001,00 hasta CLP $ 10.000.000,00",
    },
    "en": {
        "up_to_1m": "Up to CLP $ 1.000.000,00",
        "between_1m_3m": "From CLP $ 1.000.001,00 to CLP $ 3.000.000,00",
        "between_3m_5m": "From CLP $ 3.000.001,00 to CLP $ 5.000.000,00",
        "between_1m_5m": "From CLP $ 1.000.001,00 to CLP $ 5.000.000,00",
        "between_5m_10m": "From CLP $ 5.000.001,00 to CLP $ 10.000.000,00",
    },
}
BUDGET_TO_CLP = {
    "up_to_1m": 1_000_000.0,
    "between_1m_3m": 3_000_000.0,
    "between_3m_5m": 5_000_000.0,
    "between_1m_5m": 5_000_000.0,
    "between_5m_10m": 10_000_000.0,
}
RUT_WIDGET_KEY = "company_rut_input"
FLAGS_DIR = ROOT / "assets" / "localization" / "flags"
FLAG_ES_PATH = FLAGS_DIR / "es_flag.png"
FLAG_EN_PATH = FLAGS_DIR / "en_flag.png"
CATALOG_PATH = ROOT / "assets" / "roadmap" / "Catalogo_Soluciones_MM_Agro_Pymes_v3-Chile - revisado expertos INIA.xlsx"

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
        "rut_label": "RUT (sin puntos ni guión)*",
        "email": "Correo*",
        "target_level": "Nivel objetivo*",
        "target_level_help_small": "1: La gesti\u00f3n depende principalmente de tareas manuales, registros simples y baja estandarizaci\u00f3n.\n2: La empresa ya usa herramientas digitales en procesos clave, aunque todav\u00eda con integraci\u00f3n parcial.\n3: Los procesos est\u00e1n estandarizados, conectados y apoyados por datos para tomar mejores decisiones.",
        "target_level_help_medium": "1: La gesti\u00f3n es reactiva, con baja estandarizaci\u00f3n, poca integraci\u00f3n y dependencia de esfuerzos individuales.\n2: Existen procesos iniciales de formalizaci\u00f3n, control operativo y uso digital en algunas \u00e1reas.\n3: Las \u00e1reas se coordinan mejor, se monitorean indicadores y se integran procesos relevantes.\n4: La gesti\u00f3n es integrada, trazable y orientada a mejora continua mediante tecnolog\u00eda y datos.",
        "improvement_budget": "Presupuesto para mejoras (1 año)*.",
        "required_note": "* Campos obligatorios",
        "invalid_rut": "RUT inválido. Verifica el dígito verificador.",
        "missing_required_warning": "Completa los campos obligatorios del panel izquierdo antes de responder el cuestionario.",
        "missing_prefix": "Faltan:",
        "questions": "Preguntas",
        "profile": "Perfil",
        "target_level_card": "Nivel Objetivo",
        "questionnaire": "Cuestionario",
        "questionnaire_instruction": "Responda según la situación actual. Seleccione una alternativa por pregunta. Si la empresa usa prácticas de más de un nivel, elija la práctica de mayor nivel que utiliza habitualmente.",
        "answer": "Respuesta",
        "generate": "Generar Roadmap",
        "generating": "Generando roadmap y archivos de salida...",
        "generating_overlay_title": "Generando Roadmap",
        "generating_overlay_text": "El proceso puede tardar unos segundos.",
        "generated_ok": "Roadmap generado correctamente.",
        "current_score": "Puntaje actual",
        "target_score": "Puntaje objetivo",
        "actions": "Acciones",
        "email_label": "Correo",
        "email_not_sent": "No enviado",
        "download_es": "Descargar Roadmap PDF (ES)",
        "download_en": "Descargar Roadmap PDF (EN)",
        "select_company_type": "Seleccione el tipo de empresa en el panel de la izquierda para continuar.",
        "intro_title": "¿Qué es RoGen y cómo comenzar?",
        "intro_p1": "RoGen genera automáticamente una hoja de ruta personalizada para PyMEs agrícolas a partir del perfil de la empresa y las respuestas del cuestionario. Convierte los hallazgos del diagnóstico en acciones priorizadas según impacto, urgencia y horizonte temporal. La aplicación progresiva de esta ruta favorece mejoras medibles en productividad, trazabilidad, gestión de recursos, cumplimiento normativo y capacidades de digitalización.",
        "intro_p2": "Para comenzar, despliegue la barra lateral izquierda y seleccione el tamaño de empresa (Pequeña o Mediana). Complete los campos obligatorios, defina el nivel objetivo (situación futura deseada) y elija el rango de presupuesto que mejor represente su contexto. Luego responda el cuestionario según la situación actual de su empresa, no la deseada. Con esta información, RoGen prioriza acciones factibles y genera un roadmap por etapas, listo para implementar.",
        "cannot_load_profile": "No se pudo cargar el perfil",
        "roadmap_error": "No se pudo generar el roadmap",
        "language_button": "English",
        "title_company_default": "Empresa",
        "main_title": "RoGen | Generador de Roadmap Personalizado",
        "missing_company_type": "Tipo de empresa",
        "missing_company_name": "Nombre empresa",
        "missing_rut": "RUT",
        "missing_valid_rut": "RUT válido",
        "missing_email": "Correo",
        "missing_target_level": "Nivel objetivo (seleccione un nivel superior al inicial)",
        "missing_budget": "Presupuesto para mejoras",
        "missing_answers_warning": "Responde todas las preguntas antes de generar el roadmap.",
        "missing_answers_prefix": "Preguntas pendientes:",
        "smtp_missing_email": "Por favor ingresa un correo válido en Datos de la empresa (campo Correo).",
        "smtp_error_auth": "Error de autenticación SMTP. Verifica credenciales y App Password en Secrets.",
        "smtp_error_config": "Configuración SMTP incompleta o inválida en Secrets.",
        "smtp_error_network": "No fue posible conectar con el servidor SMTP. Intenta nuevamente.",
        "smtp_error_generic": "No fue posible enviar el correo automático.",
        "email_subject": "RoGen | Hoja de ruta personalizada para {company}",
        "email_body": (
            "Estimada/o representante de {company}:\n\n"
            "Junto con saludar, agradezco su participación en el estudio doctoral "
            "\"RoGen: Un marco de apoyo a la toma de decisiones, basado en la madurez, "
            "para la adopción de tecnología en pymes agrícolas\".\n\n"
            "Se adjunta la hoja de ruta personalizada de adopción tecnológica elaborada "
            "a partir de la información proporcionada durante el diagnóstico. El documento "
            "presenta los resultados de la evaluación y una secuencia de acciones priorizadas "
            "de acuerdo con el nivel de madurez, el contexto organizacional y el presupuesto seleccionado.\n\n"
            "Se espera que este material contribuya a orientar decisiones y avances graduales "
            "en el proceso de adopción tecnológica de la empresa.\n\n"
            "Para consultas relacionadas con el estudio o con el documento recibido, puede "
            "contactar a la investigadora responsable respondiendo a este correo.\n\n"
            "Atentamente,\n\n"
            "Lilianny Marrero\n"
            "Estudiante del Doctorado en Ingeniería Informática\n"
            "Universidad Técnica Federico Santa María"
        ),
        "not_sent_prefix": "No enviado",
        "sent_prefix": "Correo electrónico enviado a",
        "question_fallback": "Pregunta {qnum}",
        "friendly_label_es": "PDF amigable ES",
        "friendly_label_en": "PDF friendly EN",
        "consent_title": "Consentimiento informado",
        "consent_required": "Debe leer y aceptar el consentimiento informado para habilitar la configuración de la evaluación.",
        "consent_accept": "He leído y acepto voluntariamente el consentimiento informado.",
        "consent_download": "Descargar comprobante de consentimiento",
        "startup_error": "RoGen no pudo iniciar. Recargue la página o contacte a la investigadora responsable.",
        "email_body_with_consent": (
            "Estimada/o representante de {company}:\n\n"
            "Junto con saludar, agradezco su participación en el estudio doctoral "
            "\"RoGen: Un marco de apoyo a la toma de decisiones, basado en la madurez, "
            "para la adopción de tecnología en pymes agrícolas\".\n\n"
            "Se adjuntan la hoja de ruta personalizada de adopción tecnológica elaborada "
            "a partir de la información proporcionada durante el diagnóstico y el comprobante "
            "de consentimiento informado. La hoja de ruta presenta los resultados de la "
            "evaluación y una secuencia de acciones priorizadas de acuerdo con el nivel de "
            "madurez, el contexto organizacional y el presupuesto seleccionado.\n\n"
            "Para consultas relacionadas con el estudio o con los documentos recibidos, puede "
            "contactar a la investigadora responsable respondiendo a este correo.\n\n"
            "Atentamente,\n\n"
            "Lilianny Marrero\n"
            "Estudiante del Doctorado en Ingeniería Informática\n"
            "Universidad Técnica Federico Santa María"
        ),
    },
    "en": {
        "page_title": "Customized Roadmap Generator | Capture",
        "setup_header": "Initial Setup",
        "company_data_header": "Company Data",
        "company_type": "Company size*",
        "company_type_select": "------Select------",
        "company_small": "Small-sized enterprise",
        "company_medium": "Medium-sized enterprise",
        "company_name": "Company name*",
        "company_name_placeholder": "Enter company name",
        "rut_label": "RUT (without periods or hyphen)*",
        "email": "Email*",
        "target_level": "Target level*",
        "target_level_help_small": "1: Management relies mainly on manual tasks, simple records, and limited standardization.\n2: The company already uses digital tools in key processes, although integration is still partial.\n3: Processes are standardized, connected, and supported by data for better decision-making.",
        "target_level_help_medium": "1: Management is reactive, with low standardization, limited integration, and dependence on individual efforts.\n2: Initial formalization, operational control, and digital use exist in some areas.\n3: Areas are better coordinated, indicators are monitored, and relevant processes are integrated.\n4: Management is integrated, traceable, and oriented toward continuous improvement through technology and data.",
        "improvement_budget": "Improvement budget (1 year)*.",
        "required_note": "* Required fields",
        "invalid_rut": "Invalid RUT. Please verify the check digit.",
        "missing_required_warning": "Complete the required fields in the left panel before answering the questionnaire.",
        "missing_prefix": "Missing:",
        "questions": "Questions",
        "profile": "Profile",
        "target_level_card": "Target Level",
        "questionnaire": "Questionnaire",
        "questionnaire_instruction": "Answer according to the current situation. Select one option for each question. If the company uses practices at more than one level, choose the highest-level practice it uses regularly.",
        "answer": "Answer",
        "generate": "Generate Roadmap",
        "generating": "Generating roadmap and output files...",
        "generating_overlay_title": "Generating Roadmap",
        "generating_overlay_text": "The process may take a few seconds.",
        "generated_ok": "Roadmap generated successfully.",
        "current_score": "Current Score",
        "target_score": "Target Score",
        "actions": "Actions",
        "email_label": "Email",
        "email_not_sent": "Not sent",
        "download_es": "Download PDF Roadmap (ES)",
        "download_en": "Download PDF Roadmap (EN)",
        "select_company_type": "Select a company size to continue.",
        "intro_title": "What is RoGen and how do I get started?",
        "intro_p1": "RoGen is an automated generator of customized roadmaps that uses company characteristics and questionnaire responses as input. RoGen converts diagnostic results into a structured roadmap tailored for agricultural small and medium-sized enterprises (SMEs). The assessment process identifies maturity gaps and organizes solutions according to priority, impact, and time horizon. Progressive implementation enables measurable improvements in productivity, traceability, resource management, regulatory compliance, and digital capabilities.",
        "intro_p2": "To begin, open the left sidebar and select the company size category (Small company or Medium-sized company). Complete the required fields, choose the target level that represents the desired future state, and select the budget range that best reflects your company’s context. Respond to the questionnaire based on the current situation rather than the desired state. Based on this information, RoGen prioritizes feasible actions and generates a phased, implementable roadmap.",
        "cannot_load_profile": "Unable to load profile",
        "roadmap_error": "The roadmap could not be generated",
        "language_button": "Español",
        "title_company_default": "Company",
        "main_title": "RoGen | Customized Roadmap Generator",
        "missing_company_type": "Company size",
        "missing_company_name": "Company name",
        "missing_rut": "RUT",
        "missing_valid_rut": "Valid RUT",
        "missing_email": "Email",
        "missing_target_level": "Target level (select a level above the initial level)",
        "missing_budget": "Improvement budget",
        "missing_answers_warning": "Answer every question before generating the roadmap.",
        "missing_answers_prefix": "Unanswered questions:",
        "smtp_missing_email": "Please provide a valid email address in Company Data (Email field).",
        "smtp_error_auth": "SMTP authentication error. Check credentials and App Password in Secrets.",
        "smtp_error_config": "Incomplete or invalid SMTP configuration in Secrets.",
        "smtp_error_network": "Unable to connect to the SMTP server. Please try again.",
        "smtp_error_generic": "Unable to send the automated email.",
        "email_subject": "RoGen | Customized Roadmap for {company}",
        "email_body": (
            "Dear representative of {company}:\n\n"
            "Thank you for participating in the doctoral study "
            "\"RoGen: A Maturity-Based Decision Support Framework for Technology Adoption "
            "in Agricultural SMEs\".\n\n"
            "Attached is the customized technology-adoption roadmap prepared from the "
            "information provided during the assessment. The document presents the evaluation "
            "results and a sequence of prioritized actions based on the maturity level, "
            "organizational context, and selected budget.\n\n"
            "This material is intended to support informed decisions and gradual progress in "
            "the company's technology-adoption process.\n\n"
            "For questions regarding the study or the attached document, please contact the "
            "principal researcher at lilianny.marrero@gmail.com.\n\n"
            "Sincerely,\n\n"
            "Lilianny Marrero\n"
            "PhD Candidate in Computer Engineering\n"
            "Universidad Técnica Federico Santa María"
        ),
        "not_sent_prefix": "Not sent",
        "sent_prefix": "Email sent to",
        "question_fallback": "Question {qnum}",
        "friendly_label_es": "Friendly PDF ES",
        "friendly_label_en": "Friendly PDF EN",
        "consent_title": "Informed consent",
        "consent_required": "Read and accept the informed consent to enable the assessment configuration.",
        "consent_accept": "I have read and voluntarily accept the informed consent.",
        "consent_download": "Download consent record",
        "startup_error": "RoGen could not start. Please reload the page or contact the responsible researcher.",
        "email_body_with_consent": (
            "Dear representative of {company}:\n\n"
            "Thank you for participating in the doctoral study "
            "\"RoGen: A Maturity-Based Decision Support Framework for Technology Adoption "
            "in Agricultural SMEs\".\n\n"
            "Attached are the customized technology-adoption roadmap prepared from the "
            "information provided during the assessment and the informed-consent record. "
            "The roadmap presents the evaluation results and a sequence of prioritized "
            "actions based on the maturity level, organizational context, and selected budget.\n\n"
            "For questions regarding the study or the attached documents, please contact the "
            "principal researcher at lilianny.marrero@gmail.com.\n\n"
            "Sincerely,\n\n"
            "Lilianny Marrero\n"
            "PhD Candidate in Computer Engineering\n"
            "Universidad Técnica Federico Santa María"
        ),
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


def _budget_options(company_type: str) -> list[str]:
    key = "small" if str(company_type).strip().lower() == "small" else "medium"
    return BUDGET_OPTIONS_BY_COMPANY[key]


def _budget_radio_label(value: object, labels: dict[str, str]) -> str:
    return str(labels.get(str(value), str(value))).replace("$", r"\$")


def _target_level_help(company_type: str, language: str) -> str:
    ctype = str(company_type).strip().lower()
    if ctype == "small":
        return _t(language, "target_level_help_small").replace("\n", "\n\n")
    if ctype == "medium":
        return _t(language, "target_level_help_medium").replace("\n", "\n\n")
    return ""


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
    target_label = "English" if target == "en" else "Espa\u00f1ol"
    target_code = "EN" if target == "en" else "ES"
    flag_path = FLAG_EN_PATH if current == "es" else FLAG_ES_PATH
    data_url = _img_data_url(str(flag_path))
    if not data_url:
        if st.button(target_label, key="lang_text_fallback", use_container_width=True):
            st.session_state["ui_language"] = target
            st.query_params["ui_lang"] = target
            st.rerun()
        return

    st.markdown(
        f"""
<div class="rogen-lang-switch notranslate" translate="no">
  <a class="rogen-lang-link" href="?ui_lang={target}" target="_self" title="{html.escape(target_label)}" aria-label="{html.escape(target_label)}">
    <img class="rogen-lang-flag" src="{data_url}" alt="{html.escape(target_label)}" />
    <span class="rogen-lang-code">{target_code}</span>
  </a>
</div>
        """,
        unsafe_allow_html=True,
    )


def _apply_no_translate_guard(language: str) -> None:
    lang = _lang(language)
    nonce = datetime.now().strftime("%Y%m%d%H%M%S%f")
    try:
        components.html(
            f"""
<script>
(function () {{
  try {{
    const doc = window.parent && window.parent.document;
    if (!doc) return;

    // Remove stale language switch nodes injected by older versions in the Streamlit header.
    doc.querySelectorAll('#rogen-header-lang-switch').forEach((el) => el.remove());

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



    const hideHeaderActions = () => {{
      const header = doc.querySelector('[data-testid="stHeader"]');
      if (!header) return;

      const toolbar = header.querySelector('[data-testid="stToolbar"]');
      if (toolbar) {{
        // The native sidebar restore control belongs to this toolbar. The
        // observer below hides only administrative Cloud actions.
        toolbar.style.pointerEvents = 'auto';
        toolbar.style.zIndex = '1';
      }}

      const nodes = header.querySelectorAll("a, button, [role='button'], div, span");
      nodes.forEach((node) => {{
        const text = (node.textContent || "").trim().toLowerCase();
        const title = ((node.getAttribute("title") || "") + " " + (node.getAttribute("aria-label") || "")).toLowerCase();
        const href = (node.getAttribute("href") || "").toLowerCase();
        const signature = `${{text}} ${{title}} ${{href}}`;
        const isSidebarControl = title.includes("sidebar") || title.includes("barra lateral") || node.closest('[data-testid="collapsedControl"]') || node.closest('[data-testid="stSidebarCollapsedControl"]');
        const isLanguageSwitch = node.closest("#rogen-header-lang-switch") || node.getAttribute("data-rogen-lang-switch") === "1";
        const isCloudAction = signature.includes("deploy") || signature.includes("fork") || signature.includes("github") || signature.includes("manage app") || signature.includes("share") || signature.includes("settings") || signature.includes("analytics") || signature.includes("reboot app") || signature.includes("delete app");
        if (isLanguageSwitch) {{
          node.style.display = "";
          node.style.pointerEvents = "auto";
          return;
        }}
        if (isSidebarControl) {{
          const target = node.closest('[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], button, [role="button"]') || node;
          target.style.display = "flex";
          target.style.visibility = "visible";
          target.style.opacity = "1";
          target.style.pointerEvents = "auto";
          return;
        }}
        if (!isSidebarControl && isCloudAction) {{
          const target = node.closest("a, button, [role='button']") || node;
          target.style.display = "none";
          target.style.visibility = "hidden";
          target.style.pointerEvents = "none";
        }}
      }});
    }};
    hideHeaderActions();
    setTimeout(hideHeaderActions, 40);
    setTimeout(hideHeaderActions, 160);
    setTimeout(hideHeaderActions, 500);
    setTimeout(hideHeaderActions, 1200);

    const hideCloudProfileBadge = () => {{
      const styleId = "rogen-hide-cloud-profile-badge";
      let style = doc.getElementById(styleId);
      if (!style) {{
        style = doc.createElement("style");
        style.id = styleId;
        doc.head.appendChild(style);
      }}
      style.textContent = `
        [data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"],
        [data-testid="stMainMenu"],
        [class*="viewerBadge" i],
        [class*="viewer-badge" i],
        [class*="profileBadge" i],
        [data-testid*="viewerbadge" i],
        [data-testid*="viewer-badge" i] {{
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
        }}
      `;

      doc.querySelectorAll('a[href*="streamlit.io"], a[href*="streamlit.app"]').forEach((link) => {{
        if (!link.querySelector("img")) return;
        const rect = link.getBoundingClientRect();
        const viewportWidth = doc.documentElement.clientWidth;
        const viewportHeight = doc.documentElement.clientHeight;
        const isLowerRight = rect.right >= viewportWidth - 280 && rect.bottom >= viewportHeight - 180;
        if (!isLowerRight) return;

        const parent = link.parentElement;
        const parentRect = parent ? parent.getBoundingClientRect() : null;
        const target = parentRect && parentRect.width <= 360 && parentRect.height <= 160 ? parent : link;
        target.style.setProperty("display", "none", "important");
        target.style.setProperty("visibility", "hidden", "important");
        target.style.setProperty("pointer-events", "none", "important");
      }});
    }};
    hideCloudProfileBadge();
    setTimeout(hideCloudProfileBadge, 80);
    setTimeout(hideCloudProfileBadge, 400);
    setTimeout(hideCloudProfileBadge, 1200);

    const headerForObserver = doc.querySelector('[data-testid="stHeader"]');
    if (headerForObserver && !headerForObserver.dataset.rogenHeaderObserver) {{
      headerForObserver.dataset.rogenHeaderObserver = "1";
      const observer = new MutationObserver(() => hideHeaderActions());
      observer.observe(headerForObserver, {{ childList: true, subtree: true, attributes: true }});
    }}

    if (doc.body && !doc.body.dataset.rogenProfileBadgeObserver) {{
      doc.body.dataset.rogenProfileBadgeObserver = "1";
      const profileBadgeObserver = new MutationObserver(() => hideCloudProfileBadge());
      profileBadgeObserver.observe(doc.body, {{ childList: true, subtree: true }});
    }}

    doc.querySelectorAll('input[aria-label^="RUT"], input[placeholder*="123456785"]').forEach((el) => {{
      el.setAttribute("translate", "no");
      el.classList.add("notranslate");
    }});

    doc.querySelectorAll("label, span, p, div").forEach((el) => {{
      const txt = (el.textContent || "").trim().toUpperCase();
      if (txt.startsWith("RUT")) {{
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
    except Exception:
        # This is a cosmetic browser guard; it must never prevent the assessment UI from rendering.
        return


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


def _catalog_cache_version() -> str:
    try:
        stat = CATALOG_PATH.stat()
    except OSError:
        return "catalog-missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


@st.cache_data(show_spinner=False)
def _load_profile_cached(root: str, company_type: str, language: str, catalog_cache_version: str) -> dict[str, object]:
    _ = catalog_cache_version  # Invalidate Streamlit cache when the catalog file changes.
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

.rogen-loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000004;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(22, 34, 28, 0.34);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.rogen-loading-card {
  width: min(92vw, 540px);
  border-radius: 14px;
  border: 1px solid rgba(201, 216, 191, 0.45);
  background: #ffffff;
  box-shadow: 0 20px 46px rgba(9, 25, 17, 0.34);
  padding: 1.08rem 1rem 0.98rem;
  text-align: center;
}

.rogen-loading-spinner {
  width: 44px;
  height: 44px;
  margin: 0 auto 0.75rem;
  border-radius: 50%;
  border: 4px solid rgba(47, 109, 60, 0.20);
  border-top-color: #2f6d3c;
  animation: rogen-spin 0.9s linear infinite;
}

.rogen-loading-title {
  font-family: "Bitter", serif;
  color: #1f4f2f;
  font-size: 1.18rem;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 0.36rem;
}

.rogen-loading-text {
  color: #294436;
  font-size: 0.96rem;
  font-weight: 600;
  line-height: 1.42;
  text-wrap: balance;
}

@keyframes rogen-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.notranslate, [translate="no"] {
  -webkit-user-select: text;
}

[data-testid="stAppViewContainer"] {
  background: #f5f8f5;
}

[data-testid="stHeader"] {
  background: #123f32 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.14);
}

/* Oculta por completo el bloque de acciones Cloud (Fork/GitHub/menú). */
[data-testid="stHeader"] [data-testid="stToolbar"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  z-index: 1 !important;
}

[data-testid="stHeader"] [data-testid="stToolbar"] * {
  pointer-events: auto !important;
}

#rogen-header-lang-switch,
#rogen-header-lang-switch *,
#rogen-header-lang-switch [data-rogen-lang-switch="1"] {
  pointer-events: auto !important;
  visibility: visible !important;
  opacity: 1 !important;
}

.rogen-lang-switch {
  position: fixed;
  top: 0.56rem;
  right: 0.86rem;
  z-index: 1205;
  display: inline-flex;
  align-items: center;
}

.rogen-lang-form {
  margin: 0;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.20rem;
}

.rogen-lang-button {
  display: inline-flex;
  width: 22px;
  height: 14px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(31, 79, 47, 0.35);
  border-radius: 2px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
}

.rogen-lang-flag {
  display: block;
  width: 22px;
  height: 14px;
  object-fit: cover;
}

.rogen-lang-code {
  font-size: 0.64rem !important;
}

/* Oculta acciones de cabecera de Streamlit Cloud (Fork / GitHub / menú de tres puntos)
   sin afectar el botón de restaurar/contraer barra lateral. */
[data-testid="stHeader"] button[aria-label*="Deploy"],
[data-testid="stHeader"] button[title*="Deploy"],
[data-testid="stHeader"] a[aria-label*="Deploy"],
[data-testid="stHeader"] a[title*="Deploy"],
[data-testid="stHeader"] button[aria-label*="Fork"],
[data-testid="stHeader"] button[title*="Fork"],
[data-testid="stHeader"] a[aria-label*="Fork"],
[data-testid="stHeader"] a[title*="Fork"],
[data-testid="stHeader"] button[aria-label*="GitHub"],
[data-testid="stHeader"] button[title*="GitHub"],
[data-testid="stHeader"] a[aria-label*="GitHub"],
[data-testid="stHeader"] a[title*="GitHub"],
[data-testid="stHeader"] button[aria-label*="More"],
[data-testid="stHeader"] button[title*="More"],
[data-testid="stHeader"] button[aria-label*="más"],
[data-testid="stHeader"] button[title*="más"],
[data-testid="stHeader"] button[aria-label*="menu"],
[data-testid="stHeader"] button[title*="menu"],
[data-testid="stHeader"] button[aria-label*="menú"],
[data-testid="stHeader"] button[title*="menú"] {
  display: none !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"] {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  z-index: 1400 !important;
  width: 44px !important;
  height: 40px !important;
  align-items: center !important;
  justify-content: center !important;
  pointer-events: auto !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"] *,
[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"] * {
  pointer-events: auto !important;
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
  background: #164b39 !important;
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
  padding-top: 1.35rem;
  padding-left: 2.25rem;
  padding-right: 2.25rem;
  padding-bottom: calc(7rem + env(safe-area-inset-bottom, 0px));
}

h1, h2, h3 {
  font-family: "Bitter", serif;
  letter-spacing: 0.2px;
  color: var(--agri-leaf-900);
}

/* Oculta el icono/enlace de ancla que Streamlit agrega a los títulos. */
[data-testid="stHeadingWithActionElements"] a,
[data-testid="stHeading"] a {
  display: none !important;
  visibility: hidden !important;
}

.app-card {
  background: #ffffff;
  border: 1px solid #d8e2d9;
  border-top: 4px solid #2f6d3c;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(26, 56, 43, 0.08);
  padding: 16px 18px;
  margin-bottom: 14px;
}

.app-tip {
  background: #eff6ed;
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

.app-intro {
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
  margin-top: 0.62rem;
  margin-bottom: 0.92rem;
  width: 100%;
  max-width: none;
  box-sizing: border-box;
}

.app-intro-title {
  margin: 0 0 0.42rem 0;
}

.app-intro p {
  margin: 0 0 0.52rem 0;
  text-align: justify;
  text-align-last: left;
  hyphens: auto;
}

.app-intro p:last-child {
  margin-bottom: 0;
}

.app-intro--academic .app-intro-title {
  color: #1f3a2e;
  font-family: "Bitter", serif;
  font-size: 1.22rem;
  font-weight: 700;
  line-height: 1.28;
  letter-spacing: 0.012em;
}

.app-intro--academic p {
  color: #2f4539;
  font-family: "Source Sans 3", sans-serif;
  font-size: 0.97rem;
  font-weight: 400;
  line-height: 1.58;
  letter-spacing: 0.003em;
}

.app-warn {
  background: #fff8e8;
  border: 1px solid rgba(138, 103, 68, 0.38);
  border-left: 5px solid #8a6744;
  border-radius: 10px;
  color: #3b2f24 !important;
  font-family: "Source Sans 3", sans-serif;
  font-size: 1.00rem;
  font-weight: 700;
  line-height: 1.38;
  padding: 0.82rem 0.96rem;
  margin-bottom: 0.62rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.app-warn-meta {
  display: block;
  margin-top: 0.28rem;
  font-size: 0.92rem;
  font-weight: 700;
  color: #4a3a2d !important;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.app-warn, .app-warn * {
  color: #3b2f24 !important;
  text-shadow: none !important;
}

.app-status {
  border-radius: 10px;
  padding: 0.78rem 0.92rem;
  margin-top: 0.48rem;
  margin-bottom: 0.2rem;
  font-family: "Source Sans 3", sans-serif;
  line-height: 1.34;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.app-status-ok {
  background: #edf8ed;
  border: 1px solid rgba(47, 109, 60, 0.34);
  border-left: 5px solid #2f6d3c;
  color: #234730 !important;
}

.app-status-warn {
  background: #fff8e8;
  border: 1px solid rgba(138, 103, 68, 0.36);
  border-left: 5px solid #8a6744;
  color: #3b2f24 !important;
}

.app-status-title {
  font-size: 0.96rem;
  font-weight: 800;
  margin-right: 0.18rem;
}

.app-status-text {
  font-size: 0.92rem;
  font-weight: 700;
}

.app-status, .app-status * {
  text-shadow: none !important;
}

@media (max-width: 900px) {
  .block-container {
    padding-top: 1.65rem;
    padding-bottom: calc(8.3rem + env(safe-area-inset-bottom, 0px));
  }

  h1 {
    font-size: 2rem !important;
    line-height: 1.18 !important;
  }

  .summary-card {
    min-height: 88px;
    padding: 12px 14px;
  }

  .summary-value {
    font-size: 1.75rem;
  }

  .summary-value-text {
    font-size: 1.24rem;
  }

  .app-tip,
  .app-warn,
  .app-status {
    font-size: 0.95rem;
    padding: 0.74rem 0.82rem;
    line-height: 1.36;
  }

  .app-intro--academic .app-intro-title {
    font-size: 1.12rem;
    line-height: 1.25;
    margin-bottom: 0.34rem;
  }

  .app-intro--academic p {
    font-size: 0.93rem;
    line-height: 1.52;
    margin-bottom: 0.43rem;
  }

  .app-warn-meta,
  .app-status-text {
    font-size: 0.86rem;
  }
}

@media (max-width: 560px) {
  h1 {
    font-size: 1.72rem !important;
    line-height: 1.16 !important;
  }

  .block-container {
    padding-bottom: calc(9.2rem + env(safe-area-inset-bottom, 0px));
  }

  .rogen-lang-switch {
    top: 0.62rem;
    right: 0.68rem;
  }

  .rogen-loading-card {
    width: min(94vw, 360px);
    border-radius: 12px;
    padding: 0.90rem 0.82rem 0.82rem;
  }

  .rogen-loading-spinner {
    width: 36px;
    height: 36px;
    border-width: 3.5px;
    margin-bottom: 0.58rem;
  }

  .rogen-loading-title {
    font-size: 1.02rem;
  }

  .rogen-loading-text {
    font-size: 0.88rem;
    line-height: 1.34;
  }

  .summary-value {
    font-size: 1.62rem;
  }

  .summary-value-text {
    font-size: 1.14rem;
  }

  .app-tip,
  .app-warn,
  .app-status {
    border-left-width: 4px;
    border-radius: 9px;
  }

  .app-intro--academic .app-intro-title {
    font-size: 1.01rem;
    line-height: 1.24;
    margin-bottom: 0.28rem;
  }

  .app-intro--academic p {
    font-size: 0.86rem;
    line-height: 1.44;
    margin-bottom: 0.34rem;
  }

  .st-key-generate_action_bar {
    bottom: calc(0.4rem + env(safe-area-inset-bottom, 0px));
    padding-top: 0.42rem;
    padding-bottom: 0.42rem;
    margin-top: 0.6rem;
  }

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
  border-radius: 7px;
  background: #176b4d;
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

.st-key-generate_action_bar {
  position: sticky;
  bottom: calc(0.6rem + env(safe-area-inset-bottom, 0px));
  z-index: 80;
  padding-top: 0.5rem;
  padding-bottom: 0.48rem;
  margin-top: 0.72rem;
  background: rgba(245, 248, 245, 0.96);
  border-top: 1px solid rgba(111, 143, 78, 0.25);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}

.st-key-generate_action_bar [data-testid="stButton"] > button {
  margin-bottom: 0 !important;
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

/* Keep every budget-range label legible and numerically consistent. */
[class*="st-key-budget_total_"] label,
[class*="st-key-budget_total_"] label p,
[class*="st-key-budget_total_"] label span,
[class*="st-key-budget_total_"] label div {
  font-size: 0.94rem !important;
  line-height: 1.35 !important;
  font-variant-numeric: tabular-nums !important;
  font-feature-settings: "tnum" 1, "lnum" 1 !important;
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
  background: rgba(47, 109, 60, 0.45) !important;
}

[data-testid="stSlider"] div[data-baseweb="slider"] > div[data-testid="stTickBar"] {
  background: rgba(111, 143, 78, 0.28) !important;
}

[data-testid="stSidebar"]:has(.rogen-level-slider-marker) [data-testid="stSliderTickBar"] {
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
  visibility: hidden !important;
}

[data-testid="stSidebar"]:has(.rogen-level-slider-marker) [data-testid="stSliderTickBar"] * {
  color: transparent !important;
  -webkit-text-fill-color: transparent !important;
}

.rogen-level-slider-marker {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: space-between !important;
  width: 100% !important;
  max-width: var(--rogen-sidebar-field-width) !important;
  margin: -0.95rem auto 0.30rem auto !important;
  padding: 0 !important;
  overflow: visible !important;
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-size: 0.86rem !important;
  font-weight: 700 !important;
  line-height: 1.1 !important;
}

.rogen-level-slider-marker span {
  display: inline-block !important;
  min-width: 0.7rem !important;
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  text-align: center !important;
}

.rogen-level-slider-marker span:first-child {
  text-align: left !important;
}

.rogen-level-slider-marker span:last-child {
  text-align: right !important;
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
  color: #f7f3e8 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-size: 0.82rem;
  font-weight: 600;
  margin-top: 0.2rem;
}

/* Keep Cloud actions hidden while preserving Streamlit's native sidebar controls. */
[data-testid="stHeader"] [data-testid="stToolbar"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

[data-testid="stSidebar"] [data-testid="stTooltipIcon"],
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] *,
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg,
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg path {
  color: #f7f3e8 !important;
  fill: #f7f3e8 !important;
  stroke: #f7f3e8 !important;
}

[data-baseweb="tooltip"],
[data-baseweb="tooltip"] * {
  white-space: pre-line !important;
}

/* The configuration panel can be collapsed and restored by the visitor. */
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

[data-testid="stHeader"] [data-testid="stToolbar"] [data-testid="collapsedControl"],
[data-testid="stHeader"] [data-testid="stToolbar"] [data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

.rogen-lang-switch {
  position: fixed !important;
  top: 0.56rem !important;
  right: 0.86rem !important;
  z-index: 1000010 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  pointer-events: auto !important;
  visibility: visible !important;
  opacity: 1 !important;
}

.rogen-lang-link {
  display: inline-flex !important;
  width: auto !important;
  height: 24px !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.18rem !important;
  padding: 0 0.18rem !important;
  margin: 0 !important;
  border: 0 !important;
  border-radius: 3px !important;
  background: transparent !important;
  text-decoration: none !important;
  cursor: pointer !important;
  pointer-events: auto !important;
}

.rogen-lang-link:hover {
  background: rgba(25, 83, 56, 0.18) !important;
}

.rogen-lang-link .rogen-lang-flag {
  width: 22px !important;
  height: 14px !important;
  object-fit: cover !important;
  display: block !important;
  border: 1px solid rgba(31, 79, 47, 0.28) !important;
  border-radius: 2px !important;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12) !important;
}

.rogen-lang-link .rogen-lang-code {
  color: #f7f3e8 !important;
  -webkit-text-fill-color: #f7f3e8 !important;
  font-family: "Source Sans 3", sans-serif !important;
  font-size: 0.68rem !important;
  font-weight: 800 !important;
  line-height: 1 !important;
}

@media (max-width: 560px) {
  .rogen-lang-switch {
    top: 0.62rem !important;
    right: 0.68rem !important;
  }
}


/* Keep the configuration panel comfortably readable and collapsible. */
:root {
  --rogen-sidebar-width: 300px;
  --rogen-sidebar-field-width: 264px;
  --rogen-sidebar-pad-x: 18px;
}

html {
  font-size: 14px;
}

[data-testid="stSidebar"][aria-expanded="true"],
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
  width: var(--rogen-sidebar-width) !important;
  min-width: var(--rogen-sidebar-width) !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  box-sizing: border-box !important;
  padding-left: var(--rogen-sidebar-pad-x) !important;
  padding-right: var(--rogen-sidebar-pad-x) !important;
  overflow-x: hidden !important;
}

[data-testid="stSidebar"] [data-testid="stElementContainer"],
[data-testid="stSidebar"] [data-testid="stTextInput"],
[data-testid="stSidebar"] [data-testid="stSelectbox"],
[data-testid="stSidebar"] [data-testid="stRadio"],
[data-testid="stSidebar"] [data-testid="stSlider"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
  box-sizing: border-box !important;
  width: 100% !important;
  max-width: var(--rogen-sidebar-field-width) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

[data-testid="stSidebar"] [data-testid="stTextInput"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-testid="stRadio"] > div,
[data-testid="stSidebar"] [data-testid="stSlider"] > div {
  box-sizing: border-box !important;
  width: 100% !important;
  max-width: 100% !important;
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .sidebar-field-label,
[data-testid="stSidebar"] .sidebar-required-note {
  width: 100% !important;
  max-width: var(--rogen-sidebar-field-width) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

[data-testid="stSidebar"] hr {
  width: 100% !important;
  max-width: var(--rogen-sidebar-field-width) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

[data-testid="stHeader"] [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  z-index: 1000012 !important;
}

@media (max-width: 760px) {
  :root {
    --rogen-sidebar-width: 280px;
    --rogen-sidebar-field-width: 244px;
    --rogen-sidebar-pad-x: 16px;
  }

  .block-container {
    padding-left: 1.1rem;
    padding-right: 1.1rem;
  }
}

.app-title-band {
  display: flex;
  align-items: center;
  min-height: 76px;
  margin: 0 0 0.9rem;
  padding: 0.85rem 1rem;
  background: #ffffff;
  border: 1px solid #d8e2d9;
  border-left: 6px solid #2f6f8f;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(26, 56, 43, 0.08);
}

.app-title-band h1 {
  margin: 0;
  color: #173d31;
  font-family: "Bitter", serif;
  font-size: 1.7rem;
  font-weight: 800;
  line-height: 1.16;
}

[class*="st-key-question_card_"] {
  margin: 0.75rem 0 !important;
  padding: 1rem 1.1rem 0.9rem !important;
  background: #ffffff;
  border: 1px solid #d8e2d9;
  border-radius: 8px;
  box-shadow: 0 3px 10px rgba(26, 56, 43, 0.06);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

[class*="st-key-question_card_"]:hover {
  border-color: #8fb2a0;
  box-shadow: 0 7px 16px rgba(26, 56, 43, 0.10);
}

[class*="st-key-question_card_"] .question-label {
  margin-top: 0;
  color: #176b4d;
}

[class*="st-key-question_card_"] [data-testid="stRadio"] > div {
  background: #f6faf6;
  border-color: #d8e2d9;
}

</style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(profile: dict[str, object], max_level: int, language: str, company_type: str) -> dict[str, object]:
    budget_labels = _budget_labels(language)
    budget_options = _budget_options(company_type)
    st.sidebar.header(_t(language, "company_data_header"))
    company_name = st.sidebar.text_input(_t(language, "company_name"), value="", placeholder=_t(language, "company_name_placeholder"))
    if RUT_WIDGET_KEY not in st.session_state:
        st.session_state[RUT_WIDGET_KEY] = ""
    company_rut = st.sidebar.text_input(
        _t(language, "rut_label"),
        key=RUT_WIDGET_KEY,
        placeholder="123456785",
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
    target_level = st.sidebar.slider(
        _t(language, "target_level"),
        min_value=1,
        max_value=max_level,
        value=1,
        step=1,
        key=f"target_level_{company_type}",
        help=_target_level_help(company_type, language),
    )
    level_markers = "".join(f"<span>{level}</span>" for level in range(1, max_level + 1))
    st.sidebar.markdown(
        f'<div class="rogen-level-slider-marker" aria-hidden="true">{level_markers}</div>',
        unsafe_allow_html=True,
    )
    budget_total_key = st.sidebar.radio(
        _t(language, "improvement_budget"),
        options=budget_options,
        index=None,
        format_func=lambda key: _budget_radio_label(key, budget_labels),
        key=f"budget_total_{company_type}",
    )
    st.sidebar.markdown(f"<div class='sidebar-required-note'>{html.escape(_t(language, 'required_note'))}</div>", unsafe_allow_html=True)

    if str(company_type).strip().lower() == "small":
        localized_profile_label = _t(language, "company_small")
    elif str(company_type).strip().lower() == "medium":
        localized_profile_label = _t(language, "company_medium")
    else:
        localized_profile_label = str(profile.get("label", ""))

    return {
        "company_name": company_name,
        "company_rut": company_rut,
        "company_email": company_email,
        "target_level": target_level,
        "budget_total_label": budget_labels.get(str(budget_total_key), ""),
        "budget_total_clp": BUDGET_TO_CLP.get(str(budget_total_key)),
        "budget_range": str(budget_total_key or ""),
        "profile_label": localized_profile_label,
    }


def _collect_answers(company_type: str, questions: list[dict[str, Any]]) -> dict[int, int]:
    answers: dict[int, int] = {}
    for q in questions:
        qnum = int(q["number"])
        key = f"q_{company_type}_{qnum}"
        selected = st.session_state.get(key)
        if selected is not None:
            answers[qnum] = int(selected) + 1
    return answers


def _missing_question_numbers(company_type: str, questions: list[dict[str, Any]]) -> list[int]:
    return [
        int(question["number"])
        for question in questions
        if st.session_state.get(f"q_{company_type}_{int(question['number'])}") is None
    ]


def _build_overrides(ui_cfg: dict[str, object]) -> dict[str, Any]:
    budget_total = ui_cfg.get("budget_total_clp")
    return {
        "budget_total_clp": float(budget_total) if budget_total is not None else None,
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
    if int(ui_cfg.get("target_level", 1) or 1) <= 1:
        missing.append(_t(language, "missing_target_level"))
    if not str(ui_cfg.get("budget_range", "")).strip():
        missing.append(_t(language, "missing_budget"))
    return missing


def _clean_prompt(prompt: str, qnum: int, language: str) -> str:
    text = str(prompt or "").strip()
    text = re.sub(rf"^\s*(?:pregunta|question)\s*{qnum}\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:pregunta|question)\s*\d+\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    return text or _t(language, "question_fallback", qnum=qnum)


def _read_streamlit_secret_value(*keys: str) -> str:
    try:
        secrets = st.secrets
    except Exception:
        return ""

    candidate_maps: list[object] = [secrets]
    for section in ("smtp", "roadmap", "roadmap_smtp"):
        try:
            section_obj = secrets.get(section) if hasattr(secrets, "get") else secrets[section]
        except Exception:
            section_obj = None
        if section_obj is not None:
            candidate_maps.append(section_obj)

    for mapping in candidate_maps:
        for key in keys:
            try:
                value = mapping.get(key) if hasattr(mapping, "get") else mapping[key]
            except Exception:
                value = None
            if value is None:
                continue
            txt = str(value).strip()
            if txt:
                return txt
    return ""


def _parse_secret_bool(value: str, *, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _merge_smtp_config_from_streamlit_secrets(cfg: object) -> object:
    try:
        cfg.require_smtp = _parse_secret_bool(
            _read_streamlit_secret_value(
                ENV_KEYS["require_smtp"],
                "require_smtp",
                "ROADMAP_REQUIRE_SMTP",
            ),
            default=getattr(cfg, "require_smtp", False),
        )

        host = _read_streamlit_secret_value(ENV_KEYS["smtp_host"], "smtp_host", "ROADMAP_SMTP_HOST", "host")
        if host:
            cfg.smtp_host = host

        port_txt = _read_streamlit_secret_value(ENV_KEYS["smtp_port"], "smtp_port", "ROADMAP_SMTP_PORT", "port")
        if port_txt:
            try:
                cfg.smtp_port = int(str(port_txt).strip())
            except ValueError:
                pass

        user = _read_streamlit_secret_value(ENV_KEYS["smtp_user"], "smtp_user", "ROADMAP_SMTP_USER", "user")
        if user:
            cfg.smtp_user = user

        password = _read_streamlit_secret_value(ENV_KEYS["smtp_password"], "smtp_password", "ROADMAP_SMTP_PASSWORD", "password")
        if password:
            cfg.smtp_password = password

        sender = _read_streamlit_secret_value(ENV_KEYS["smtp_from"], "smtp_from", "ROADMAP_SMTP_FROM", "from")
        if sender:
            cfg.smtp_from = sender

        smtp_to = _read_streamlit_secret_value(ENV_KEYS["smtp_to"], "smtp_to", "ROADMAP_SMTP_TO", "to")
        if smtp_to:
            cfg.smtp_to = smtp_to
    except Exception:
        # Never fail roadmap generation due to optional secret lookup.
        pass
    return cfg


def _safe_smtp_error_message(exc: Exception, language: str) -> str:
    if isinstance(exc, RuntimeError):
        lower = str(exc).lower()
        if "incomplete smtp configuration" in lower or "faltan variables smtp" in lower:
            return _t(language, "smtp_error_config")

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return _t(language, "smtp_error_auth")

    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError, OSError)):
        return _t(language, "smtp_error_network")

    if isinstance(exc, smtplib.SMTPException):
        return _t(language, "smtp_error_generic")

    return _t(language, "smtp_error_generic")


def _send_pdfs_via_gmail(
    *,
    root: Path,
    company_name: str,
    company_email: str,
    pdf_paths: list[Path],
    language: str,
    include_consent: bool = False,
) -> list[str]:
    cfg, _ = load_security_config(root)
    cfg = _merge_smtp_config_from_streamlit_secrets(cfg)
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
    body_key = "email_body_with_consent" if include_consent else "email_body"
    msg.set_content(_t(language, body_key, company=company_name))

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
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg.smtp_user, cfg.smtp_password)
        smtp.send_message(msg)
    return targets


def _stats_recipient_from_config(cfg: object) -> str:
    recipient = _read_streamlit_secret_value("ROADMAP_STATS_TO", "roadmap_stats_to", "stats_to")
    if not recipient:
        recipient = os.getenv("ROADMAP_STATS_TO", "").strip()
    if not recipient:
        recipient = str(getattr(cfg, "smtp_user", "") or "").strip()
    return recipient


def _statistical_email_body(
    record: dict[str, object],
    payload: dict[str, object],
    consent_record: dict[str, object],
    language: str,
) -> str:
    company = payload.get("company", {}) if isinstance(payload.get("company"), dict) else {}
    selected_language = _lang(language)
    company_name = str(company.get("name", "")).strip() or "-"
    company_rut = str(company.get("rut", "")).strip() or "-"
    company_email = str(company.get("email", "")).strip() or "-"
    company_size = str(record.get("company_size", "")).strip()
    size_label = {
        "small": "Small-sized enterprise" if selected_language == "en" else "Pequeña empresa",
        "medium": "Medium-sized enterprise" if selected_language == "en" else "Mediana empresa",
    }.get(company_size, company_size or "-")
    budget_label = _budget_labels(selected_language).get(
        str(record.get("budget_range_code", "")),
        str(record.get("budget_range", "")) or "-",
    )
    budget_usage = to_float(record.get("budget_utilization_ratio")) * 100

    if selected_language == "en":
        return (
            "This internal message contains identifiable research data. Do not forward it outside the research team.\n\n"
            "CASE LINKAGE\n"
            f"Case ID: {record.get('case_id', '')}\n"
            f"Generated at: {format_timestamp(record.get('generated_at', ''))}\n"
            f"Company: {company_name}\n"
            f"Business RUT: {company_rut}\n"
            f"Participant email: {company_email}\n"
            f"Company size: {size_label}\n\n"
            "INFORMED CONSENT\n"
            f"Consent ID: {consent_record.get('consent_id', '')}\n"
            f"Consent version: {consent_record.get('consent_version', '')}\n"
            f"Accepted at: {format_timestamp(consent_record.get('accepted_at', ''))}\n\n"
            "ASSESSMENT SUMMARY\n"
            f"Questionnaire version: {record.get('questionnaire_instrument_version', '')}\n"
            f"Global target level: {format_integer(record.get('global_target_level', 0))}\n"
            f"Current maturity score: {format_decimal(record.get('current_maturity_score', 0))}\n"
            f"Target maturity score: {format_decimal(record.get('target_maturity_score', 0))}\n"
            f"Maturity gap: {format_decimal(record.get('maturity_gap', 0))}\n"
            f"KPIs assessed: {format_integer(record.get('questionnaire_kpis_total', 0))}\n"
            f"KPIs with gap: {format_integer(record.get('kpis_with_gap', 0))}\n"
            f"KPIs at or above target: {format_integer(record.get('kpis_at_or_above_target', 0))}\n\n"
            "ROADMAP SUMMARY\n"
            f"Selected budget range: {budget_label}\n"
            f"Budget cap: {format_clp(record.get('budget_cap_clp'), 'Not available')}\n"
            f"Budget used: {format_clp(record.get('engine_used_budget_clp'), 'Not available')} ({format_decimal(budget_usage)}%)\n"
            f"Budget remaining: {format_clp(record.get('budget_remaining_clp'), 'Not available')}\n"
            f"Selected recommendations: {format_integer(record.get('recommendations_total', 0))}\n"
            f"Short / medium / long term: {format_integer(record.get('short_term_count', 0))} / {format_integer(record.get('medium_term_count', 0))} / {format_integer(record.get('long_term_count', 0))}\n"
            f"Required / covered transitions: {format_integer(record.get('required_transitions_total', 0))} / {format_integer(record.get('covered_transitions_total', 0))}\n"
            f"Recommendation engine version: {record.get('engine_version', '')}\n"
            f"Catalog version: {record.get('catalog_schema_version', '')}\n\n"
            "Attached files: pseudonymized statistical summary, KPI detail, and the variable guide."
        )

    return (
        "Este correo interno contiene datos identificables de investigación. No debe reenviarse fuera del equipo investigador.\n\n"
        "VINCULACIÓN DEL CASO\n"
        f"ID de caso: {record.get('case_id', '')}\n"
        f"Generado el: {format_timestamp(record.get('generated_at', ''))}\n"
        f"Empresa: {company_name}\n"
        f"RUT empresa: {company_rut}\n"
        f"Correo de participante: {company_email}\n"
        f"Tamaño de empresa: {size_label}\n\n"
        "CONSENTIMIENTO INFORMADO\n"
        f"ID de consentimiento: {consent_record.get('consent_id', '')}\n"
        f"Versión de consentimiento: {consent_record.get('consent_version', '')}\n"
        f"Aceptado el: {format_timestamp(consent_record.get('accepted_at', ''))}\n\n"
        "RESUMEN DE LA EVALUACIÓN\n"
        f"Versión del cuestionario: {record.get('questionnaire_instrument_version', '')}\n"
        f"Nivel objetivo global: {format_integer(record.get('global_target_level', 0))}\n"
        f"Puntaje de madurez actual: {format_decimal(record.get('current_maturity_score', 0))}\n"
        f"Puntaje de madurez objetivo: {format_decimal(record.get('target_maturity_score', 0))}\n"
        f"Brecha de madurez: {format_decimal(record.get('maturity_gap', 0))}\n"
        f"KPI evaluados: {format_integer(record.get('questionnaire_kpis_total', 0))}\n"
        f"KPI con brecha: {format_integer(record.get('kpis_with_gap', 0))}\n"
        f"KPI en o sobre la meta: {format_integer(record.get('kpis_at_or_above_target', 0))}\n\n"
        "RESUMEN DEL ROADMAP\n"
        f"Rango de presupuesto seleccionado: {budget_label}\n"
        f"Tope de presupuesto: {format_clp(record.get('budget_cap_clp'), 'No disponible')}\n"
        f"Presupuesto usado: {format_clp(record.get('engine_used_budget_clp'), 'No disponible')} ({format_decimal(budget_usage)}%)\n"
        f"Presupuesto remanente: {format_clp(record.get('budget_remaining_clp'), 'No disponible')}\n"
        f"Recomendaciones seleccionadas: {format_integer(record.get('recommendations_total', 0))}\n"
        f"Acciones corto / mediano / largo plazo: {format_integer(record.get('short_term_count', 0))} / {format_integer(record.get('medium_term_count', 0))} / {format_integer(record.get('long_term_count', 0))}\n"
        f"Transiciones requeridas / cubiertas: {format_integer(record.get('required_transitions_total', 0))} / {format_integer(record.get('covered_transitions_total', 0))}\n"
        f"Versión del motor de recomendaciones: {record.get('engine_version', '')}\n"
        f"Versión del catálogo: {record.get('catalog_schema_version', '')}\n\n"
        "Se adjuntan el resumen estadístico seudonimizado, el detalle por KPI y la guía de variables."
    )


def _send_statistical_csv_via_gmail(
    *,
    root: Path,
    record: dict[str, object],
    payload: dict[str, object],
    consent_record: dict[str, object],
    summary_csv_bytes: bytes,
    kpi_csv_bytes: bytes,
    guide_csv_bytes: bytes,
    language: str,
) -> str:
    cfg, _ = load_security_config(root)
    cfg = _merge_smtp_config_from_streamlit_secrets(cfg)
    if not cfg.smtp_host:
        cfg.smtp_host = "smtp.gmail.com"
    if cfg.smtp_port <= 0:
        cfg.smtp_port = 587

    errors = validate_smtp_config(cfg, strict=True)
    if errors:
        raise RuntimeError("Incomplete SMTP configuration: " + " | ".join(errors))

    recipient = _stats_recipient_from_config(cfg)
    if not recipient:
        raise RuntimeError("Missing ROADMAP_STATS_TO or ROADMAP_SMTP_USER for internal statistical export.")

    case_id = str(record.get("case_id", "rogen_case")).strip() or "rogen_case"
    company = payload.get("company", {}) if isinstance(payload.get("company"), dict) else {}
    company_name = str(company.get("name", "")).strip() or case_id
    msg = EmailMessage()
    subject_prefix = "RoGen | Statistical records" if _lang(language) == "en" else "RoGen | Registros estadísticos"
    msg["Subject"] = f"{subject_prefix} | {company_name} | {case_id}"
    msg["From"] = cfg.smtp_from
    msg["To"] = recipient
    msg.set_content(_statistical_email_body(record, payload, consent_record, language))
    msg.add_attachment(
        summary_csv_bytes,
        maintype="text",
        subtype="csv",
        filename=f"rogen_estadisticas_resumen_{case_id}.csv",
    )
    msg.add_attachment(
        kpi_csv_bytes,
        maintype="text",
        subtype="csv",
        filename=f"rogen_estadisticas_detalle_kpi_{case_id}.csv",
    )
    msg.add_attachment(
        guide_csv_bytes,
        maintype="text",
        subtype="csv",
        filename="rogen_estadisticas_guia_de_variables.csv",
    )

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg.smtp_user, cfg.smtp_password)
        smtp.send_message(msg)
    return recipient


def _render_downloads(result: dict[str, object], language: str) -> None:
    files: dict[str, str] = result.get("files", {}) if isinstance(result, dict) else {}
    pdf_es: Path | None = None
    pdf_en: Path | None = None
    consent_pdf: Path | None = None
    for path_str in files.values():
        path = Path(path_str)
        if not path.exists() or path.suffix.lower() != ".pdf":
            continue
        name_txt = path.name.lower()
        if name_txt.endswith("_es.pdf"):
            pdf_es = path
        if name_txt.endswith("_en.pdf"):
            pdf_en = path
        if name_txt.startswith("consent_"):
            consent_pdf = path

    if pdf_es is None and pdf_en is None and consent_pdf is None:
        return

    col_es, col_en, col_consent = st.columns(3)
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
    if consent_pdf is not None:
        with col_consent:
            st.download_button(
                label=_t(language, "consent_download"),
                data=consent_pdf.read_bytes(),
                file_name=consent_pdf.name,
                mime="application/pdf",
                use_container_width=True,
            )


def _score_to_float(value: object) -> float:
    return to_float(value)


def _format_score(value: object, language: str) -> str:
    _ = language
    return format_decimal(value)


def _render_last_result_summary(last: dict[str, object], language: str) -> None:
    st.success(_t(language, "generated_ok"))
    m1, m2, m3 = st.columns(3)
    m1.metric(_t(language, "current_score"), _format_score(last.get("current_score", 0), language))
    m2.metric(_t(language, "target_score"), _format_score(last.get("target_score", 0), language))
    m3.metric(_t(language, "actions"), format_integer(last.get("actions", 0)))
    status_text_raw = str(last.get("email_status", _t(language, "email_not_sent")))
    status_label = html.escape(_t(language, "email_label"))
    status_text = html.escape(status_text_raw)
    if status_text_raw.startswith(_t(language, "sent_prefix")):
        st.markdown(
            f"<div class='app-status app-status-ok'><span class='app-status-text'>{status_text}</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='app-status app-status-warn'><span class='app-status-title'>{status_label}:</span><span class='app-status-text'>{status_text}</span></div>",
            unsafe_allow_html=True,
        )


def _render_intro_block(language: str) -> None:
    with st.container(border=True):
        intro_title = html.escape(_t(language, "intro_title"))
        intro_p1 = html.escape(_t(language, "intro_p1"))
        intro_p2 = html.escape(_t(language, "intro_p2"))
        st.markdown(
            f"""
            <section class="app-intro app-intro--academic">
              <h2 class="app-intro-title">{intro_title}</h2>
              <p>{intro_p1}</p>
              <p>{intro_p2}</p>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _consent_contact_email(root: Path) -> str:
    cfg, _ = load_security_config(root)
    cfg = _merge_smtp_config_from_streamlit_secrets(cfg)
    return str(getattr(cfg, "smtp_from", "") or getattr(cfg, "smtp_user", "") or "").strip()


def _render_consent_block(language: str) -> bool:
    contact_email = _consent_contact_email(ROOT)
    with st.container(border=True):
        st.subheader(_t(language, "consent_title"))
        for section_title, paragraph in consent_sections(language, contact_email):
            st.markdown(f"**{html.escape(section_title)}**")
            st.write(paragraph)
        accepted = st.checkbox(_t(language, "consent_accept"), key="consent_accepted_checkbox")

    if not accepted:
        st.session_state.pop("consent_session", None)
        st.info(_t(language, "consent_required"))
        return False

    if "consent_session" not in st.session_state:
        accepted_at = datetime.now(ZoneInfo("America/Santiago")).isoformat(timespec="seconds")
        st.session_state["consent_session"] = {
            "consent_id": uuid.uuid4().hex,
            "accepted_at": accepted_at,
            "language": language,
            "consent_version": CONSENT_VERSION,
        }
    return True


def _render_main_title(language: str, company_type_label: str = "") -> None:
    title = _t(language, "main_title")
    if company_type_label:
        title = f"{title} | {company_type_label}"
    st.markdown(
        f"<section class='app-title-band'><h1>{html.escape(title)}</h1></section>",
        unsafe_allow_html=True,
    )


def _scroll_to_result_once() -> None:
    if not bool(st.session_state.get("scroll_to_top_result", False)):
        return
    nonce = int(st.session_state.get("scroll_to_top_nonce", 0))
    js_block = """
<script>
const smoothScrollTop = () => {
  try {
    const frame = window.parent;
    const doc = frame.document;
    const anchor = doc.getElementById("rogen-result-anchor");
    if (anchor && anchor.scrollIntoView) {
      anchor.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const targets = [
      doc.querySelector("section.main"),
      doc.querySelector(".main"),
      doc.querySelector('[data-testid="stMain"]'),
      doc.querySelector('[data-testid="stAppViewContainer"]')
    ].filter(Boolean);
    targets.forEach((el) => {
      if (anchor && el.contains(anchor)) return;
      if (el.scrollTo) el.scrollTo({ top: Math.max((el.scrollTop || 0) - 8, 0), behavior: "smooth" });
    });
    if (!anchor) frame.scrollTo({ top: 0, behavior: "smooth" });
  } catch (_) {}
};
setTimeout(smoothScrollTop, 30);
setTimeout(smoothScrollTop, 160);
setTimeout(smoothScrollTop, 360);
</script>
<div style="display:none">scroll-nonce-__NONCE__</div>
    """
    components.html(
        js_block.replace("__NONCE__", str(nonce)),
        height=0,
    )
    st.session_state["scroll_to_top_result"] = False


def _show_generation_overlay(slot: st.delta_generator.DeltaGenerator, language: str) -> None:
    title = html.escape(_t(language, "generating_overlay_title"))
    text = html.escape(_t(language, "generating_overlay_text"))
    slot.markdown(
        f"""
<div class="rogen-loading-overlay" role="status" aria-live="assertive" aria-busy="true">
  <div class="rogen-loading-card">
    <div class="rogen-loading-spinner" aria-hidden="true"></div>
    <div class="rogen-loading-title">{title}</div>
    <div class="rogen-loading-text">{text}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Generador de Roadmap Personalizado / Customized Roadmap Generator", layout="wide", initial_sidebar_state="expanded")
    _render_styles()

    if "ui_language" not in st.session_state:
        st.session_state["ui_language"] = "es"

    qp_lang = st.query_params.get("ui_lang")
    if qp_lang:
        st.session_state["ui_language"] = _lang(str(qp_lang))

    language = _lang(str(st.session_state.get("ui_language", "es")))
    _render_language_flag(language)

    st.sidebar.header(_t(language, "setup_header"))
    company_type_labels = {
        "__select__": _t(language, "company_type_select"),
        "small": _t(language, "company_small"),
        "medium": _t(language, "company_medium"),
    }
    if "consent_session" not in st.session_state:
        if _render_consent_block(language):
            # Render the accepted state from the top of the page on the next run.
            st.rerun()
        else:
            st.sidebar.selectbox(
                _t(language, "company_type"),
                options=["__select__", "small", "medium"],
                format_func=lambda x: company_type_labels.get(x, x),
                disabled=True,
            )
            st.sidebar.markdown("---")
            return

    company_type = st.sidebar.selectbox(
        _t(language, "company_type"),
        options=["__select__", "small", "medium"],
        format_func=lambda x: company_type_labels.get(x, x),
    )
    st.sidebar.markdown("---")
    selected_company_type = "" if company_type == "__select__" else company_type_labels.get(company_type, "")

    _render_main_title(language, selected_company_type)
    _render_intro_block(language)

    if company_type == "__select__":
        return

    try:
        profile = _load_profile_cached(str(ROOT), company_type, language, _catalog_cache_version())
    except Exception as exc:
        st.error(f"{_t(language, 'cannot_load_profile')} '{company_type}': {exc}")
        return

    questions: list[dict[str, Any]] = [dict(x) for x in profile.get("questions", [])]
    max_level = max((len(q.get("level_labels", [])) for q in questions), default=5)
    ui_cfg = _render_sidebar(profile, max_level=max_level, language=language, company_type=company_type)
    missing_required = _missing_required_company_fields(company_type, ui_cfg, language)
    if missing_required:
        warning_text = html.escape(_t(language, "missing_required_warning"))
        missing_text = html.escape(_t(language, "missing_prefix") + " " + ", ".join(missing_required))
        st.markdown(
            f"<div class='app-warn'>{warning_text}<span class='app-warn-meta'>{missing_text}</span></div>",
            unsafe_allow_html=True,
        )
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">{_t(language, "questions")}</div>
  <div class="summary-value">{format_integer(len(questions))}</div>
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
  <div class="summary-value">{format_integer(ui_cfg["target_level"])}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader(_t(language, "questionnaire"))
    st.caption(_t(language, "questionnaire_instruction"))
    for q in sorted(questions, key=lambda row: int(row.get("number", 0))):
        qnum = int(q["number"])
        options = [str(x) for x in q.get("options", [])]
        prompt = _clean_prompt(str(q.get("prompt", "")), qnum, language)

        with st.container(key=f"question_card_{company_type}_{qnum}"):
            st.markdown(f"<div class='question-label'>{_t(language, 'question_fallback', qnum=qnum)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='question-text'>{html.escape(prompt)}</div>", unsafe_allow_html=True)
            st.radio(
                label=f"{_t(language, 'answer')} {qnum}",
                options=list(range(len(options))),
                index=None,
                format_func=lambda i, rows=options: rows[i],
                key=f"q_{company_type}_{qnum}",
                label_visibility="collapsed",
            )

    missing_questions = _missing_question_numbers(company_type, questions)
    if missing_questions:
        question_list = ", ".join(str(number) for number in missing_questions)
        st.warning(
            f"{_t(language, 'missing_answers_warning')} "
            f"{_t(language, 'missing_answers_prefix')} {question_list}"
        )

    generate_clicked = False
    with st.container(key="generate_action_bar"):
        generate_clicked = st.button(
            _t(language, "generate"),
            type="primary",
            use_container_width=True,
            disabled=bool(missing_questions),
        )

    if generate_clicked:
        overlay_slot = st.empty()
        try:
            answers = _collect_answers(company_type, questions)
            engine_cfg = build_engine_config(None, _build_overrides(ui_cfg))
            _show_generation_overlay(overlay_slot, language)

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
                consent_session = st.session_state.get("consent_session", {})
                if not isinstance(consent_session, dict):
                    raise RuntimeError("Missing informed-consent acceptance.")
                consent_language = _lang(str(consent_session.get("language", language)))
                consent_record = build_consent_record(
                    consent_id=str(consent_session.get("consent_id", "")),
                    language=consent_language,
                    accepted_at=str(consent_session.get("accepted_at", "")),
                    participant_email=str(ui_cfg["company_email"]),
                    company_name=str(ui_cfg["company_name"]),
                    company_rut=str(ui_cfg["company_rut"]),
                    contact_email=_consent_contact_email(ROOT),
                )
                result_consent_json = run_dir / "consent_record.json"
                result_consent_pdf = run_dir / f"consent_{case_name}_{stamp}_{consent_language}.pdf"

                payload_export = dict(payload_selected)
                payload_export.pop("catalog_validation_report", None)
                result_json.write_text(json.dumps(payload_export, ensure_ascii=False, indent=2), encoding="utf-8")
                result_consent_json.write_text(json.dumps(consent_record, ensure_ascii=False, indent=2), encoding="utf-8")
                save_txt(payload_selected, result_txt)
                save_traceability_json(payload_selected, result_trace_json)
                save_traceability_csv(payload_selected, result_trace_csv)

                generated_files = {
                    "JSON": str(result_json),
                    "TXT": str(result_txt),
                    "Traceability JSON": str(result_trace_json),
                    "Traceability CSV": str(result_trace_csv),
                    "Consent record JSON": str(result_consent_json),
                }

                export_technical_pdf(payload_selected, result_pdf_tech)
                export_friendly_pdf_es(payload_es, result_pdf_es)
                export_friendly_pdf_en(payload_en, result_pdf_en)
                export_consent_pdf(consent_record, result_consent_pdf)
                generated_files["Technical PDF"] = str(result_pdf_tech)
                generated_files[_t(language, "friendly_label_es")] = str(result_pdf_es)
                generated_files[_t(language, "friendly_label_en")] = str(result_pdf_en)
                generated_files[_t(language, "consent_download")] = str(result_consent_pdf)

                selected_pdf = result_pdf_en if language == "en" else result_pdf_es
                email_status = _t(language, "email_not_sent")
                try:
                    recipients = _send_pdfs_via_gmail(
                        root=ROOT,
                        company_name=str(ui_cfg["company_name"]),
                        company_email=str(ui_cfg["company_email"]),
                        pdf_paths=[selected_pdf, result_consent_pdf],
                        language=language,
                        include_consent=True,
                    )
                    email_status = f"{_t(language, 'sent_prefix')}: {', '.join(recipients)}"
                except Exception as email_exc:
                    safe_error = _safe_smtp_error_message(email_exc, language)
                    email_status = f"{_t(language, 'not_sent_prefix')}: {safe_error}"

                try:
                    stats_record = build_statistical_record(
                        payload_es,
                        company_type=company_type,
                        budget_range=str(ui_cfg.get("budget_range", "")),
                        generated_at=generated_at,
                    )
                    stats_summary_csv = build_statistical_csv_bytes(stats_record)
                    stats_kpi_records = build_kpi_statistical_records(payload_es, stats_record)
                    stats_kpi_csv = build_kpi_statistical_csv_bytes(stats_kpi_records)
                    stats_guide_csv = build_statistical_data_guide_csv_bytes()
                    _send_statistical_csv_via_gmail(
                        root=ROOT,
                        record=stats_record,
                        payload=payload_es,
                        consent_record=consent_record,
                        summary_csv_bytes=stats_summary_csv,
                        kpi_csv_bytes=stats_kpi_csv,
                        guide_csv_bytes=stats_guide_csv,
                        language=language,
                    )
                except Exception as stats_exc:
                    print(f"RoGen statistical CSV email not sent: {_safe_smtp_error_message(stats_exc, language)}")

                result = payload_selected.get("result", {})
                st.session_state["ui_last_result"] = {
                    "files": generated_files,
                    "generated_at": result.get("timestamp", ""),
                    "current_score": round(_score_to_float(result.get("current_score", 0)), 2),
                    "target_score": result.get("target_score", 0),
                    "actions": len(result.get("roadmap_entries", [])),
                    "email_status": email_status,
                    "language": language,
                }
                st.session_state["scroll_to_top_result"] = True
                st.session_state["scroll_to_top_nonce"] = int(st.session_state.get("scroll_to_top_nonce", 0)) + 1

        except Exception as exc:
            st.error(f"{_t(language, 'roadmap_error')}: {exc}")
        finally:
            overlay_slot.empty()

    if "ui_last_result" in st.session_state:
        st.markdown('<div id="rogen-result-anchor"></div>', unsafe_allow_html=True)
        current_lang = _lang(str(st.session_state["ui_last_result"].get("language", language)))
        _render_last_result_summary(st.session_state["ui_last_result"], current_lang)
        _render_downloads(st.session_state["ui_last_result"], current_lang)


def run_app() -> None:
    try:
        main()
    except Exception as exc:
        language = _lang(str(st.query_params.get("ui_lang", "es")))
        st.error(_t(language, "startup_error"))
        if str(st.query_params.get("debug", "")) == "1":
            st.code(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    run_app()
