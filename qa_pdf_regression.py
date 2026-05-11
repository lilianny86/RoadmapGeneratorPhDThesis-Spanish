from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


BASELINE_PATH = Path("qa_baselines/pdf_baseline.json")

SCENARIOS = [
    {
        "name": "small",
        "args": [
            "--company-type",
            "small",
            "--target-level",
            "3",
            "--answers-file",
            "examples/answers_small.json",
            "--company-name",
            "QA Baseline Small",
            "--output-pdf-tech",
            "outputs/qa_small_tecnico.pdf",
            "--output-pdf-friendly",
            "outputs/qa_small_amigable.pdf",
            "--output-json",
            "outputs/qa_small.json",
            "--output-txt",
            "outputs/qa_small.txt",
        ],
        "pdfs": [
            "outputs/qa_small_tecnico.pdf",
            "outputs/qa_small_amigable.pdf",
        ],
    },
    {
        "name": "medium",
        "args": [
            "--company-type",
            "medium",
            "--target-level",
            "4",
            "--answers-file",
            "examples/answers_medium.json",
            "--company-name",
            "QA Baseline Medium",
            "--output-pdf-tech",
            "outputs/qa_medium_tecnico.pdf",
            "--output-pdf-friendly",
            "outputs/qa_medium_amigable.pdf",
            "--output-json",
            "outputs/qa_medium.json",
            "--output-txt",
            "outputs/qa_medium.txt",
        ],
        "pdfs": [
            "outputs/qa_medium_tecnico.pdf",
            "outputs/qa_medium_amigable.pdf",
        ],
    },
]

REQUIRED_TOKENS = [
    "ROADMAP T\u00c9CNICO DE MADUREZ",
    "TU ROADMAP DE MEJORA TECNOL\u00d3GICA",
    "Plan de Arranque 90 d\u00edas",
    "CRONOGRAMA 12 MESES",
]


def _run_command(root: Path, args: list[str]) -> None:
    cmd = [sys.executable, "run_roadmap.py", *args]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Fallo run_roadmap: {proc.stdout}\n{proc.stderr}")


def _collect_metrics(root: Path) -> dict[str, dict[str, int]]:
    metrics: dict[str, dict[str, int]] = {}
    for scenario in SCENARIOS:
        for rel in scenario["pdfs"]:
            pdf = root / rel
            if not pdf.exists():
                raise RuntimeError(f"No existe PDF esperado: {pdf}")
            content = pdf.read_bytes()
            metrics[rel] = {"size": len(content)}
    return metrics


def _extract_pdf_text(pdf_path: Path) -> str:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        # Fallback sin dependencia externa.
        return pdf_path.read_bytes().decode("latin-1", "ignore")


def _check_tokens(root: Path) -> list[str]:
    missing: list[str] = []
    merged_text: list[str] = []
    for scenario in SCENARIOS:
        for rel in scenario["pdfs"]:
            merged_text.append(_extract_pdf_text(root / rel))
    text = "\n".join(merged_text)
    for token in REQUIRED_TOKENS:
        if token not in text:
            missing.append(token)
    return missing


def _compare_against_baseline(current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]) -> list[str]:
    issues: list[str] = []
    for rel, data in current.items():
        if rel not in baseline:
            issues.append(f"Falta en baseline: {rel}")
            continue
        cur_size = int(data["size"])
        base_size = int(baseline[rel]["size"])
        if base_size <= 0:
            continue
        delta = abs(cur_size - base_size) / base_size
        if delta > 0.35:
            issues.append(f"Tama\u00f1o fuera de umbral en {rel}: baseline={base_size}, actual={cur_size}, delta={delta:.2%}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="QA-02 PDF regression baseline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    for scenario in SCENARIOS:
        _run_command(root, scenario["args"])

    missing_tokens = _check_tokens(root)
    if missing_tokens:
        print("[QA-02] Faltan secciones clave en PDFs:", ", ".join(missing_tokens))
        return 2

    current = _collect_metrics(root)
    baseline_path = root / BASELINE_PATH

    if args.update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[QA-02] Baseline actualizado en: {baseline_path}")
        return 0

    if not baseline_path.exists():
        print(f"[QA-02] No existe baseline. Ejecuta con --update-baseline primero: {baseline_path}")
        return 3

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    issues = _compare_against_baseline(current, baseline)
    if issues:
        print("[QA-02] Regresi\u00f3n detectada:")
        for row in issues:
            print(f"[QA-02] - {row}")
        return 4

    print("[QA-02] Regresi\u00f3n PDF OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
