"""
Module de Piste d'Audit (Audit Trail)
Permet d'enregistrer les événements système pour la conformité et l'analyse.
"""
import json
from .db import save_audit_log, get_audit_logs

def log_event(event_type: str, severity: str, message: str, details: dict = None):
    """
    Enregistre un événement dans la piste d'audit.
    event_type: 'CONFIG_CHANGE', 'ALERT', 'RECOMMENDATION', 'SYSTEM'
    severity: 'INFO', 'WARNING', 'CRITICAL'
    """
    details_str = json.dumps(details) if details else None
    save_audit_log(event_type, severity, message, details_str)
    print(f"[AUDIT] [{severity}] {event_type}: {message}")

def fetch_logs(limit: int = 100):
    """Récupère les derniers logs d'audit."""
    return get_audit_logs(limit)
