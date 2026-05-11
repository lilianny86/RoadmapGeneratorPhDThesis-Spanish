from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


ENV_KEYS = {
    "require_smtp": "ROADMAP_REQUIRE_SMTP",
    "smtp_host": "ROADMAP_SMTP_HOST",
    "smtp_port": "ROADMAP_SMTP_PORT",
    "smtp_user": "ROADMAP_SMTP_USER",
    "smtp_password": "ROADMAP_SMTP_PASSWORD",
    "smtp_from": "ROADMAP_SMTP_FROM",
    "smtp_to": "ROADMAP_SMTP_TO",
}

PLACEHOLDER_MARKERS = {
    "",
    "change_me",
    "placeholder",
    "tu_password",
    "password",
    "reemplazar_con_secreto",
    "replace_with_secret",
}

SCAN_EXTENSIONS = {".py", ".txt", ".md", ".json", ".yaml", ".yml", ".ini", ".toml", ".env"}
SCAN_EXCLUDE_DIRS = {"outputs", "__pycache__", ".git", ".venv", "venv"}

HARD_CODED_PATTERNS = [
    re.compile(r"(?i)smtp[_-]?password\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)token\s*[:=]\s*['\"][^'\"]+['\"]"),
]


@dataclass
class SecurityConfig:
    require_smtp: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_to: str


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clean_env_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    return value


def load_dotenv_if_present(root: Path) -> Path | None:
    env_path = root / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, _clean_env_value(value))
    return env_path


def load_security_config(root: Path) -> tuple[SecurityConfig, Path | None]:
    env_file = load_dotenv_if_present(root)
    port_raw = os.getenv(ENV_KEYS["smtp_port"], "587")
    try:
        smtp_port = int(port_raw)
    except ValueError:
        smtp_port = 587

    cfg = SecurityConfig(
        require_smtp=_parse_bool(os.getenv(ENV_KEYS["require_smtp"]), default=False),
        smtp_host=os.getenv(ENV_KEYS["smtp_host"], "").strip(),
        smtp_port=smtp_port,
        smtp_user=os.getenv(ENV_KEYS["smtp_user"], "").strip(),
        smtp_password=os.getenv(ENV_KEYS["smtp_password"], "").strip(),
        smtp_from=os.getenv(ENV_KEYS["smtp_from"], "").strip(),
        smtp_to=os.getenv(ENV_KEYS["smtp_to"], "").strip(),
    )
    return cfg, env_file


def validate_smtp_config(cfg: SecurityConfig, *, strict: bool = False) -> list[str]:
    errors: list[str] = []

    if not strict and not cfg.require_smtp:
        return errors

    required = {
        "ROADMAP_SMTP_HOST": cfg.smtp_host,
        "ROADMAP_SMTP_USER": cfg.smtp_user,
        "ROADMAP_SMTP_PASSWORD": cfg.smtp_password,
        "ROADMAP_SMTP_FROM": cfg.smtp_from,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        errors.append("Faltan variables SMTP requeridas: " + ", ".join(missing))

    if not (1 <= cfg.smtp_port <= 65535):
        errors.append("ROADMAP_SMTP_PORT está fuera de rango (1-65535).")

    secret_marker = cfg.smtp_password.strip().lower()
    if secret_marker in PLACEHOLDER_MARKERS:
        errors.append("ROADMAP_SMTP_PASSWORD tiene un valor de placeholder; debe rotarse y reemplazarse.")

    return errors


def scan_hardcoded_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(content.splitlines(), start=1):
            for pattern in HARD_CODED_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path}:{idx} -> posible secreto hardcodeado")
                    break
    return findings

