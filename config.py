"""Configuration par variables d'environnement (voir BRIEF.md §Config)."""

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    upstream_base_url: str
    enable_rpps: bool
    enable_adeli: bool
    enable_siren_siret: bool
    upstream_timeout_s: float
    port: int
    audit_log_file: str | None


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        upstream_base_url=os.environ.get(
            "UPSTREAM_BASE_URL", "https://api.anthropic.com"
        ).rstrip("/"),
        enable_rpps=_bool_env("ENABLE_RPPS", True),
        enable_adeli=_bool_env("ENABLE_ADELI", True),
        enable_siren_siret=_bool_env("ENABLE_SIREN_SIRET", True),
        upstream_timeout_s=float(os.environ.get("UPSTREAM_TIMEOUT_S", "120")),
        port=int(os.environ.get("PORT", "8080")),
        audit_log_file=os.environ.get("AUDIT_LOG_FILE"),
    )
