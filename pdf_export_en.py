from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from economic_policy import action_economics
from pdf_export import _format_solution_description, identified_gap_indicators
from display_format import format_integer, format_percentage, format_timestamp, to_float

PALETTE = {
    "forest": (0.12, 0.34, 0.24),
    "forest_dark": (0.08, 0.24, 0.18),
    "olive": (0.37, 0.45, 0.28),
    "slate": (0.29, 0.34, 0.28),
    "text": (0.12, 0.13, 0.12),
    "muted": (0.39, 0.42, 0.39),
    "line": (0.80, 0.82, 0.78),
    "card_bg": (0.96, 0.97, 0.95),
    "short": (0.83, 0.33, 0.25),
    "medium": (0.83, 0.58, 0.18),
    "long": (0.34, 0.56, 0.28),
    "link": (0.12, 0.56, 0.96),
}

HORIZON_ORDER = ["Short term", "Medium term", "Long term", "Unclassified"]


def _norm(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized).strip().lower()




_GENERIC_SOLUTION_NAMES_EN = {
    "cnr law 18,450 irrigation technification grant call": "Application for irrigation technology financing",
    "concurso cnr ley 18.450 para tecnificacion de riego": "Application for irrigation technology financing",
    "inia la cruz program for pressurized irrigation with photovoltaic energy": "Pressurized irrigation with photovoltaic energy",
    "programa inia la cruz de riego presurizado con energia fotovoltaica": "Pressurized irrigation with photovoltaic energy",
    "orbit 1-inch solenoid valve at sodimac": "Basic automated irrigation sector control",
    "valvula solenoide 1 pulgada orbit en sodimac": "Basic automated irrigation sector control",
    "agrometeorologia inia para evapotranspiracion y programacion de riego": "Irrigation scheduling based on evapotranspiration and climate",
    "orbit irrigation timer at sodimac": "Basic irrigation timer automation",
    "temporizador de riego orbit en sodimac": "Basic irrigation timer automation",
    "orbit pocket star controller at sodimac": "Basic automatic irrigation scheduling",
    "programador orbit pocket star en sodimac": "Basic automatic irrigation scheduling",
    "orbit b-hyve wifi controller at sodimac": "Remote and automated irrigation scheduling",
    "programador orbit b-hyve wifi en sodimac": "Remote and automated irrigation scheduling",
    "defontana entrepreneur": "Administrative and commercial digitalization with ERP",
    "defontana emprendedor": "Administrative and commercial digitalization with ERP",
    "defontana sme value": "Administrative and commercial integration for SMEs",
    "defontana valor pyme": "Administrative and commercial integration for SMEs",
    "defontana pos starter": "Digital recording of sales and daily production",
    "defontana punto de venta inicio": "Digital recording of sales and daily production",
    "nubox basic module 1.75 uf": "Basic accounting and administrative digitalization",
    "nubox modulo basico 1,75 uf": "Basic accounting and administrative digitalization",
    "nubox advanced plan 2.45 uf": "Advanced administrative and accounting management",
    "nubox plan avanzado 2,45 uf": "Advanced administrative and accounting management",
    "nubox plan 5.75 uf": "Higher-capacity integrated administrative management",
    "nubox plan 5,75 uf": "Higher-capacity integrated administrative management",
    "nubox plan 8.00 uf": "Advanced administrative and accounting management",
    "nubox plan 8,00 uf": "Advanced administrative and accounting management",
    "pvc pipe 25 mm x 3 m at sodimac": "Improvement of irrigation water conveyance and distribution",
    "tuberia pvc 25 mm x 3 m en sodimac": "Improvement of irrigation water conveyance and distribution",
    "pvc pipe 25 mm x 6 m at sodimac": "Improvement of irrigation water conveyance and distribution",
    "tuberia pvc 25 mm x 6 m en sodimac": "Improvement of irrigation water conveyance and distribution",
    "orbit valve with flow control at sodimac": "Sectorized irrigation flow control",
    "valvula orbit con control de flujo en sodimac": "Sectorized irrigation flow control",
    "agrometeorologia inia para seguimiento de rendimiento y clima": "Production performance monitoring with climate data",
    "sag manuals and guidelines for food safety and good practices": "Implementation of good agricultural practices and food safety",
    "manuales y pautas sag para inocuidad y buenas practicas": "Implementation of good agricultural practices and food safety",
    "prochile virtual classroom": "Strengthening export capabilities",
    "aula virtual prochile": "Strengthening export capabilities",
    "prochile user portal": "Access to institutional tools for internationalization",
    "portal del usuario prochile": "Access to institutional tools for internationalization",
    "sence online courses": "Online digital and workforce training",
    "cursos en linea sence": "Online digital and workforce training",
    "sence digital society diploma programs": "Advanced training in digital competencies",
    "diplomados sociedad digital sence": "Advanced training in digital competencies",
    "fia innovation tours and events": "Connection with innovation networks and sector learning",
    "fia giras y eventos de innovacion": "Connection with innovation networks and sector learning",
    "indap investment development program": "Application for productive investment instruments",
    "indap programa de desarrollo de inversiones": "Application for productive investment instruments",
    "jumpseller basic": "Initial implementation of an online sales channel",
    "jumpseller plus": "Professionalization of the online sales channel",
    "jumpseller advanced": "E-commerce scaling",
    "jumpseller premium": "Multichannel e-commerce consolidation",
    "transbank payment link": "Digital payment enablement through payment links",
    "transbank link de pago": "Digital payment enablement through payment links",
    "mercado pago payment link": "Digital payment enablement through payment links",
    "mercado pago link de pago": "Digital payment enablement through payment links",
    "transbank entrepreneur pack": "In-person payment system implementation",
    "transbank pack emprende": "In-person payment system implementation",
    "mercado pago point smart 2": "Mobile point-of-sale implementation",
    "transbank smart pos + payment link": "Integration of in-person and remote payments",
    "transbank smart pos + link de pago": "Integration of in-person and remote payments",
    "transbank webpay plus": "Web payment implementation for e-commerce",
    "uc master's in agrifood business management": "Specialized training in agrifood management",
    "magister en gestion de empresas agroalimentarias uc": "Specialized training in agrifood management",
    "uc doctoral program in agricultural and natural sciences": "Advanced strengthening of research and innovation capabilities",
    "doctorado en ciencias de la agricultura y la naturaleza uc": "Advanced strengthening of research and innovation capabilities",
    "all in one lenovo at pc factory": "IT hardware renewal",
    "all in one lenovo en pc factory": "IT hardware renewal",
    "all in one hp i5 at pc factory": "IT hardware renewal",
    "all in one hp i5 en pc factory": "IT hardware renewal",
    "asesoria tecnica inia y soporte local especializado": "Formalization of specialized technical support",
    "digital renewal in agriculture": "Digital literacy applied to agriculture",
    "renacer digital en el agro": "Digital literacy applied to agriculture",
    "sistema integrado de sensores y programacion de riego": "Integrated sensor-based irrigation scheduling",
    "sistema integrado de sensores y analitica para planificacion productiva": "Sensor-based analytics for production planning",
    "sistema integrado de sensores y analitica para seguimiento de rendimiento": "Sensor-based analytics for performance monitoring",
}


