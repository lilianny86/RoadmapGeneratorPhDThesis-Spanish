from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from costing import estimate_cost_clp, is_monthly_subscription
from display_format import format_clp, format_decimal, format_integer, format_percentage, format_timestamp, to_float

PALETTE = {
    "forest": (0.12, 0.34, 0.24),
    "forest_dark": (0.08, 0.24, 0.18),
    "olive": (0.37, 0.45, 0.28),
    "slate": (0.29, 0.34, 0.28),
    "text": (0.12, 0.13, 0.12),
    "muted": (0.39, 0.42, 0.39),
    "line": (0.80, 0.82, 0.78),
    "chip_bg": (0.92, 0.95, 0.91),
    "card_bg": (0.96, 0.97, 0.95),
    "short": (0.83, 0.33, 0.25),
    "medium": (0.83, 0.58, 0.18),
    "long": (0.34, 0.56, 0.28),
    "danger": (0.78, 0.22, 0.20),
    "warning": (0.86, 0.67, 0.14),
    "success": (0.28, 0.58, 0.30),
    "link": (0.12, 0.56, 0.96),
}

HORIZON_ORDER = ["Corto plazo", "Mediano plazo", "Largo plazo", "Sin clasificar"]
HORIZON_RANGES = {
    "Corto plazo": "1-3 meses",
    "Mediano plazo": "3-6 meses",
    "Largo plazo": "6-12 meses",
}
_TRAILING_CONNECTOR_WORDS = {
    "a",
    "al",
    "ante",
    "bajo",
    "cabe",
    "con",
    "contra",
    "como",
    "de",
    "del",
    "desde",
    "durante",
    "e",
    "el",
    "en",
    "entre",
    "hacia",
    "hasta",
    "la",
    "las",
    "los",
    "mediante",
    "o",
    "para",
    "por",
    "que",
    "segun",
    "sin",
    "sobre",
    "tras",
    "u",
    "un",
    "una",
    "unos",
    "unas",
    "y",
}


def _norm(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized).strip().lower()





_GENERIC_SOLUTION_NAMES_ES = {
    "concurso cnr ley 18.450 para tecnificacion de riego": "Postulación a financiamiento para tecnificación de riego",
    "programa inia la cruz de riego presurizado con energia fotovoltaica": "Implementación de riego presurizado con energía fotovoltaica",
    "valvula solenoide 1 pulgada orbit en sodimac": "Sectorización automatizada del riego",
    "agrometeorologia inia para evapotranspiracion y programacion de riego": "Programación de riego basada en evapotranspiración y clima",
    "temporizador de riego orbit en sodimac": "Automatización básica de horarios de riego",
    "programador orbit pocket star en sodimac": "Programación automática básica del riego",
    "programador orbit b-hyve wifi en sodimac": "Programación remota y automatizada del riego",
    "defontana emprendedor": "Digitalización administrativa y comercial con ERP",
    "defontana valor pyme": "Integración administrativa y comercial para PyMEs",
    "defontana punto de venta inicio": "Registro digital de ventas y producción diaria",
    "nubox modulo basico 1,75 uf": "Digitalización contable y administrativa básica",
    "nubox plan avanzado 2,45 uf": "Gestión administrativa y contable avanzada",
    "nubox plan 5,75 uf": "Gestión administrativa integrada de mayor capacidad",
    "nubox plan 8,00 uf": "Gestión administrativa y contable avanzada",
    "tuberia pvc 25 mm x 3 m en sodimac": "Mejora de conducción y distribución de agua de riego",
    "tuberia pvc 25 mm x 6 m en sodimac": "Mejora de conducción y distribución de agua de riego",
    "valvula orbit con control de flujo en sodimac": "Control sectorizado del flujo de riego",
    "agrometeorologia inia para seguimiento de rendimiento y clima": "Seguimiento de rendimiento productivo con datos climáticos",
    "manuales y pautas sag para inocuidad y buenas practicas": "Implementación de buenas prácticas e inocuidad agrícola",
    "aula virtual prochile": "Fortalecimiento de habilidades exportadoras",
    "portal del usuario prochile": "Acceso a herramientas institucionales para internacionalización",
    "cursos en linea sence": "Capacitación digital y laboral en línea",
    "diplomados sociedad digital sence": "Formación avanzada en competencias digitales",
    "fia giras y eventos de innovacion": "Vinculación con redes de innovación y aprendizaje sectorial",
    "indap programa de desarrollo de inversiones": "Postulación a instrumentos de inversión productiva",
    "jumpseller basic": "Implementación inicial de canal de venta online",
    "jumpseller plus": "Profesionalización del canal de venta online",
    "jumpseller advanced": "Escalamiento del comercio electrónico",
    "jumpseller premium": "Consolidación de comercio electrónico multicanal",
    "transbank link de pago": "Habilitación de pagos digitales mediante enlaces",
    "mercado pago link de pago": "Habilitación de pagos digitales mediante enlaces",
    "transbank pack emprende": "Implementación de sistema de pago presencial",
    "mercado pago point smart 2": "Implementación de punto de venta móvil",
    "transbank smart pos + link de pago": "Integración de pagos presenciales y remotos",
    "transbank webpay plus": "Implementación de pagos web para comercio electrónico",
    "magister en gestion de empresas agroalimentarias uc": "Formación especializada en gestión agroalimentaria",
    "doctorado en ciencias de la agricultura y la naturaleza uc": "Fortalecimiento avanzado de capacidades de investigación e innovación",
    "all in one lenovo en pc factory": "Renovación de infraestructura computacional",
    "all in one hp i5 en pc factory": "Renovación de infraestructura computacional",
    "asesoria tecnica inia y soporte local especializado": "Formalización de soporte técnico especializado",
    "renacer digital en el agro": "Alfabetización digital aplicada al agro",
}


