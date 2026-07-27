from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf_export import PALETTE as PALETTE_ES
from pdf_export import SimplePdf as SpanishPdf
from pdf_export_en import PALETTE as PALETTE_EN
from pdf_export_en import SimplePdf as EnglishPdf


CONSENT_VERSION = "RoGen-IC-v1.0"
THESIS_TITLE_ES = "RoGen: Un marco de apoyo a la toma de decisiones, basado en la madurez, para la adopción de tecnología en pymes agrícolas"
THESIS_TITLE_EN = "RoGen: A maturity-based decision-support framework for technology adoption in agricultural SMEs"
RESEARCHER_NAME = "Lilianny Marrero"
UNIVERSITY_NAME_ES = "Universidad Técnica Federico Santa María"
UNIVERSITY_NAME_EN = "Universidad Técnica Federico Santa María"


def _language(language: str) -> str:
    return "en" if str(language).strip().lower() == "en" else "es"


def consent_sections(language: str, contact_email: str) -> list[tuple[str, str]]:
    if _language(language) == "en":
        return [
            (
                "Invitation and purpose",
                f"You are invited to participate voluntarily in the doctoral thesis \"{THESIS_TITLE_EN}\". "
                f"The responsible researcher is {RESEARCHER_NAME}, a PhD student in Computer Engineering at {UNIVERSITY_NAME_EN}. "
                "The study diagnoses the current state of agricultural SMEs using a predefined set of indicators and uses the results to produce a customized technology-adoption roadmap.",
            ),
            (
                "What participation involves",
                "Participation consists of providing company-profile information and answering a maturity questionnaire. "
                "The information is used to prepare the roadmap and to conduct academic analyses related to the doctoral thesis.",
            ),
            (
                "Voluntary participation",
                "Participation is voluntary. You may decline to participate or stop before submitting the questionnaire, without consequences. "
                "You may ask questions before or during your participation.",
            ),
            (
                "Confidentiality and use of information",
                "The application processes the company name, business RUT, contact email, questionnaire responses, and generated roadmap. "
                "This information is accessible only to the responsible researcher for thesis-related purposes. "
                "Any academic reporting will use aggregated or anonymized information and will not associate published results with your name or company.",
            ),
            (
                "Benefits and contact",
                f"You will receive the generated roadmap by email. For questions, comments, or a request related to your participation, contact {RESEARCHER_NAME} at {contact_email}.",
            ),
        ]

    return [
        (
            "Invitación y propósito",
            f"Se le invita a participar voluntariamente en la tesis doctoral \"{THESIS_TITLE_ES}\". "
            f"La investigadora responsable es {RESEARCHER_NAME}, estudiante del Doctorado en Ingeniería Informática de la {UNIVERSITY_NAME_ES}. "
            "El estudio realiza un diagnóstico del estado actual de las pymes agrícolas, usando como base un grupo de indicadores previamente definidos, y utiliza los resultados para generar una hoja de ruta personalizada de adopción tecnológica.",
        ),
        (
            "En qué consiste la participación",
            "La participación consiste en proporcionar información del perfil de la empresa y responder un cuestionario de madurez. "
            "La información se utiliza para preparar el roadmap y realizar análisis académicos relacionados con la tesis doctoral.",
        ),
        (
            "Participación voluntaria",
            "La participación es voluntaria. Puede decidir no participar o detenerse antes de enviar el cuestionario, sin consecuencias. "
            "Puede realizar preguntas antes o durante su participación.",
        ),
        (
            "Confidencialidad y uso de la información",
            "La aplicación procesa el nombre de la empresa, RUT de empresa, correo de contacto, respuestas del cuestionario y roadmap generado. "
            "Esta información será accesible solo para la investigadora responsable y para fines relacionados con la tesis. "
            "Todo reporte académico utilizará información agregada o anonimizada y no asociará los resultados publicados con su nombre o empresa.",
        ),
        (
            "Beneficio y contacto",
            f"Recibirá por correo electrónico el roadmap generado. Para preguntas, comentarios o solicitudes relacionadas con su participación, contacte a {RESEARCHER_NAME} en {contact_email}.",
        ),
    ]