def _solution_display_name(row: dict[str, object], fallback: str = "Unnamed action") -> str:
    raw = str(row.get("solution_name", "") or "").strip()
    if not raw:
        return fallback
    return _GENERIC_SOLUTION_NAMES_EN.get(_norm(raw), raw)


def _solution_urls(row: dict[str, object], *, max_urls: int = 1) -> list[str]:
    raw_values: list[str] = []
    # Prioritize the specific solution URL (source_url) over provider/context links.
    for field in ("source_url", "provider_url"):
        raw = str(row.get(field, "") or "").strip()
        if not raw:
            continue
        raw_values.extend([chunk.strip() for chunk in raw.split("|") if chunk.strip()])
    out: list[str] = []
    seen: set[str] = set()
    for url in raw_values:
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            continue
        # Keep path and query to preserve the exact solution URL.
        clean = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= max_urls:
            break
    return out


def _horizon_order(plazo: str) -> int:
    key = _norm(plazo)
    if "corto" in key or "short" in key:
        return 1
    if "mediano" in key or "medium" in key:
        return 2
    if "largo" in key or "long" in key:
        return 3
    return 4


def _horizon_color(plazo: str) -> tuple[float, float, float]:
    key = _norm(plazo)
    if "corto" in key or "short" in key:
        return PALETTE["short"]
    if "mediano" in key or "medium" in key:
        return PALETTE["medium"]
    if "largo" in key or "long" in key:
        return PALETTE["long"]
    return PALETTE["slate"]


def _canonical_horizon(value: str) -> str:
    key = _norm(value)
    if "corto" in key or "short" in key:
        return "Short term"
    if "mediano" in key or "medium" in key:
        return "Medium term"
    if "largo" in key or "long" in key:
        return "Long term"
    return "Unclassified"


def _horizon_label(value: str) -> str:
    return _canonical_horizon(value)