def _solution_display_name(row: dict[str, object], fallback: str = "Acción sin nombre") -> str:
    raw = str(row.get("solution_name", "") or "").strip()
    if not raw:
        return fallback
    return _GENERIC_SOLUTION_NAMES_ES.get(_norm(raw), raw)


def _short(text: str, max_len: int = 170) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", str(text)).strip()
    marker = re.search(r"\bSe propone para la transici[oó]n\b", compact, flags=re.IGNORECASE)
    if marker:
        compact = compact[: marker.start()].strip()
    compact = re.sub(r"\s*,\s*$", "", compact).strip()
    compact = re.sub(r"\s*\.\.\.\s*$", ".", compact).strip()
    return compact


def _trim_incomplete_ending(text: str) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ""
    tokens = clean.split(" ")
    while tokens:
        candidate = tokens[-1].strip(" ,.;:-")
        if not candidate:
            tokens.pop()
            continue
        if _norm(candidate) not in _TRAILING_CONNECTOR_WORDS:
            break
        tokens.pop()
    out = " ".join(tokens).strip(" ,.;:-")
    return out or clean


def _brief(text: str, max_len: int = 110) -> str:
    compact = _short(text)
    if not compact:
        return ""
    compact = re.sub(r"\s+", " ", compact).strip()

    if len(compact) <= max_len:
        if re.search(r"[.!?]$", compact):
            return compact
        finalized = _trim_incomplete_ending(compact)
        if not re.search(r"[.!?]$", finalized):
            finalized = f"{finalized}."
        return finalized

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]
    candidate = ""
    for sentence in sentences:
        trial = sentence if not candidate else f"{candidate} {sentence}"
        if len(trial) <= max_len:
            candidate = trial
            continue
        break
    if candidate:
        if re.search(r"[.!?]$", candidate):
            return candidate
        return f"{_trim_incomplete_ending(candidate)}."

    trimmed = compact[: max_len + 1]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    trimmed = _trim_incomplete_ending(trimmed)
    if not trimmed:
        trimmed = compact[:max_len].strip(" ,.;:-")
    if not re.search(r"[.!?]$", trimmed):
        trimmed = f"{trimmed}."
    return trimmed


def _solution_urls(row: dict[str, object], *, max_urls: int = 1) -> list[str]:
    raw_values: list[str] = []
    # Prioriza URL de la solución concreta (source_url) antes que enlaces de proveedor/contexto.
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
        # Mantiene ruta y query para no perder el enlace exacto de la solución.
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
        return "Corto plazo"
    if "mediano" in key or "medium" in key:
        return "Mediano plazo"
    if "largo" in key or "long" in key:
        return "Largo plazo"
    months = _extract_timeline_months(value)
    if months is not None:
        if months <= 3:
            return "Corto plazo"
        if months <= 6:
            return "Mediano plazo"
        if months <= 12:
            return "Largo plazo"
    return "Sin clasificar"


def _extract_timeline_months(value: object) -> float | None:
    if value is None:
        return None
    text = str(value)
    normalized = _norm(text)
    numbers = [float(token.replace(",", ".")) for token in re.findall(r"\d+(?:[.,]\d+)?", text)]
    if not numbers:
        return None
    if "mes" in normalized or "month" in normalized:
        return max(numbers)
    if "anio" in normalized or "year" in normalized:
        return max(numbers) * 12.0
    return None


def _horizon_label(value: str) -> str:
    base = _canonical_horizon(value)
    if base in HORIZON_RANGES:
        return f"{base} ({HORIZON_RANGES[base]})"
    return base


def _parse_clp_amount(price_value: object) -> float | None:
    if price_value is None:
        return None
    raw = str(price_value).strip()
    if not raw:
        return None
    normalized = _norm(raw)
    if "uf" in normalized:
        return None

    numbers: list[int] = []
    for chunk in re.findall(r"\d[\d\.,\s]*", raw):
        digits = re.sub(r"[^\d]", "", chunk)
        if digits:
            numbers.append(int(digits))
    if not numbers:
        return None
    if len(numbers) >= 2 and ("-" in raw or "entre" in normalized or " a " in f" {normalized} "):
        return float(max(numbers))
    return float(numbers[0])


def _fmt_clp(value: float | None) -> str:
    return format_clp(value, "No estimable")


def _entry_price_amount(row: dict[str, object]) -> float | None:
    if _norm(row.get("price_type", "")) in {"variable", "unknown"}:
        return None
    estimated = estimate_cost_clp(row, use_existing_estimate=True)
    return estimated if estimated is not None else _parse_clp_amount(row.get("price"))


def _entry_price_label(row: dict[str, object], unavailable: str = "No confirmado (requiere cotización)") -> str:
    min_value = row.get("price_min_clp")
    max_value = row.get("price_max_clp")
    try:
        min_amount = max(float(min_value), 0.0) if min_value is not None and str(min_value).strip() else None
    except (TypeError, ValueError):
        min_amount = None
    try:
        max_amount = max(float(max_value), 0.0) if max_value is not None and str(max_value).strip() else None
    except (TypeError, ValueError):
        max_amount = None

    amount = max_amount if max_amount is not None else min_amount
    if amount is not None:
        if is_monthly_subscription(row):
            total = _entry_price_amount(row)
            if total is not None:
                return _fmt_clp(total)
        if min_amount is not None and max_amount is not None and min_amount != max_amount:
            return f"{_fmt_clp(min_amount)} - {_fmt_clp(max_amount)}"
        return _fmt_clp(amount)

    return unavailable


