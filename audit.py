"""Log d'audit : horodatage, types de PII détectés, compte par type, latence.

JAMAIS les valeurs, ni le prompt, ni la réponse, ni le mapping.
Sortie : stdout (toujours) + fichier optionnel (AUDIT_LOG_FILE).
"""

import json
import logging
import sys
from datetime import datetime, timezone

_logger = logging.getLogger("voile.audit")
_logger.setLevel(logging.INFO)
_logger.propagate = False


def configure(audit_log_file: str | None) -> None:
    """(Re)configure les handlers — idempotent."""
    _logger.handlers.clear()
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(stream)
    if audit_log_file:
        file_handler = logging.FileHandler(audit_log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(file_handler)


def log_request(pii_counts: dict[str, int], latency_ms: float, status_code: int) -> None:
    """Une ligne JSON par requête. Uniquement des métadonnées, aucune valeur."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "request",
        "status": status_code,
        "latency_ms": round(latency_ms, 1),
        "pii_types": sorted(pii_counts),
        "pii_counts": dict(sorted(pii_counts.items())),
    }
    _logger.info(json.dumps(entry, ensure_ascii=False))