class SimplePdf:
    def __init__(self, page_width: float = 595.28, page_height: float = 841.89, margin: float = 48.0) -> None:
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.pages: list[list[str]] = []
        self.current_ops: list[str] = []
        self.current_y = 0.0
        self._new_page()

    def _new_page(self) -> None:
        self.current_ops = []
        self.pages.append(self.current_ops)
        self.current_y = self.page_height - self.margin

    @staticmethod
    def _latin1(text: str) -> str:
        # Preserve Spanish Unicode characters and map them to WinAnsi (cp1252) for PDF output.
        cleaned = unicodedata.normalize("NFC", str(text))
        compact = re.sub(r"\s+", " ", cleaned).strip()
        return compact.encode("cp1252", "replace").decode("latin-1")

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _text_op(
        self,
        text: str,
        *,
        x: float,
        y: float,
        size: float,
        bold: bool,
        color: tuple[float, float, float],
    ) -> str:
        font_key = "F2" if bold else "F1"
        escaped = self._escape(self._latin1(text))
        return (
            f"BT /{font_key} {size:.2f} Tf "
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET"
        )

    def _approx_text_width(self, text: str, *, size: float, bold: bool = False) -> float:
        total = 0.0
        for ch in str(text):
            if ch == " ":
                total += size * 0.33
            elif ch in {"M", "W", "@", "%", "&", "Q"}:
                total += size * 0.88
            elif ch.isupper():
                total += size * 0.68
            elif ch.isdigit():
                total += size * 0.56
            else:
                total += size * 0.52
        if bold:
            total *= 1.03
        return total

    def _wrap_by_width(self, text: str, *, max_width: float, size: float, bold: bool = False) -> list[str]:
        words = str(text).split(" ")
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if self._approx_text_width(candidate, size=size, bold=bold) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = word
                continue
            # Very long word: split it to prevent overflow beyond page margins.
            chunk = word
            while chunk and self._approx_text_width(chunk, size=size, bold=bold) > max_width:
                split_at = max(4, int(max_width / max(size * 0.55, 0.1)))
                lines.append(chunk[: split_at - 1] + "-")
                chunk = chunk[split_at - 1 :]
            current = chunk
        if current:
            lines.append(current)
        return lines if lines else [""]

    def _ensure_space(self, height: float) -> None:
        if (self.current_y - height) < self.margin:
            self._new_page()

    def add_rect(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        fill_color: tuple[float, float, float] | None = None,
        stroke_color: tuple[float, float, float] | None = None,
        line_width: float = 1.0,
    ) -> None:
        parts: list[str] = []
        if fill_color is not None:
            parts.append(f"{fill_color[0]:.3f} {fill_color[1]:.3f} {fill_color[2]:.3f} rg")
        if stroke_color is not None:
            parts.append(f"{stroke_color[0]:.3f} {stroke_color[1]:.3f} {stroke_color[2]:.3f} RG {line_width:.2f} w")
        if fill_color is not None and stroke_color is not None:
            draw_op = "B"
        elif fill_color is not None:
            draw_op = "f"
        else:
            draw_op = "S"
        parts.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re {draw_op}")
        self.current_ops.append(" ".join(parts))

    def add_text(
        self,
        text: str,
        *,
        size: float = 11.0,
        bold: bool = False,
        indent: float = 0.0,
        color: tuple[float, float, float] = PALETTE["text"],
        gap_after: float = 2.0,
    ) -> None:
        if text is None:
            return
        line_height = size * 1.40
        usable_width = self.page_width - (2 * self.margin) - indent
        max_width = usable_width if usable_width > 0 else 120.0
        paragraphs = str(text).splitlines() or [str(text)]
        for para in paragraphs:
            clean = self._latin1(para)
            if not clean:
                self._ensure_space(line_height * 0.7)
                self.current_y -= line_height * 0.7
                continue
            for line in self._wrap_by_width(clean, max_width=max_width, size=size, bold=bold):
                self._ensure_space(line_height)
                x = self.margin + indent
                y = self.current_y
                self.current_ops.append(
                    self._text_op(line, x=x, y=y, size=size, bold=bold, color=color)
                )
                self.current_y -= line_height
        if gap_after > 0:
            self._ensure_space(gap_after)
            self.current_y -= gap_after

    def add_section_header(self, title: str, *, accent: tuple[float, float, float] = PALETTE["forest"], gap_after: float = 9.0) -> None:
        block_h = 24.0
        self._ensure_space(block_h + gap_after + 2)
        y_top = self.current_y
        y_bottom = y_top - block_h
        self.add_rect(
            x=self.margin,
            y=y_bottom,
            width=self.page_width - (2 * self.margin),
            height=block_h,
            fill_color=accent,
        )
        self.current_ops.append(
            self._text_op(
                title,
                x=self.margin + 10,
                y=y_bottom + 8.2,
                size=11.2,
                bold=True,
                color=(1.0, 1.0, 1.0),
            )
        )
        self.current_y = y_bottom - gap_after

    def add_banner(self, title: str, subtitle: str) -> None:
        h = 120.0
        y_bottom = self.page_height - h
        self.add_rect(x=0, y=y_bottom, width=self.page_width, height=h, fill_color=PALETTE["forest"])
        usable_width = self.page_width - (2 * self.margin)

        title_clean = self._latin1(title)
        title_size = 22.0
        title_lines: list[str] = []
        for candidate_size in (22.0, 20.0, 18.0, 16.0):
            lines = self._wrap_by_width(title_clean, max_width=usable_width, size=candidate_size, bold=True)
            if len(lines) <= 2:
                title_size = candidate_size
                title_lines = lines
                break
        if not title_lines:
            title_size = 16.0
            title_lines = self._wrap_by_width(title_clean, max_width=usable_width, size=title_size, bold=True)[:3]

        title_top_y = self.page_height - 44.0
        title_line_h = title_size * 1.08
        for idx, line in enumerate(title_lines):
            self.current_ops.append(
                self._text_op(
                    line,
                    x=self.margin,
                    y=title_top_y - (idx * title_line_h),
                    size=title_size,
                    bold=True,
                    color=(1.0, 1.0, 1.0),
                )
            )

        subtitle_clean = self._latin1(subtitle)
        subtitle_width = usable_width * 0.82
        subtitle_size = 11.0
        subtitle_lines = self._wrap_by_width(subtitle_clean, max_width=subtitle_width, size=subtitle_size, bold=False)
        if len(subtitle_lines) > 2:
            subtitle_size = 10.0
            subtitle_lines = self._wrap_by_width(subtitle_clean, max_width=subtitle_width, size=subtitle_size, bold=False)
        if len(subtitle_lines) > 2:
            subtitle_size = 9.0
            subtitle_lines = self._wrap_by_width(subtitle_clean, max_width=subtitle_width, size=subtitle_size, bold=False)
        subtitle_lines = subtitle_lines[:2]

        subtitle_line_h = subtitle_size * 1.15
        subtitle_start_y = max(y_bottom + 12.0, title_top_y - (len(title_lines) * title_line_h) - 8.0)
        for idx, line in enumerate(subtitle_lines):
            self.current_ops.append(
                self._text_op(
                    line,
                    x=self.margin,
                    y=subtitle_start_y - (idx * subtitle_line_h),
                    size=subtitle_size,
                    bold=False,
                    color=(0.90, 0.95, 0.89),
                )
            )

        self.current_y = y_bottom - 24

    def add_page_break(self) -> None:
        self._new_page()

    def _add_page_numbers(self) -> None:
        total = len(self.pages)
        for i, ops in enumerate(self.pages, start=1):
            footer_y = 24.0
            footer_text = f"Page {i} of {total}"
            width_est = len(footer_text) * 9.0 * 0.5
            x = (self.page_width - width_est) / 2.0
            ops.append(
                self._text_op(
                    footer_text,
                    x=x,
                    y=footer_y,
                    size=9.0,
                    bold=False,
                    color=PALETTE["muted"],
                )
            )
            ops.append(f"{PALETTE['line'][0]:.3f} {PALETTE['line'][1]:.3f} {PALETTE['line'][2]:.3f} RG 0.6 w {self.margin:.2f} 36.00 m {self.page_width - self.margin:.2f} 36.00 l S")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._add_page_numbers()
        objects: list[bytes] = []
        page_object_numbers: list[int] = []
        page_count = len(self.pages)
        first_page_obj = 3
        for i, ops in enumerate(self.pages):
            page_obj_num = first_page_obj + (i * 2)
            content_obj_num = page_obj_num + 1
            page_object_numbers.append(page_obj_num)
            stream_data = ("\n".join(ops) + "\n").encode("latin-1", "replace")
            content_obj = b"<< /Length " + str(len(stream_data)).encode("ascii") + b" >>\nstream\n" + stream_data + b"endstream"
            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width:.2f} {self.page_height:.2f}] "
                f"/Resources << /Font << /F1 {first_page_obj + (page_count * 2)} 0 R /F2 {first_page_obj + (page_count * 2) + 1} 0 R >> >> "
                f"/Contents {content_obj_num} 0 R >>"
            ).encode("ascii")
            objects.append(page_obj)
            objects.append(content_obj)
        kids = " ".join(f"{n} 0 R" for n in page_object_numbers)
        pages_obj = f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii")
        catalog_obj = b"<< /Type /Catalog /Pages 2 0 R >>"
        font_regular = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        font_bold = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        full_objects: list[bytes] = [catalog_obj, pages_obj] + objects + [font_regular, font_bold]
        out = BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, obj in enumerate(full_objects, start=1):
            offsets.append(out.tell())
            out.write(f"{i} 0 obj\n".encode("ascii"))
            out.write(obj)
            out.write(b"\nendobj\n")
        xref_start = out.tell()
        out.write(f"xref\n0 {len(full_objects) + 1}\n".encode("ascii"))
        out.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            out.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        out.write(f"trailer\n<< /Size {len(full_objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
        out.write(f"startxref\n{xref_start}\n%%EOF\n".encode("ascii"))
        path.write_bytes(out.getvalue())


def _metric_card(doc: SimplePdf, *, x: float, y_top: float, width: float, title: str, value: str, note: str) -> float:
    h = 70.0
    y_bottom = y_top - h
    doc.add_rect(x=x, y=y_bottom, width=width, height=h, fill_color=PALETTE["card_bg"], stroke_color=PALETTE["line"], line_width=0.8)
    doc.current_ops.append(doc._text_op(title, x=x + 10, y=y_bottom + 50, size=8.7, bold=True, color=PALETTE["muted"]))
    doc.current_ops.append(doc._text_op(value, x=x + 10, y=y_bottom + 31, size=16.0, bold=True, color=PALETTE["forest_dark"]))
    doc.current_ops.append(doc._text_op(note, x=x + 10, y=y_bottom + 15, size=8.5, bold=False, color=PALETTE["slate"]))
    return y_bottom


def _render_summary(
    doc: "SimplePdf",
    entries: list[dict[str, object]],
    *,
    target_progress_pct: float,
    gap_indicators: list[str],
) -> None:
    doc.add_section_header("Summary", accent=PALETTE["forest"])
    progress_pct = min(max(to_float(target_progress_pct), 0.0), 100.0)
    pending_pct = 100.0 - progress_pct
    gap_count = len(gap_indicators)
    action_count = len(entries)
    card_top = doc.current_y
    usable = doc.page_width - (2 * doc.margin)
    gap = 12.0
    card_w = (usable - (3 * gap)) / 4.0
    x0 = doc.margin
    x1 = x0 + card_w + gap
    x2 = x1 + card_w + gap
    x3 = x2 + card_w + gap

    _metric_card(
        doc,
        x=x0,
        y_top=card_top,
        width=card_w,
        title="Progress toward your goal",
        value=format_percentage(progress_pct),
        note="company progress",
    )
    _metric_card(
        doc,
        x=x1,
        y_top=card_top,
        width=card_w,
        title="Still to improve",
        value=format_percentage(pending_pct),
        note="to address with this roadmap",
    )
    _metric_card(
        doc,
        x=x2,
        y_top=card_top,
        width=card_w,
        title="Indicators with gaps",
        value=format_integer(gap_count),
        note="identified in the assessment",
    )
    _metric_card(
        doc,
        x=x3,
        y_top=card_top,
        width=card_w,
        title="Recommended actions",
        value=format_integer(action_count),
        note="organized in stages",
    )
    # Leave the same breathing room below the cards as below the section header.
    doc.current_y = card_top - 88
    if pending_pct > 0.005:
        if action_count:
            action_label = "action" if action_count == 1 else "actions"
            summary_text = (
                f"The company still has {format_percentage(pending_pct)} to improve in order to reach the selected goal. "
                f"This roadmap proposes {format_integer(action_count)} {action_label}, "
                "organized in stages to support gradual improvement."
            )
        else:
            summary_text = (
                f"The company still has {format_percentage(pending_pct)} to improve in order to reach the selected goal. "
                "No actions were included for these gaps in the generated roadmap."
            )
    else:
        summary_text = "The company has already reached the selected improvement goal; no additional actions are required for this goal."
    doc.add_text(summary_text, size=9.2, color=PALETTE["slate"], gap_after=4.0)


def _render_gap_indicators(doc: SimplePdf, indicators: list[str]) -> None:
    doc.add_section_header("Indicators with identified gaps", accent=PALETTE["olive"])
    if not indicators:
        doc.add_text("No gaps were identified for the selected target.", size=9.5)
    for index, indicator in enumerate(indicators, start=1):
        doc.add_text(f"{index}. {indicator}", size=9.5, indent=8, gap_after=1.0)


def _entry_key(row: dict[str, object]) -> tuple[str, str]:
    return (_norm(str(row.get("solution_name", ""))), _norm(str(row.get("kpi", ""))))


def _estimate_text_block_height(
    doc: SimplePdf,
    text: object,
    *,
    size: float,
    indent: float = 0.0,
    gap_after: float = 0.0,
) -> float:
    line_height = size * 1.40
    if text is None:
        return max(gap_after, 0.0)
    usable_width = doc.page_width - (2 * doc.margin) - indent
    max_width = usable_width if usable_width > 0 else 120.0
    paragraphs = str(text).splitlines() or [str(text)]
    total = 0.0
    for para in paragraphs:
        clean = doc._latin1(para)
        if not clean:
            total += line_height * 0.7
            continue
        total += len(doc._wrap_by_width(clean, max_width=max_width, size=size, bold=False)) * line_height
    return total + max(gap_after, 0.0)


def _wrap_url_lines(
    doc: SimplePdf,
    url: str,
    *,
    max_width: float,
    size: float,
) -> list[str]:
    clean = doc._latin1(url)
    if not clean:
        return [""]
    tokens = [tok for tok in re.split(r"([/:?&=#._%-])", clean) if tok != ""]
    lines: list[str] = []
    current = ""
    for tok in tokens:
        candidate = f"{current}{tok}"
        if doc._approx_text_width(candidate, size=size, bold=False) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = tok
        else:
            current = tok
        while current and doc._approx_text_width(current, size=size, bold=False) > max_width:
            piece = ""
            for ch in current:
                probe = piece + ch
                if doc._approx_text_width(probe, size=size, bold=False) <= max_width or not piece:
                    piece = probe
                else:
                    break
            if not piece:
                break
            lines.append(piece)
            current = current[len(piece) :]
    if current:
        lines.append(current)
    return lines if lines else [clean]


def _estimate_labeled_url_height(
    doc: SimplePdf,
    *,
    label: str,
    url: str | None,
    size: float,
    indent: float = 0.0,
    gap_after: float = 0.0,
) -> float:
    if not url:
        return 0.0
    line_height = size * 1.40
    usable_width = doc.page_width - (2 * doc.margin) - indent
    if usable_width <= 0:
        return line_height + max(gap_after, 0.0)
    label_width = doc._approx_text_width(doc._latin1(label), size=size, bold=False)
    first_line_width = max(usable_width - label_width - (size * 0.45), size * 2.0)
    first_line_chunks = _wrap_url_lines(doc, str(url), max_width=first_line_width, size=size)
    extra_lines = 0
    if len(first_line_chunks) > 1:
        extra_lines += len(first_line_chunks) - 1
        for frag in first_line_chunks[1:]:
            extra_lines += max(len(_wrap_url_lines(doc, frag, max_width=usable_width, size=size)) - 1, 0)
    total_lines = 1 + max(extra_lines, 0)
    return (total_lines * line_height) + max(gap_after, 0.0)


def _add_labeled_url(
    doc: SimplePdf,
    *,
    label: str,
    url: str | None,
    size: float,
    indent: float = 0.0,
    label_color: tuple[float, float, float] = PALETTE["slate"],
    link_color: tuple[float, float, float] = PALETTE["link"],
    gap_after: float = 0.0,
) -> None:
    if not url:
        return
    line_height = size * 1.40
    usable_width = doc.page_width - (2 * doc.margin) - indent
    if usable_width <= 0:
        return
    label_clean = doc._latin1(label)
    label_width = doc._approx_text_width(label_clean, size=size, bold=False)
    first_line_width = max(usable_width - label_width - (size * 0.45), size * 2.0)
    chunks = _wrap_url_lines(doc, str(url), max_width=first_line_width, size=size)
    if not chunks:
        chunks = [doc._latin1(str(url))]
    first = chunks[0]
    rest = chunks[1:]
    expanded_rest: list[str] = []
    for frag in rest:
        expanded_rest.extend(_wrap_url_lines(doc, frag, max_width=usable_width, size=size))

    doc._ensure_space(line_height)
    x0 = doc.margin + indent
    y0 = doc.current_y
    doc.current_ops.append(doc._text_op(label_clean, x=x0, y=y0, size=size, bold=False, color=label_color))
    doc.current_ops.append(
        doc._text_op(
            doc._latin1(first),
            x=x0 + label_width + (size * 0.45),
            y=y0,
            size=size,
            bold=False,
            color=link_color,
        )
    )
    doc.current_y -= line_height
    for line in expanded_rest:
        doc._ensure_space(line_height)
        doc.current_ops.append(
            doc._text_op(doc._latin1(line), x=x0, y=doc.current_y, size=size, bold=False, color=link_color)
        )
        doc.current_y -= line_height
    if gap_after > 0:
        doc._ensure_space(gap_after)
        doc.current_y -= gap_after


def _estimate_solution_item_height(
    doc: SimplePdf,
    *,
    title: str,
    meta: str,
    url: str | None,
    description: str,
    title_size: float,
    meta_size: float,
    url_size: float,
    desc_size: float,
    indent: float,
) -> float:
    total = 0.0
    total += _estimate_text_block_height(doc, title, size=title_size, indent=indent, gap_after=0.0)
    total += _estimate_text_block_height(doc, meta, size=meta_size, indent=indent, gap_after=0.0)
    if url:
        total += _estimate_labeled_url_height(doc, label="URL:", url=url, size=url_size, indent=indent, gap_after=0.0)
    total += _estimate_text_block_height(doc, description, size=desc_size, indent=indent, gap_after=2.2)
    return total


def _split_rows_in_buckets(rows: list[dict[str, object]], bucket_count: int) -> list[list[dict[str, object]]]:
    if bucket_count <= 0:
        return []
    if not rows:
        return [[] for _ in range(bucket_count)]
    n = len(rows)
    base = n // bucket_count
    rem = n % bucket_count
    sizes = [base + (1 if i < rem else 0) for i in range(bucket_count)]
    out: list[list[dict[str, object]]] = []
    start = 0
    for size in sizes:
        end = start + size
        out.append(rows[start:end])
        start = end
    return out


def _build_short_term_plan(
    entries: list[dict[str, object]],
    *,
    excluded_keys: set[tuple[str, str]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    blocked_keys = set(excluded_keys or set())
    ordered = sorted(
        entries,
        key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
    )
    short_stage = [r for r in ordered if _canonical_horizon(str(r.get("plazo", ""))) == "Short term"]
    deduped_short: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in short_stage:
        key = _entry_key(row)
        if key in blocked_keys or key in seen:
            continue
        seen.add(key)
        deduped_short.append(row)

    buckets = _split_rows_in_buckets(deduped_short, 3)
    return {
        "start": buckets[0] if len(buckets) > 0 else [],
        "stabilize": buckets[1] if len(buckets) > 1 else [],
        "scale": buckets[2] if len(buckets) > 2 else [],
    }


def _render_plan_bucket(
    doc: SimplePdf,
    *,
    title: str,
    accent: tuple[float, float, float],
    items: list[dict[str, object]],
) -> None:
    doc.add_section_header(title, accent=accent)
    if not items:
        doc.add_text("No actions were identified for this time window.", size=9.2, color=PALETTE["muted"], indent=10)
        return
    for i, row in enumerate(items, start=1):
        item_title = f"{i}. {_solution_display_name(row)}"
        item_meta = f"Focus KPI: {row.get('kpi', '')} | Stage: {_horizon_label(str(row.get('plazo', '')))} | {action_economics(row, 'en')}"
        urls = _solution_urls(row, max_urls=1)
        item_url = urls[0] if urls else None
        description = _format_solution_description(row.get("solution_description"))
        item_desc = f"Description: {description or 'Description not available.'}"
        item_h = _estimate_solution_item_height(
            doc,
            title=item_title,
            meta=item_meta,
            url=item_url,
            description=item_desc,
            title_size=9.8,
            meta_size=8.5,
            url_size=8.2,
            desc_size=8.4,
            indent=16,
        )
        # Keep each solution block together to avoid visible line overlap in dense pages.
        doc._ensure_space(item_h + 3.0)

        doc.add_text(
            item_title,
            size=9.8,
            bold=True,
            indent=8,
            color=PALETTE["forest_dark"],
            gap_after=0.0,
        )
        doc.add_text(
            item_meta,
            size=8.5,
            indent=16,
            color=PALETTE["slate"],
            gap_after=0.0,
        )
        if item_url:
            _add_labeled_url(
                doc,
                label="URL:",
                url=item_url,
                size=8.2,
                indent=16,
                label_color=PALETTE["slate"],
                link_color=PALETTE["link"],
                gap_after=0.0,
            )
        doc.add_text(
            item_desc,
            size=8.4,
            indent=16,
            color=PALETTE["muted"],
            gap_after=1.4,
        )


def _append_short_term_page(
    doc: SimplePdf,
    plan: dict[str, list[dict[str, object]]],
    *,
    company_name: str,
) -> None:
    doc.add_page_break()
    title = "Short-Term Plan"
    subtitle = f"{company_name} | Suggested sequence to implement short-term solutions"
    doc.add_banner(title, subtitle)
    intro = "This plan proposes an actionable sequence to move from diagnosis to the implementation of short-term solutions."
    doc.add_text(intro, size=9.6, color=PALETTE["text"], gap_after=5.0)
    _render_plan_bucket(
        doc,
        title="Phase 1 | Startup and baseline control",
        accent=PALETTE["short"],
        items=plan["start"],
    )
    _render_plan_bucket(
        doc,
        title="Phase 2 | Standardization and monitoring",
        accent=PALETTE["medium"],
        items=plan["stabilize"],
    )
    _render_plan_bucket(
        doc,
        title="Phase 3 | Scale and optimize",
        accent=PALETTE["long"],
        items=plan["scale"],
    )
    doc.add_text(
        "Tip: if a milestone is delayed, do not stop the plan. Reschedule while preserving the order of the phases to maintain momentum.",
        size=8.8,
        color=PALETTE["muted"],
        gap_after=0.0,
    )


def _stage_plan_rows(
    entries: list[dict[str, object]],
    stage: str,
    *,
    excluded_keys: set[tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    blocked_keys = set(excluded_keys or set())
    rows = [row for row in entries if _canonical_horizon(str(row.get("plazo", ""))) == stage]
    rows = sorted(
        rows,
        key=lambda r: (-float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
    )
    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = _entry_key(row)
        if key in blocked_keys or key in seen:
            continue
        deduped.append(row)
        seen.add(key)
    return deduped


def _validate_plan_distribution(
    entries: list[dict[str, object]],
    quick_win_keys: set[tuple[str, str]],
    short_plan: dict[str, list[dict[str, object]]],
    medium_rows: list[dict[str, object]],
    long_rows: list[dict[str, object]],
) -> None:
    all_entries_sorted = sorted(
        entries,
        key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
    )
    deduped_rows: list[dict[str, object]] = []
    seen_all: set[tuple[str, str]] = set()
    for row in all_entries_sorted:
        key = _entry_key(row)
        if key in seen_all:
            continue
        seen_all.add(key)
        deduped_rows.append(row)

    expected_plan_keys = {
        _entry_key(row) for row in deduped_rows
        if _entry_key(row) not in quick_win_keys and _canonical_horizon(str(row.get("plazo", ""))) != "Unclassified"
    }

    short_rows = list(short_plan.get("start", [])) + list(short_plan.get("stabilize", [])) + list(short_plan.get("scale", []))
    short_keys = {_entry_key(r) for r in short_rows}
    medium_keys = {_entry_key(r) for r in medium_rows}
    long_keys = {_entry_key(r) for r in long_rows}
    plan_union = short_keys | medium_keys | long_keys

    overlaps = [
        ("short-medium", short_keys & medium_keys),
        ("short-long", short_keys & long_keys),
        ("medium-long", medium_keys & long_keys),
    ]
    overlap_count = sum(len(keys) for _, keys in overlaps)
    if overlap_count > 0:
        raise ValueError("Plan validation failed: duplicated solutions were found across plans.")

    for row in short_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Short term":
            raise ValueError("Plan validation failed: the short-term plan contains solutions from another stage.")
    for row in medium_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Medium term":
            raise ValueError("Plan validation failed: the medium-term plan contains solutions from another stage.")
    for row in long_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Long term":
            raise ValueError("Plan validation failed: the long-term plan contains solutions from another stage.")

    if quick_win_keys & plan_union:
        raise ValueError("Plan validation failed: an immediate-impact action was included in staged plans.")

    missing = expected_plan_keys - plan_union
    extra = plan_union - expected_plan_keys
    if missing or extra:
        detail = []
        if missing:
            detail.append(f"orphaned={len(missing)}")
        if extra:
            detail.append(f"extra={len(extra)}")
        raise ValueError("Plan validation failed: inconsistent distribution (" + ", ".join(detail) + ").")


def _append_stage_plan_page(
    doc: SimplePdf,
    stage_rows: list[dict[str, object]],
    *,
    company_name: str,
    title: str,
    subtitle: str,
    intro: str,
    buckets: list[tuple[str, tuple[float, float, float]]],
) -> None:
    if not stage_rows:
        return

    doc.add_page_break()
    doc.add_banner(title, f"{company_name} | {subtitle}")
    doc.add_text(intro, size=9.6, color=PALETTE["text"], gap_after=5.0)

    bucket_rows = _split_rows_in_buckets(stage_rows, max(len(buckets), 1))
    for idx, (bucket_title, bucket_color) in enumerate(buckets):
        rows_for_bucket = bucket_rows[idx] if idx < len(bucket_rows) else []
        _render_plan_bucket(
            doc,
            title=bucket_title,
            accent=bucket_color,
            items=rows_for_bucket,
        )


def _append_backlog_page(doc: SimplePdf, entries: list[dict[str, object]], *, company_name: str) -> None:
    ordered = sorted(
        entries,
        key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
    )
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in ordered:
        key = _entry_key(row)
        if key in seen:
            continue
        seen.add(key)
        stage = _canonical_horizon(str(row.get("plazo", "")))
        grouped[stage].append(row)

    doc.add_page_break()
    doc.add_banner("IMPLEMENTATION CHECKLIST", f"{company_name} | Implementation checklist by period")
    doc.add_text(
        "Mark each action as it is implemented.",
        size=9.4,
        color=PALETTE["text"],
        gap_after=4.0,
    )

    stage_defs = [
        ("Short term", "Short term", PALETTE["short"]),
        ("Medium term", "Medium term", PALETTE["medium"]),
        ("Long term", "Long term", PALETTE["long"]),
        ("Unclassified", "Unclassified", PALETTE["muted"]),
    ]
    for stage_key, stage_label, stage_color in stage_defs:
        stage_rows = grouped.get(stage_key, [])
        if stage_key == "Unclassified" and not stage_rows:
            continue
        doc.add_section_header(stage_label, accent=stage_color)
        if not stage_rows:
            doc.add_text("No pending actions for this stage.", size=8.9, color=PALETTE["muted"], indent=8)
            continue
        for idx, row in enumerate(stage_rows, start=1):
            name = _solution_display_name(row)
            area = str(row.get("domain", "")).strip() or "No key area"
            kpi = str(row.get("kpi", "")).strip() or "Not reported"
            economics = action_economics(row, "en")
            backlog_title = f"[ ] {idx}. {name}"
            backlog_meta = f"Key area: {area} | KPI: {kpi} | {economics}"
            backlog_h = _estimate_text_block_height(doc, backlog_title, size=9.4, indent=8, gap_after=0.0)
            backlog_h += _estimate_text_block_height(doc, backlog_meta, size=8.2, indent=18, gap_after=1.0)
            doc._ensure_space(backlog_h + 2.0)
            doc.add_text(f"[ ] {idx}. {name}", size=9.4, bold=True, indent=8, color=PALETTE["forest_dark"], gap_after=0.0)
            doc.add_text(
                f"Key area: {area} | KPI: {kpi} | {economics}",
                size=8.2,
                indent=18,
                color=PALETTE["slate"],
                gap_after=1.0,
            )


def export_roadmap_pdf(payload: dict[str, object], output_path: Path) -> None:
    company = payload.get("company", {}) if isinstance(payload, dict) else {}
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    entries = result.get("roadmap_entries", []) if isinstance(result, dict) else []
    entries = sorted(entries, key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0))))
    compatible = [row for row in entries if row.get("selection_status") == "compatible"]
    conditional = [row for row in entries if row.get("selection_status") != "compatible"]
    quick_wins = [row for row in compatible if _canonical_horizon(str(row.get("plazo", ""))) == "Short term"][:3]
    quick_win_keys = {_entry_key(item) for item in quick_wins}
    target_progress_pct = float(result.get("target_progress_pct", 0))
    gap_indicators = identified_gap_indicators(result.get("kpi_results", []))

    doc = SimplePdf()
    doc.add_banner(
        "TECHNOLOGY IMPROVEMENT ROADMAP",
        f"{company.get('name', '')} | {company.get('company_type', '')} | {format_timestamp(result.get('timestamp', ''))}",
    )
    _render_summary(
        doc,
        entries,
        target_progress_pct=target_progress_pct,
        gap_indicators=gap_indicators,
    )
    _render_gap_indicators(doc, gap_indicators)
    if conditional:
        doc.add_section_header("Actions that require confirmation", accent=PALETTE["olive"])
        for item in conditional:
            doc._ensure_space(43.0)
            doc.add_text(_solution_display_name(item), bold=True, size=9.5, gap_after=0.0)
            doc.add_text(
                f"{item.get('kpi', '')} | {_horizon_label(str(item.get('plazo', '')))} | {action_economics(item, 'en')}",
                indent=10, size=8.7, gap_after=1.0,
            )
            urls = _solution_urls(item, max_urls=1)
            if urls:
                _add_labeled_url(doc, label="URL:", url=urls[0], size=8.7, indent=10, gap_after=3.0)
    entries = compatible

    doc.add_section_header("Quick Wins", accent=PALETTE["forest"])
    if not quick_wins:
        doc.add_text("No compatible short-term actions were selected.", size=10)
    else:
        for i, item in enumerate(quick_wins, start=1):
            horizon = str(item.get("plazo", ""))
            marker = _horizon_color(horizon)
            item_title = f"{i}. {_solution_display_name(item)}"
            item_meta = f"{_horizon_label(horizon)} | KPI: {item.get('kpi', '')} | {action_economics(item, 'en')}"
            urls = _solution_urls(item, max_urls=1)
            item_url = urls[0] if urls else None
            description = _format_solution_description(item.get("solution_description"))
            item_desc = f"Description: {description or 'Description not available.'}"
            item_h = _estimate_solution_item_height(
                doc,
                title=item_title,
                meta=item_meta,
                url=item_url,
                description=item_desc,
                title_size=10.8,
                meta_size=9.0,
                url_size=8.7,
                desc_size=9.0,
                indent=12,
            )
            marker_h = max(item_h - 4.0, 38.0)
            doc._ensure_space(item_h + 4.0)
            y_top = doc.current_y + 2.0
            y_bottom = y_top - marker_h
            doc.add_rect(
                x=doc.margin + 4,
                y=y_bottom,
                width=3.5,
                height=marker_h,
                fill_color=marker,
            )
            doc.add_text(item_title, size=10.8, bold=True, indent=12, color=PALETTE["forest_dark"], gap_after=0.0)
            doc.add_text(
                item_meta,
                size=9.0,
                indent=12,
                color=PALETTE["slate"],
                gap_after=0.0,
            )
            if item_url:
                _add_labeled_url(
                    doc,
                    label="URL:",
                    url=item_url,
                    size=8.7,
                    indent=12,
                    label_color=PALETTE["slate"],
                    link_color=PALETTE["link"],
                    gap_after=0.0,
                )
            doc.add_text(
                item_desc,
                size=9.0,
                indent=12,
                color=PALETTE["muted"],
                gap_after=2.2,
            )

    short_plan = _build_short_term_plan(entries, excluded_keys=quick_win_keys)
    medium_plan_rows = _stage_plan_rows(entries, "Medium term", excluded_keys=quick_win_keys)
    long_plan_rows = _stage_plan_rows(entries, "Long term", excluded_keys=quick_win_keys)
    _validate_plan_distribution(entries, quick_win_keys, short_plan, medium_plan_rows, long_plan_rows)

    _append_short_term_page(
        doc,
        short_plan,
        company_name=str(company.get("name", "Company")),
    )
    _append_stage_plan_page(
        doc,
        medium_plan_rows,
        company_name=str(company.get("name", "Company")),
        title="Medium-Term Plan",
        subtitle="Suggested sequence to implement medium-term solutions",
        intro="This plan proposes an actionable sequence to move from diagnosis to the implementation of medium-term solutions.",
        buckets=[
            (
                "Phase 1 | Operational preparation",
                PALETTE["medium"],
            ),
            (
                "Phase 2 | Core implementation",
                PALETTE["olive"],
            ),
            (
                "Phase 3 | Stage closure",
                PALETTE["long"],
            ),
        ],
    )
    _append_stage_plan_page(
        doc,
        long_plan_rows,
        company_name=str(company.get("name", "Company")),
        title="Long-Term Plan",
        subtitle="Suggested sequence to implement long-term solutions",
        intro="This plan proposes an actionable sequence to move from diagnosis to the implementation of long-term solutions.",
        buckets=[
            (
                "Phase 1 | Initial scaling",
                PALETTE["long"],
            ),
            (
                "Phase 2 | Integration and optimization",
                PALETTE["olive"],
            ),
            (
                "Phase 3 | Consolidation",
                PALETTE["forest_dark"],
            ),
        ],
    )
    _append_backlog_page(doc, entries, company_name=str(company.get("name", "Company")))
    doc.save(output_path)