def _build_budget_summary(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in entries:
        grouped[_canonical_horizon(str(row.get("plazo", "")))].append(row)

    rows: list[dict[str, object]] = []
    for horizon in HORIZON_ORDER:
        stage_rows = grouped.get(horizon, [])
        known_values = [_entry_price_amount(r) for r in stage_rows]
        known_values = [v for v in known_values if v is not None]
        rows.append(
            {
                "stage": horizon,
                "actions": len(stage_rows),
                "with_cost": len(known_values),
                "without_cost": max(len(stage_rows) - len(known_values), 0),
                "budget_clp": sum(known_values) if known_values else 0.0,
            }
        )
    return rows


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
        # Conserva caracteres Unicode de español y los mapea a WinAnsi (cp1252) para PDF.
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

    def _wrap(self, text: str, max_chars: int) -> list[str]:
        if max_chars < 8:
            max_chars = 8
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                    current = word
                else:
                    chunk = word
                    while len(chunk) > max_chars:
                        lines.append(chunk[: max_chars - 1] + "-")
                        chunk = chunk[max_chars - 1 :]
                    current = chunk
        if current:
            lines.append(current)
        return lines if lines else [""]

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
            # Palabra muy larga: partirla para evitar que se corte fuera de página.
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

    def add_center_text(
        self,
        text: str,
        *,
        size: float = 11.0,
        bold: bool = False,
        color: tuple[float, float, float] = PALETTE["text"],
        gap_after: float = 2.0,
    ) -> None:
        clean = self._latin1(text)
        width_est = max(len(clean), 1) * size * 0.51
        x = max((self.page_width - width_est) / 2.0, self.margin)
        self._ensure_space(size * 1.4)
        self.current_ops.append(self._text_op(clean, x=x, y=self.current_y, size=size, bold=bold, color=color))
        self.current_y -= size * 1.40
        if gap_after > 0:
            self.current_y -= gap_after

    def add_rule(
        self,
        *,
        color: tuple[float, float, float] = PALETTE["line"],
        line_width: float = 1.0,
        gap_after: float = 10.0,
    ) -> None:
        self._ensure_space(gap_after + 2)
        y = self.current_y
        self.current_ops.append(
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG {line_width:.2f} w {self.margin:.2f} {y:.2f} m {self.page_width - self.margin:.2f} {y:.2f} l S"
        )
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

    def add_kpi_bar(self, *, label: str, current: float, target: float, gap: float) -> None:
        line_h = 20.0
        self._ensure_space(line_h + 8)
        y_text = self.current_y
        self.current_ops.append(self._text_op(label, x=self.margin, y=y_text, size=9.2, bold=False, color=PALETTE["text"]))
        bar_x = self.page_width - self.margin - 170
        bar_w = 150.0
        bar_h = 7.5
        y_bar = y_text - 1
        max_score = max(target, 4.0, current)
        current_ratio = max(min(current / max_score, 1.0), 0.0)
        target_ratio = max(min(target / max_score, 1.0), 0.0)
        self.add_rect(x=bar_x, y=y_bar, width=bar_w, height=bar_h, fill_color=(0.90, 0.91, 0.88))
        self.add_rect(x=bar_x, y=y_bar, width=bar_w * current_ratio, height=bar_h, fill_color=PALETTE["forest"])
        marker_x = bar_x + (bar_w * target_ratio)
        self.current_ops.append(f"{PALETTE['short'][0]:.3f} {PALETTE['short'][1]:.3f} {PALETTE['short'][2]:.3f} RG 1.1 w {marker_x:.2f} {y_bar - 1:.2f} m {marker_x:.2f} {y_bar + bar_h + 1:.2f} l S")
        self.current_ops.append(
            self._text_op(
                f"Brecha {format_decimal(gap)}",
                x=bar_x + bar_w + 6,
                y=y_text,
                size=8.6,
                bold=True,
                color=PALETTE["slate"],
            )
        )
        self.current_y -= line_h

    def add_page_break(self) -> None:
        self._new_page()

    def _add_page_numbers(self) -> None:
        total = len(self.pages)
        for i, ops in enumerate(self.pages, start=1):
            footer_y = 24.0
            footer_text = f"Página {i} de {total}"
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


def _progress_to_target_pct(current_score: float, target_score: float) -> float:
    if target_score <= 0:
        return 0.0
    return min(max((current_score / target_score) * 100.0, 0.0), 100.0)


def _render_friendly_summary(
    doc: "SimplePdf",
    entries: list[dict[str, object]],
    *,
    current_score: float,
    target_score: float,
    gap_total: float,
) -> None:
    doc.add_section_header("Resumen", accent=PALETTE["forest"])
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
        title="Puntaje actual",
        value=format_decimal(current_score),
        note="situación de partida",
    )
    _metric_card(
        doc,
        x=x1,
        y_top=card_top,
        width=card_w,
        title="Puntaje objetivo",
        value=format_decimal(target_score),
        note="meta de madurez",
    )
    _metric_card(
        doc,
        x=x2,
        y_top=card_top,
        width=card_w,
        title="Brecha total",
        value=format_decimal(gap_total),
        note="Objetivo - actual",
    )
    _metric_card(
        doc,
        x=x3,
        y_top=card_top,
        width=card_w,
        title="Avance a la meta",
        value=format_percentage(_progress_to_target_pct(current_score, target_score)),
        note="Actual / objetivo",
    )
    doc.current_y = card_top - 84


def _table_cell_text(doc: SimplePdf, text: str, *, x: float, y: float, width: float, size: float, bold: bool, color: tuple[float, float, float], align: str = "left") -> None:
    clean = doc._latin1(text)
    avail = max(width - 10.0, 8.0)
    draw_size = size
    est = doc._approx_text_width(clean, size=draw_size, bold=bold)
    while est > avail and draw_size > 7.2:
        draw_size = round(draw_size - 0.2, 2)
        est = doc._approx_text_width(clean, size=draw_size, bold=bold)
    if est > avail:
        base = clean
        suffix = "..."
        while base and doc._approx_text_width(base + suffix, size=draw_size, bold=bold) > avail:
            base = base[:-1]
        clean = (base.rstrip() + suffix) if base else suffix
        est = doc._approx_text_width(clean, size=draw_size, bold=bold)
    if align == "right":
        tx = max(x + 4.0, x + width - est - 6.0)
    elif align == "center":
        tx = x + max((width - est) / 2.0, 4.0)
    else:
        tx = x + 6.0
    doc.current_ops.append(doc._text_op(clean, x=tx, y=y, size=draw_size, bold=bold, color=color))