def consent_acceptance_statement(language: str) -> str:
    if _language(language) == "en":
        return "I confirm that I have read and understood this informed consent and voluntarily agree to participate in the RoGen assessment."
    return "Confirmo que he leído y comprendido este consentimiento informado y acepto voluntariamente participar en la evaluación RoGen."


def build_consent_record(
    *,
    consent_id: str,
    language: str,
    accepted_at: str,
    participant_email: str,
    company_name: str,
    company_rut: str,
    contact_email: str,
) -> dict[str, Any]:
    selected_language = _language(language)
    return {
        "consent_id": str(consent_id),
        "consent_version": CONSENT_VERSION,
        "language": selected_language,
        "accepted_at": str(accepted_at),
        "acceptance_method": "checkbox",
        "acceptance_statement": consent_acceptance_statement(selected_language),
        "participant_email": str(participant_email),
        "company_name": str(company_name),
        "company_rut": str(company_rut),
        "researcher_name": RESEARCHER_NAME,
        "university": UNIVERSITY_NAME_EN if selected_language == "en" else UNIVERSITY_NAME_ES,
        "contact_email": str(contact_email),
        "interviewer_signature_status": "pending",
    }


def export_consent_pdf(record: dict[str, Any], output_path: Path) -> None:
    language = _language(str(record.get("language", "es")))
    if language == "en":
        doc = EnglishPdf()
        palette = PALETTE_EN
        title = "INFORMED CONSENT"
        subtitle = f"RoGen doctoral thesis | Version {record.get('consent_version', CONSENT_VERSION)}"
        acceptance_title = "Electronic acceptance record"
        signature_title = "Acceptance and interviewer confirmation"
        participant_label = "Participant contact email"
        company_label = "Company"
        rut_label = "Business RUT"
        accepted_label = "Acceptance date and time"
        identifier_label = "Consent identifier"
        participant_signature = "Participant: electronic acceptance registered through the informed-consent checkbox."
        interviewer_signature = f"Interviewer: {RESEARCHER_NAME}. Digital signature pending incorporation."
    else:
        doc = SpanishPdf()
        palette = PALETTE_ES
        title = "CONSENTIMIENTO INFORMADO"
        subtitle = f"Tesis doctoral RoGen | Versión {record.get('consent_version', CONSENT_VERSION)}"
        acceptance_title = "Registro de aceptación electrónica"
        signature_title = "Aceptación y constancia de entrevistadora"
        participant_label = "Correo de contacto de participante"
        company_label = "Empresa"
        rut_label = "RUT de empresa"
        accepted_label = "Fecha y hora de aceptación"
        identifier_label = "Identificador de consentimiento"
        participant_signature = "Participante: aceptación electrónica registrada mediante la casilla de consentimiento informado."
        interviewer_signature = f"Entrevistadora: {RESEARCHER_NAME}. Firma digital pendiente de incorporación."

    doc.add_banner(title, subtitle)
    for section_title, paragraph in consent_sections(language, str(record.get("contact_email", ""))):
        doc.add_section_header(section_title, accent=palette["forest"])
        doc.add_text(paragraph, size=10.2, color=palette["text"], gap_after=7.0)

    doc.add_section_header(acceptance_title, accent=palette["forest"])
    doc.add_text(str(record.get("acceptance_statement", "")), size=10.2, bold=True, color=palette["forest_dark"])
    doc.add_text(f"{participant_label}: {record.get('participant_email', '')}", size=9.8)
    doc.add_text(f"{company_label}: {record.get('company_name', '')}", size=9.8)
    doc.add_text(f"{rut_label}: {record.get('company_rut', '')}", size=9.8)
    doc.add_text(f"{accepted_label}: {record.get('accepted_at', '')}", size=9.8)
    doc.add_text(f"{identifier_label}: {record.get('consent_id', '')}", size=9.8)

    doc.add_section_header(signature_title, accent=palette["forest"])
    doc.add_text(participant_signature, size=10.0, gap_after=6.0)
    doc.add_text(interviewer_signature, size=10.0)
    doc.save(output_path)
