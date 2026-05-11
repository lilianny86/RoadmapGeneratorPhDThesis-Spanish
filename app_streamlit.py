from __future__ import annotations

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

from pdf_export import export_friendly_pdf, export_technical_pdf
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
BUDGET_LABELS = {
    "up_to_1m": "Hasta 1.000.000 CLP",
    "between_1m_5m": "Entre 1.000.000 y 5.000.000 CLP",
    "from_5m": "Desde 5.000.000 CLP",
}
BUDGET_TO_CLP = {
    "up_to_1m": 1_000_000.0,
    "between_1m_5m": 4_999_999.0,
    "from_5m": 5_000_000.0,
}
RUT_WIDGET_KEY = "company_rut_input"


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return clean or "empresa"


def _company_name_for_filename(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "", text)
    text = re.sub(r"\s+", "_", text).strip("._-")
    return (text or "Empresa").upper()


def _friendly_pdf_filename(company_type: str, company_name: str, generated_at: datetime) -> str:
    prefix = "ME" if str(company_type) == "medium" else "PE"
    stamp = generated_at.strftime("%Y%m%d_%H%M")
    return f"Roadmap_{prefix}_{_company_name_for_filename(company_name)}_{stamp}.pdf"


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
def _load_profile_cached(root: str, company_type: str) -> dict[str, object]:
    return load_profile_data(Path(root), company_type)


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
}

.stApp {
  font-family: "Source Sans 3", sans-serif;
  color: var(--agri-ink);
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 12% 12%, rgba(111, 143, 78, 0.22), transparent 32%),
    radial-gradient(circle at 90% 4%, rgba(163, 112, 63, 0.16), transparent 28%),
    linear-gradient(180deg, #e7f0e2 0%, #f8f4e9 52%, #f3ebd6 100%);
}

[data-testid="stHeader"] {
  background: rgba(248, 244, 233, 0.55);
  backdrop-filter: blur(4px);
}

[data-testid="stSidebar"] {
  background:
    linear-gradient(180deg, rgba(31, 79, 47, 0.92) 0%, rgba(47, 109, 60, 0.9) 48%, rgba(122, 79, 44, 0.9) 100%);
  border-right: 1px solid rgba(245, 237, 213, 0.28);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
  color: #f7f3e8;
}