def _render_budget_table(
    doc: SimplePdf,
    entries: list[dict[str, object]],
    *,
    title: str,
    accent: tuple[float, float, float],
    note: str,
) -> None:
    summary = _build_budget_summary(entries)
    total_actions = sum(int(r["actions"]) for r in summary)
    total_with_cost = sum(int(r["with_cost"]) for r in summary)
    total_without_cost = sum(int(r["without_cost"]) for r in summary)
    total_budget = sum(float(r["budget_clp"]) for r in summary)

    doc.add_section_header(title, accent=accent)
    table_width = doc.page_width - (2 * doc.margin)
    col_widths = [0.30, 0.12, 0.14, 0.14, 0.30]
    col_widths = [w * table_width for w in col_widths]
    row_h = 24.0

    def draw_row(values: list[str], *, fill: tuple[float, float, float], text_color: tuple[float, float, float], bold: bool = False, header: bool = False) -> None:
        doc._ensure_space(row_h + 2)
        y_top = doc.current_y
        y_bottom = y_top - row_h
        x = doc.margin
        for idx, cell in enumerate(values):
            width = col_widths[idx]
            doc.add_rect(x=x, y=y_bottom, width=width, height=row_h, fill_color=fill, stroke_color=PALETTE["line"], line_width=0.7)
            align = "left" if idx == 0 else ("center" if header else "right")
            _table_cell_text(
                doc,
                cell,
                x=x,
                y=y_bottom + 8.3,
                width=width,
                size=8.8,
                bold=bold,
                color=text_color,
                align=align,
            )
            x += width
        doc.current_y = y_bottom

    draw_row(
        ["Etapa", "Acciones", "Con valor", "Sin dato", "Presupuesto CLP"],
        fill=PALETTE["forest_dark"],
        text_color=(1.0, 1.0, 1.0),
        bold=True,
        header=True,
    )

    for row in summary:
        draw_row(
            [
                _horizon_label(str(row["stage"])),
                format_integer(row["actions"]),
                format_integer(row["with_cost"]),
                format_integer(row["without_cost"]),
                _fmt_clp(float(row["budget_clp"])),
            ],
            fill=PALETTE["card_bg"],
            text_color=PALETTE["text"],
            bold=False,
        )

    draw_row(
        [
            "Total",
            format_integer(total_actions),
            format_integer(total_with_cost),
            format_integer(total_without_cost),
            _fmt_clp(total_budget),
        ],
        fill=PALETTE["chip_bg"],
        text_color=PALETTE["forest_dark"],
        bold=True,
    )
    doc.current_y -= 10
    doc.add_text(note, size=8.3, color=PALETTE["muted"], gap_after=8.0)


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


def _build_30_60_90_plan(
    entries: list[dict[str, object]],
    *,
    excluded_keys: set[tuple[str, str]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    blocked_keys = set(excluded_keys or set())
    ordered = sorted(
        entries,
        key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
    )
    short_stage = [r for r in ordered if _canonical_horizon(str(r.get("plazo", ""))) == "Corto plazo"]
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
        "30": buckets[0] if len(buckets) > 0 else [],
        "60": buckets[1] if len(buckets) > 1 else [],
        "90": buckets[2] if len(buckets) > 2 else [],
    }


def _render_plan_bucket(
    doc: SimplePdf,
    *,
    title: str,
    subtitle: str,
    accent: tuple[float, float, float],
    items: list[dict[str, object]],
) -> None:
    doc.add_section_header(title, accent=accent)
    doc.add_text(subtitle, size=8.9, color=PALETTE["slate"], gap_after=3.5)
    if not items:
        doc.add_text("No se detectaron acciones para esta ventana de tiempo.", size=9.2, color=PALETTE["muted"], indent=10)
        return
    for i, row in enumerate(items, start=1):
        item_title = f"{i}. {_solution_display_name(row)}"
        item_meta = f"KPI foco: {row.get('kpi', '')} | Etapa: {_horizon_label(str(row.get('plazo', '')))} | Valor: {_entry_price_label(row)}"
        urls = _solution_urls(row, max_urls=1)
        item_url = urls[0] if urls else None
        item_desc = f"Descripción: {_brief(str(row.get('solution_description', '')), 180) or 'Descripción no disponible.'}"
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
        # Mantiene cada solución completa en una misma página para evitar solapes visuales.
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


def _append_30_60_90_page(
    doc: SimplePdf,
    entries: list[dict[str, object]],
    *,
    company_name: str,
    friendly: bool,
    excluded_keys: set[tuple[str, str]] | None = None,
    plan_override: dict[str, list[dict[str, object]]] | None = None,
) -> None:
    plan = plan_override if plan_override is not None else _build_30_60_90_plan(entries, excluded_keys=excluded_keys)
    doc.add_page_break()
    title = "Plan de Corto Plazo"
    subtitle = f"{company_name} | Secuencia sugerida para implementar soluciones de Corto plazo"
    doc.add_banner(title, subtitle)
    intro = "Este plan propone una secuencia accionable para pasar del diagnóstico a implementación de soluciones de Corto plazo."
    doc.add_text(intro, size=9.6, color=PALETTE["text"], gap_after=5.0)
    _render_plan_bucket(
        doc,
        title="Días 0-30 | Arranque y control base",
        subtitle="Objetivo: activar quick wins y establecer línea base de indicadores.",
        accent=PALETTE["short"],
        items=plan["30"],
    )
    _render_plan_bucket(
        doc,
        title="Días 31-60 | Estandarización y seguimiento",
        subtitle="Objetivo: consolidar procesos, automatizar tareas recurrentes y medir adopción.",
        accent=PALETTE["medium"],
        items=plan["60"],
    )
    _render_plan_bucket(
        doc,
        title="Días 61-90 | Escalar y optimizar",
        subtitle="Objetivo: integrar iniciativas de mayor impacto y cerrar brechas estructurales.",
        accent=PALETTE["long"],
        items=plan["90"],
    )
    if friendly:
        doc.add_text(
            "Tip: si un hito se retrasa, no detengas el plan. Reprograma manteniendo el orden 30/60/90 para sostener tracción.",
            size=8.8,
            color=PALETTE["muted"],
            gap_after=0.0,
        )
    else:
        doc.add_text(
            "Gobernanza sugerida: reunión quincenal de avance, decisión semanal de bloqueadores y registro de evidencias de impacto.",
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


def _validate_friendly_plan_distribution(
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

    expected_plan_keys = {_entry_key(r) for r in deduped_rows if _entry_key(r) not in quick_win_keys}

    short_rows = list(short_plan.get("30", [])) + list(short_plan.get("60", [])) + list(short_plan.get("90", []))
    short_keys = {_entry_key(r) for r in short_rows}
    medium_keys = {_entry_key(r) for r in medium_rows}
    long_keys = {_entry_key(r) for r in long_rows}
    plan_union = short_keys | medium_keys | long_keys

    overlaps = [
        ("corto-mediano", short_keys & medium_keys),
        ("corto-largo", short_keys & long_keys),
        ("mediano-largo", medium_keys & long_keys),
    ]
    overlap_count = sum(len(keys) for _, keys in overlaps)
    if overlap_count > 0:
        return

    for row in short_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Corto plazo":
            return
    for row in medium_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Mediano plazo":
            return
    for row in long_rows:
        if _canonical_horizon(str(row.get("plazo", ""))) != "Largo plazo":
            return

    if quick_win_keys & plan_union:
        return

    missing = expected_plan_keys - plan_union
    extra = plan_union - expected_plan_keys
    if missing or extra:
        return


def _append_stage_plan_page(
    doc: SimplePdf,
    entries: list[dict[str, object]],
    *,
    company_name: str,
    stage: str,
    title: str,
    subtitle: str,
    intro: str,
    buckets: list[tuple[str, str, tuple[float, float, float]]],
    excluded_keys: set[tuple[str, str]] | None = None,
    stage_rows_override: list[dict[str, object]] | None = None,
) -> bool:
    stage_rows = stage_rows_override if stage_rows_override is not None else _stage_plan_rows(entries, stage, excluded_keys=excluded_keys)
    if not stage_rows:
        return False

    doc.add_page_break()
    doc.add_banner(title, f"{company_name} | {subtitle}")
    doc.add_text(intro, size=9.6, color=PALETTE["text"], gap_after=5.0)

    bucket_rows = _split_rows_in_buckets(stage_rows, max(len(buckets), 1))
    for idx, (bucket_title, bucket_subtitle, bucket_color) in enumerate(buckets):
        rows_for_bucket = bucket_rows[idx] if idx < len(bucket_rows) else []
        _render_plan_bucket(
            doc,
            title=bucket_title,
            subtitle=bucket_subtitle,
            accent=bucket_color,
            items=rows_for_bucket,
        )
    return True


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
    doc.add_banner("CHECKLIST DE IMPLEMENTACIÓN", f"{company_name} | Checklist de implementación por período")
    doc.add_text(
        "Marca cada acción cuando se implemente.",
        size=9.4,
        color=PALETTE["text"],
        gap_after=4.0,
    )

    stage_defs = [
        ("Corto plazo", "Corto plazo (1-3 meses)", PALETTE["short"]),
        ("Mediano plazo", "Mediano plazo (3-6 meses)", PALETTE["medium"]),
        ("Largo plazo", "Largo plazo (6-12 meses)", PALETTE["long"]),
    ]
    for stage_key, stage_label, stage_color in stage_defs:
        doc.add_section_header(stage_label, accent=stage_color)
        stage_rows = grouped.get(stage_key, [])
        if not stage_rows:
            doc.add_text("Sin acciones pendientes en esta etapa.", size=8.9, color=PALETTE["muted"], indent=8)
            continue
        for idx, row in enumerate(stage_rows, start=1):
            name = _solution_display_name(row)
            area = str(row.get("domain", "")).strip() or "Sin área clave"
            kpi = str(row.get("kpi", "")).strip() or "No informado"
            cost = _entry_price_label(row)
            backlog_title = f"[ ] {idx}. {name}"
            backlog_meta = f"Área clave: {area} | KPI: {kpi} | Valor: {cost}"
            backlog_h = _estimate_text_block_height(doc, backlog_title, size=9.4, indent=8, gap_after=0.0)
            backlog_h += _estimate_text_block_height(doc, backlog_meta, size=8.2, indent=18, gap_after=1.0)
            doc._ensure_space(backlog_h + 2.0)
            doc.add_text(f"[ ] {idx}. {name}", size=9.4, bold=True, indent=8, color=PALETTE["forest_dark"], gap_after=0.0)
            doc.add_text(
                f"Área clave: {area} | KPI: {kpi} | Valor: {cost}",
                size=8.2,
                indent=18,
                color=PALETTE["slate"],
                gap_after=1.0,
            )


def _top_stage_milestones(entries: list[dict[str, object]], *, per_stage: int = 2) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in entries:
        stage = _canonical_horizon(str(row.get("plazo", "")))
        grouped[stage].append(row)

    selected: dict[str, list[dict[str, object]]] = {}
    for stage in ["Corto plazo", "Mediano plazo", "Largo plazo"]:
        stage_rows = grouped.get(stage, [])
        stage_rows = sorted(
            stage_rows,
            key=lambda r: (-float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))),
        )
        selected[stage] = stage_rows[:per_stage]
    return selected


def _draw_12_month_timeline_band(doc: SimplePdf) -> None:
    band_h = 21.0
    doc._ensure_space(band_h + 34.0)
    x0 = doc.margin + 10.0
    total_w = doc.page_width - (2 * doc.margin) - 20.0
    y_top = doc.current_y
    y_bottom = y_top - band_h
    cursor = x0
    segments = [
        ("Corto 1-3m", 3.0, PALETTE["short"]),
        ("Mediano 3-6m", 3.0, PALETTE["medium"]),
        ("Largo 6-12m", 6.0, PALETTE["long"]),
    ]
    for label, months, color in segments:
        width = total_w * (months / 12.0)
        doc.add_rect(
            x=cursor,
            y=y_bottom,
            width=width,
            height=band_h,
            fill_color=color,
            stroke_color=PALETTE["line"],
            line_width=0.6,
        )
        doc.current_ops.append(
            doc._text_op(
                label,
                x=cursor + 6,
                y=y_bottom + 6,
                size=8.2,
                bold=True,
                color=(1.0, 1.0, 1.0),
            )
        )
        cursor += width

    ticks = [(0.0, "M1"), (3.0, "M3"), (6.0, "M6"), (12.0, "M12")]
    for month, label in ticks:
        x = x0 + (total_w * (month / 12.0))
        doc.current_ops.append(
            f"{PALETTE['slate'][0]:.3f} {PALETTE['slate'][1]:.3f} {PALETTE['slate'][2]:.3f} RG 0.9 w {x:.2f} {y_bottom - 2:.2f} m {x:.2f} {y_bottom - 9:.2f} l S"
        )
        doc.current_ops.append(
            doc._text_op(
                label,
                x=max(x - 7, doc.margin),
                y=y_bottom - 20,
                size=8.0,
                bold=True,
                color=PALETTE["slate"],
            )
        )
    doc.current_y = y_bottom - 28


def _stage_traffic_status(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in entries:
        grouped[_canonical_horizon(str(row.get("plazo", "")))].append(row)

    stages = ["Corto plazo", "Mediano plazo", "Largo plazo"]
    action_counts: dict[str, int] = {}
    avg_priorities: dict[str, float] = {}
    for stage in stages:
        rows = grouped.get(stage, [])
        action_counts[stage] = len(rows)
        if rows:
            avg_priorities[stage] = sum(float(r.get("priority", 0)) for r in rows) / len(rows)
        else:
            avg_priorities[stage] = 0.0

    max_actions = max(action_counts.values()) if action_counts else 0
    max_priority = max(avg_priorities.values()) if avg_priorities else 0.0
    status: dict[str, dict[str, object]] = {}

    for stage in stages:
        actions = action_counts[stage]
        avg_priority = avg_priorities[stage]
        if actions == 0:
            status[stage] = {
                "label": "ALTO",
                "color": PALETTE["success"],
                "note": "Sin acciones pendientes en esta etapa.",
            }
            continue

        action_ratio = (actions / max_actions) if max_actions > 0 else 0.0
        priority_ratio = (avg_priority / max_priority) if max_priority > 0 else 0.0
        pressure = (0.6 * action_ratio) + (0.4 * priority_ratio)

        if pressure >= 0.67:
            status[stage] = {
                "label": "BAJO",
                "color": PALETTE["danger"],
                "note": "Alta carga de implementación; requiere seguimiento semanal.",
            }
        elif pressure >= 0.34:
            status[stage] = {
                "label": "MEDIO",
                "color": PALETTE["warning"],
                "note": "Carga intermedia; monitorear avances quincenalmente.",
            }
        else:
            status[stage] = {
                "label": "ALTO",
                "color": PALETTE["success"],
                "note": "Carga controlada para esta etapa.",
            }
    return status


def _render_stage_traffic_lights(doc: SimplePdf, entries: list[dict[str, object]]) -> None:
    status = _stage_traffic_status(entries)
    doc.add_section_header("Semáforo de avance por etapa", accent=PALETTE["olive"])
    doc.add_text(
        "Lectura estimada según carga de acciones y prioridad: verde (avance alto), amarillo (avance medio), rojo (avance bajo).",
        size=8.6,
        color=PALETTE["muted"],
        gap_after=4.0,
    )
    for stage in ["Corto plazo", "Mediano plazo", "Largo plazo"]:
        row = status.get(stage, {})
        color = row.get("color", PALETTE["slate"])
        label = str(row.get("label", "MEDIO"))
        note = str(row.get("note", ""))
        doc._ensure_space(24.0)
        y = doc.current_y
        x = doc.margin + 6.0
        doc.add_rect(
            x=x,
            y=y - 13.0,
            width=13.0,
            height=13.0,
            fill_color=color,
            stroke_color=PALETTE["line"],
            line_width=0.6,
        )
        doc.current_ops.append(
            doc._text_op(
                f"{_horizon_label(stage)}",
                x=x + 20.0,
                y=y - 2.0,
                size=9.0,
                bold=True,
                color=PALETTE["forest_dark"],
            )
        )
        doc.current_ops.append(
            doc._text_op(
                f"{label}: {note}",
                x=x + 170.0,
                y=y - 2.0,
                size=8.5,
                bold=False,
                color=PALETTE["slate"],
            )
        )
        doc.current_y -= 20.0
    doc.current_y -= 2.0


def _append_12_month_timeline_page(doc: SimplePdf, entries: list[dict[str, object]], *, company_name: str, friendly: bool) -> None:
    milestones = _top_stage_milestones(entries, per_stage=2)
    doc.add_page_break()
    doc.add_banner(
        "CRONOGRAMA 12 MESES",
        f"{company_name} | Visual por etapas: corto (1-3), mediano (3-6), largo (6-12)",
    )
    doc.add_text(
        "Usa este cronograma para calendarizar hitos por trimestre y monitorear avance mensual.",
        size=9.6,
        color=PALETTE["text"],
        gap_after=5.0,
    )
    _draw_12_month_timeline_band(doc)
    for stage in ["Corto plazo", "Mediano plazo", "Largo plazo"]:
        doc.add_section_header(f"Hitos {_horizon_label(stage)}", accent=_horizon_color(stage))
        rows = milestones.get(stage, [])
        if not rows:
            doc.add_text("Sin hitos priorizados para esta etapa.", size=9.0, color=PALETTE["muted"], indent=8)
            continue
        for i, row in enumerate(rows, start=1):
            doc.add_text(
                f"Hito {i}: {_solution_display_name(row)}",
                size=9.7,
                bold=True,
                indent=8,
                color=PALETTE["forest_dark"],
                gap_after=0.0,
            )
            doc.add_text(
                f"KPI: {row.get('kpi', '')} | Valor: {_entry_price_label(row)}",
                size=8.4,
                indent=16,
                color=PALETTE["slate"],
                gap_after=0.0,
            )
            doc.add_text(
                f"Resultado esperado: {_short(str(row.get('solution_description', '')), 120)}",
                size=8.3,
                indent=16,
                color=PALETTE["muted"],
                gap_after=1.2,
            )
    if friendly:
        doc.add_text(
            "Revisión sugerida: cierre mensual de avances y ajuste de prioridades según resultados.",
            size=8.7,
            color=PALETTE["muted"],
            gap_after=0.0,
        )
    else:
        doc.add_text(
            "Control técnico sugerido: checkpoint mensual con evidencia de KPI y estado de implementación por hito.",
            size=8.7,
            color=PALETTE["muted"],
            gap_after=0.0,
        )


def export_technical_pdf(payload: dict[str, object], output_path: Path) -> None:
    company = payload.get("company", {}) if isinstance(payload, dict) else {}
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    doc = SimplePdf()

    doc.add_banner(
        "ROADMAP TÉCNICO DE MADUREZ",
        f"{company.get('name', '')} | {company.get('company_type', '')} | {format_timestamp(result.get('timestamp', ''))}",
    )

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
        title="Puntaje actual",
        value=format_decimal(result.get("current_score", 0)),
        note="madurez ponderada",
    )
    _metric_card(
        doc,
        x=x1,
        y_top=card_top,
        width=card_w,
        title="Puntaje objetivo",
        value=format_decimal(result.get("target_score", 0)),
        note=f"nivel {format_integer(result.get('target_level_index', 0))}",
    )
    _metric_card(
        doc,
        x=x2,
        y_top=card_top,
        width=card_w,
        title="Brecha total",
        value=format_decimal(to_float(result.get("target_score", 0)) - to_float(result.get("current_score", 0))),
        note="Objetivo - actual",
    )
    _metric_card(
        doc,
        x=x3,
        y_top=card_top,
        width=card_w,
        title="Avance a la meta",
        value=format_percentage(_progress_to_target_pct(to_float(result.get("current_score", 0)), to_float(result.get("target_score", 0)))),
        note="Actual / objetivo",
    )
    doc.current_y = card_top - 84

    doc.add_section_header("Brecha por dominio")
    domains = result.get("domain_results", []) if isinstance(result, dict) else []
    if not domains:
        doc.add_text("No hay dominios para mostrar.", size=10)
    else:
        for row in domains:
            label = str(row.get("domain", ""))
            current = float(row.get("current_score", 0))
            target = float(row.get("target_score", 0))
            gap = float(row.get("gap", 0))
            doc.add_kpi_bar(label=label, current=current, target=target, gap=gap)

    doc.add_section_header("KPI críticos priorizados")
    kpis = result.get("kpi_results", []) if isinstance(result, dict) else []
    if not kpis:
        doc.add_text("No se detectaron brechas para el nivel objetivo seleccionado.", size=10)
    else:
        for i, row in enumerate(kpis[:60], start=1):
            doc.add_text(
                f"{i}. {row.get('kpi', '')} [{row.get('domain', '')} / {row.get('kda', '')}]",
                size=10.2,
                bold=True,
                color=PALETTE["forest_dark"],
                gap_after=0.0,
            )
            doc.add_text(
                f"Prioridad {format_decimal(row.get('priority', 0))} | Brecha {format_decimal(row.get('gap', 0))} | {row.get('current_label', '')} -> {row.get('target_label', '')}",
                size=9.1,
                indent=12,
                color=PALETTE["slate"],
                gap_after=0.0,
            )
            doc.add_text(
                f"Respuesta observada: {row.get('selected_option_text', '')}",
                size=9.0,
                indent=12,
                color=PALETTE["muted"],
                gap_after=1.4,
            )

    doc.add_section_header("Roadmap de soluciones")
    entries = result.get("roadmap_entries", []) if isinstance(result, dict) else []
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in entries:
        grouped[str(row.get("plazo", "Sin clasificar"))].append(row)

    any_item = False
    for horizon in HORIZON_ORDER:
        rows = grouped.get(horizon, [])
        if not rows:
            continue
        any_item = True
        doc.add_text(_horizon_label(horizon), size=11.2, bold=True, color=_horizon_color(horizon), gap_after=2.0)
        rows = sorted(rows, key=lambda r: (-float(r.get("priority", 0)), _norm(str(r.get("solution_name", "")))))
        for idx, row in enumerate(rows, start=1):
            doc.add_text(f"{idx}. {_solution_display_name(row)}", size=10.0, bold=True, indent=8, gap_after=0.0)
            doc.add_text(
                f"KPI: {row.get('kpi', '')} | Prioridad: {format_decimal(row.get('priority', 0))} | Precio: {_entry_price_label(row)}",
                size=8.8,
                indent=16,
                color=PALETTE["slate"],
                gap_after=0.0,
            )
            doc.add_text(
                f"Resumen: {_short(str(row.get('solution_description', '')))}",
                size=8.8,
                indent=16,
                color=PALETTE["muted"],
                gap_after=1.4,
            )

    if not any_item:
        doc.add_text("No hay acciones roadmap para este escenario.", size=10.0)

    _render_budget_table(
        doc,
        entries,
        title="Presupuesto estimado por etapa",
        accent=PALETTE["forest_dark"],
        note="Nota: el total considera solo precios en CLP verificables. Las acciones con costo no confirmado se reportan como 'Sin dato' y requieren cotización.",
    )
    _append_30_60_90_page(doc, entries, company_name=str(company.get("name", "Empresa")), friendly=False)
    _append_12_month_timeline_page(doc, entries, company_name=str(company.get("name", "Empresa")), friendly=False)

    doc.save(output_path)


def export_friendly_pdf(payload: dict[str, object], output_path: Path) -> None:
    company = payload.get("company", {}) if isinstance(payload, dict) else {}
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    entries = result.get("roadmap_entries", []) if isinstance(result, dict) else []
    entries = sorted(entries, key=lambda r: (_horizon_order(str(r.get("plazo", ""))), -float(r.get("priority", 0))))
    quick_wins = entries[:3]
    quick_win_keys = {_entry_key(item) for item in quick_wins}
    current_score = float(result.get("current_score", 0))
    target_score = float(result.get("target_score", 0))
    gap_total = target_score - current_score

    doc = SimplePdf()
    doc.add_banner(
        "ROADMAP DE MEJORA TECNOLÓGICA",
        f"{company.get('name', '')} | {company.get('company_type', '')} | {format_timestamp(result.get('timestamp', ''))}",
    )
    _render_friendly_summary(
        doc,
        entries,
        current_score=current_score,
        target_score=target_score,
        gap_total=gap_total,
    )
    _render_budget_table(
        doc,
        entries,
        title="Presupuesto por etapa",
        accent=PALETTE["olive"],
        note="Tip: usa esta tabla para armar caja trimestral. Si una fila no tiene valor informado, cotízala antes de calendarizar.",
    )

    doc.add_section_header("Acciones de impacto inmediato", accent=PALETTE["forest"])
    if not quick_wins:
        doc.add_text("No se identificaron acciones para el nivel objetivo seleccionado.", size=10)
    else:
        for i, item in enumerate(quick_wins, start=1):
            horizon = str(item.get("plazo", ""))
            marker = _horizon_color(horizon)
            item_title = f"{i}. {_solution_display_name(item)}"
            item_meta = f"{_horizon_label(horizon)} | KPI: {item.get('kpi', '')} | Valor: {_entry_price_label(item)}"
            urls = _solution_urls(item, max_urls=1)
            item_url = urls[0] if urls else None
            item_desc = f"Descripción: {_brief(str(item.get('solution_description', '')), 170) or 'Descripción no disponible.'}"
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

    short_plan = _build_30_60_90_plan(entries, excluded_keys=quick_win_keys)
    medium_plan_rows = _stage_plan_rows(entries, "Mediano plazo", excluded_keys=quick_win_keys)
    long_plan_rows = _stage_plan_rows(entries, "Largo plazo", excluded_keys=quick_win_keys)
    _validate_friendly_plan_distribution(entries, quick_win_keys, short_plan, medium_plan_rows, long_plan_rows)

    _append_30_60_90_page(
        doc,
        entries,
        company_name=str(company.get("name", "Empresa")),
        friendly=True,
        excluded_keys=quick_win_keys,
        plan_override=short_plan,
    )
    _append_stage_plan_page(
        doc,
        entries,
        company_name=str(company.get("name", "Empresa")),
        stage="Mediano plazo",
        title="Plan de Mediano Plazo",
        subtitle="Secuencia sugerida para implementar soluciones de Mediano plazo",
        intro="Este plan propone una secuencia accionable para pasar del diagnóstico a implementación de soluciones de Mediano plazo.",
        buckets=[
            (
                "Meses 3-4 | Preparación operativa",
                "Objetivo: instalar capacidades base y coordinar recursos para ejecución sostenida.",
                PALETTE["medium"],
            ),
            (
                "Meses 4-5 | Implementación central",
                "Objetivo: ejecutar soluciones troncales y controlar adopción con seguimiento quincenal.",
                PALETTE["olive"],
            ),
            (
                "Meses 5-6 | Cierre de etapa",
                "Objetivo: estabilizar resultados, cerrar brechas pendientes y dejar traspaso a largo plazo.",
                PALETTE["long"],
            ),
        ],
        excluded_keys=quick_win_keys,
        stage_rows_override=medium_plan_rows,
    )
    _append_stage_plan_page(
        doc,
        entries,
        company_name=str(company.get("name", "Empresa")),
        stage="Largo plazo",
        title="Plan de Largo Plazo",
        subtitle="Secuencia sugerida para implementar soluciones de Largo plazo",
        intro="Este plan propone una secuencia accionable para pasar del diagnóstico a implementación de soluciones de Largo plazo.",
        buckets=[
            (
                "Meses 6-8 | Escalamiento inicial",
                "Objetivo: activar iniciativas de expansión y alinear gobernanza para crecimiento controlado.",
                PALETTE["long"],
            ),
            (
                "Meses 8-10 | Integración y optimización",
                "Objetivo: integrar soluciones desplegadas, optimizar procesos y elevar trazabilidad.",
                PALETTE["olive"],
            ),
            (
                "Meses 10-12 | Consolidación",
                "Objetivo: cerrar ciclo anual con estándares definidos y backlog estratégico validado.",
                PALETTE["forest_dark"],
            ),
        ],
        excluded_keys=quick_win_keys,
        stage_rows_override=long_plan_rows,
    )
    _append_backlog_page(doc, entries, company_name=str(company.get("name", "Empresa")))
    doc.save(output_path)