.block-container {
  padding-top: 1.2rem;
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
  background-color: rgba(248, 244, 233, 0.96) !important;
  color: var(--agri-ink) !important;
  -webkit-text-fill-color: var(--agri-ink) !important;
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


def _render_sidebar(profile: dict[str, object], max_level: int) -> dict[str, object]:
    st.sidebar.header("Datos De Empresa")
    company_name = st.sidebar.text_input("Nombre empresa*", value="", placeholder="Ingresa nombre de la empresa")
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
        st.sidebar.markdown("<div class='field-error'>RUT inválido. Verifica el dígito verificador.</div>", unsafe_allow_html=True)
    company_email = st.sidebar.text_input("Correo*", value="")
    target_level = st.sidebar.slider("Nivel objetivo", min_value=1, max_value=max_level, value=min(3, max_level), step=1)
    budget_total_key = st.sidebar.radio(
        "Presupuesto para mejoras*",
        options=BUDGET_OPTIONS,
        index=1,
        format_func=lambda key: BUDGET_LABELS.get(str(key), str(key)),
    )
    st.sidebar.markdown("<div class='sidebar-required-note'>* Campos obligatorios</div>", unsafe_allow_html=True)

    return {
        "company_name": company_name,
        "company_rut": company_rut,
        "company_email": company_email,
        "target_level": target_level,
        "budget_total_label": BUDGET_LABELS.get(str(budget_total_key), str(budget_total_key)),
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


def _missing_required_company_fields(company_type: str, ui_cfg: dict[str, object]) -> list[str]:
    missing: list[str] = []
    if company_type == "__select__":
        missing.append("Tipo de empresa")
    if not str(ui_cfg.get("company_name", "")).strip():
        missing.append("Nombre empresa")
    rut_value = str(ui_cfg.get("company_rut", "")).strip()
    if not rut_value:
        missing.append("RUT")
    elif not _is_valid_rut(rut_value):
        missing.append("RUT válido")
    if not str(ui_cfg.get("company_email", "")).strip():
        missing.append("Correo")
    return missing


def _clean_prompt(prompt: str, qnum: int) -> str:
    text = str(prompt or "").strip()
    text = re.sub(rf"^\s*pregunta\s*{qnum}\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*pregunta\s*\d+\s*[:.)-]*\s*", "", text, flags=re.IGNORECASE)
    return text or f"Pregunta {qnum}"


def _send_pdfs_via_gmail(
    *,
    root: Path,
    company_name: str,
    company_email: str,
    pdf_paths: list[Path],
) -> list[str]:
    cfg, _ = load_security_config(root)
    if not cfg.smtp_host:
        cfg.smtp_host = "smtp.gmail.com"
    if cfg.smtp_port <= 0:
        cfg.smtp_port = 587

    errors = validate_smtp_config(cfg, strict=True)
    if errors:
        raise RuntimeError("Config SMTP incompleta: " + " | ".join(errors))

    targets: list[str] = []
    for raw in [str(company_email or "")]:
        parts = [x.strip() for x in raw.split(",") if x.strip()]
        for p in parts:
            if p not in targets:
                targets.append(p)
    if not targets:
        raise RuntimeError("Debes indicar un correo válido en los datos de empresa (campo Correo).")

    msg = EmailMessage()
    msg["Subject"] = f"Roadmap customizado {company_name}"
    msg["From"] = cfg.smtp_from
    msg["To"] = ", ".join(targets)
    msg.set_content(
        "Estimado/a,\n\n"
        f"Se adjunta el Roadmap customizado para la empresa {company_name}.\n\n"
        "*Este es un correo automático. No responder."
    )

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


def _render_downloads(result: dict[str, object]) -> None:
    files: dict[str, str] = result.get("files", {}) if isinstance(result, dict) else {}
    friendly_pdf: Path | None = None
    for label, path_str in files.items():
        path = Path(path_str)
        if not path.exists() or path.suffix.lower() != ".pdf":
            continue
        label_txt = str(label).lower()
        name_txt = path.name.lower()
        if "amigable" in label_txt or "amigable" in name_txt:
            friendly_pdf = path
            break

    if friendly_pdf is None:
        return

    st.download_button(
        label="Descargar PDF",
        data=friendly_pdf.read_bytes(),
        file_name=friendly_pdf.name,
        mime="application/pdf",
        use_container_width=True,
    )


def _render_last_result_summary(last: dict[str, object]) -> None:
    st.success("Roadmap generado correctamente.")
    m1, m2, m3 = st.columns(3)
    m1.metric("Puntaje Actual", last.get("current_score", 0))
    m2.metric("Puntaje Objetivo", last.get("target_score", 0))
    m3.metric("Acciones", last.get("actions", 0))
    if str(last.get("email_status", "")).startswith("Enviado"):
        st.info(f"Correo: {last['email_status']}")
    else:
        st.warning(f"Correo: {last.get('email_status', 'No enviado')}")


def main() -> None:
    st.set_page_config(page_title="RoadmapGenerator Captura", layout="wide")
    _render_styles()

    st.sidebar.header("Configuracion Inicial")
    company_type_labels = {
        "__select__": "------Seleccione------",
        "small": "Pequeña empresa",
        "medium": "Mediana empresa",
    }
    company_type = st.sidebar.selectbox(
        "Tipo de empresa*",
        options=["__select__", "small", "medium"],
        format_func=lambda x: company_type_labels.get(x, x),
    )
    st.sidebar.markdown("---")
    title_company_type = "Empresa" if company_type == "__select__" else company_type_labels.get(company_type, "Empresa")
    st.title(f"RoadmapGenerator | Captura De Datos {title_company_type}")

    if company_type == "__select__":
        st.info("Selecciona un tipo de empresa para continuar.")
        return

    try:
        profile = _load_profile_cached(str(ROOT), company_type)
    except Exception as exc:
        st.error(f"No fue posible cargar el perfil '{company_type}': {exc}")
        return

    questions: list[dict[str, Any]] = [dict(x) for x in profile.get("questions", [])]
    max_level = max((len(q.get("level_labels", [])) for q in questions), default=5)
    ui_cfg = _render_sidebar(profile, max_level=max_level)
    missing_required = _missing_required_company_fields(company_type, ui_cfg)
    if missing_required:
        st.warning("Completa los campos obligatorios del panel izquierdo antes de responder el cuestionario.")
        st.caption("Faltantes: " + ", ".join(missing_required))
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">Preguntas</div>
  <div class="summary-value">{len(questions)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">Perfil</div>
  <div class="summary-value summary-value-text">{html.escape(str(ui_cfg.get("profile_label", "")))}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
<div class="app-card summary-card">
  <div class="summary-label">Nivel Objetivo</div>
  <div class="summary-value">{int(ui_cfg["target_level"])}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Cuestionario")
    for q in sorted(questions, key=lambda row: int(row.get("number", 0))):
        qnum = int(q["number"])
        options = [str(x) for x in q.get("options", [])]
        prompt = _clean_prompt(str(q.get("prompt", "")), qnum)

        st.markdown(f"<div class='question-label'>Pregunta {qnum}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='question-text'>{html.escape(prompt)}</div>", unsafe_allow_html=True)
        st.radio(
            label=f"Respuesta {qnum}",
            options=list(range(len(options))),
            format_func=lambda i, rows=options: rows[i],
            key=f"q_{company_type}_{qnum}",
            label_visibility="collapsed",
        )

    if st.button("Generar Roadmap", type="primary", use_container_width=True):
        try:
            answers = _collect_answers(company_type, questions)
            engine_cfg = build_engine_config(None, _build_overrides(ui_cfg))

            with st.spinner("Generando roadmap y archivos de salida..."):
                payload = build_roadmap(
                    root=ROOT,
                    company_type=company_type,
                    answers=answers,
                    target_level=int(ui_cfg["target_level"]),
                    company_name=str(ui_cfg["company_name"]),
                    company_rut=str(ui_cfg["company_rut"]),
                    company_email=str(ui_cfg["company_email"]),
                    engine_cfg=engine_cfg,
                )

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
                result_pdf_friendly = run_dir / _friendly_pdf_filename(
                    company_type=company_type,
                    company_name=str(ui_cfg["company_name"]),
                    generated_at=generated_at,
                )

                payload_export = dict(payload)
                payload_export.pop("catalog_validation_report", None)
                result_json.write_text(json.dumps(payload_export, ensure_ascii=False, indent=2), encoding="utf-8")
                save_txt(payload, result_txt)
                save_traceability_json(payload, result_trace_json)
                save_traceability_csv(payload, result_trace_csv)

                generated_files = {
                    "JSON": str(result_json),
                    "TXT": str(result_txt),
                    "Trazabilidad JSON": str(result_trace_json),
                    "Trazabilidad CSV": str(result_trace_csv),
                }

                export_technical_pdf(payload, result_pdf_tech)
                export_friendly_pdf(payload, result_pdf_friendly)
                generated_files["PDF Tecnico"] = str(result_pdf_tech)
                generated_files["PDF Amigable"] = str(result_pdf_friendly)

                email_status = "No enviado"
                try:
                    recipients = _send_pdfs_via_gmail(
                        root=ROOT,
                        company_name=str(ui_cfg["company_name"]),
                        company_email=str(ui_cfg["company_email"]),
                        pdf_paths=[result_pdf_friendly],
                    )
                    email_status = f"Enviado a: {', '.join(recipients)}"
                except Exception as email_exc:
                    email_status = f"No enviado: {email_exc}"

                result = payload.get("result", {})
                st.session_state["ui_last_result"] = {
                    "files": generated_files,
                    "generated_at": result.get("timestamp", ""),
                    "current_score": result.get("current_score", 0),
                    "target_score": result.get("target_score", 0),
                    "actions": len(result.get("roadmap_entries", [])),
                    "email_status": email_status,
                }

        except Exception as exc:
            st.error(f"No se pudo generar el roadmap: {exc}")

    if "ui_last_result" in st.session_state:
        _render_last_result_summary(st.session_state["ui_last_result"])
        _render_downloads(st.session_state["ui_last_result"])


if __name__ == "__main__":
    main()
