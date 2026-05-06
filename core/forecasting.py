"""
Predictive Lag Forecasting — régression linéaire sur l'historique SQLite.

PRINCIPE :
    1. On récupère les N derniers points de lag depuis SQLite
    2. On ajuste une droite y = slope * x + intercept (numpy.polyfit)
    3. On calcule quand cette droite atteindra les seuils WARNING et CRITICAL
    4. On retourne une prédiction avec intervalle de confiance simple

LIMITES (à mentionner dans l'article) :
    - Précision limitée si le lag n'est pas linéaire (pics soudains)
    - Nécessite au minimum MIN_POINTS points pour être fiable
    - Indicatif uniquement — pas un modèle de production
"""
import numpy as np
from datetime import datetime
from .db import get_lag_history
from .config_loader import CONFIG

# Nombre minimum de points pour faire une prédiction fiable
MIN_POINTS = 5

# Fenêtre d'historique utilisée pour la régression (en heures)
FORECAST_WINDOW_HOURS = 1


def _parse_timestamp(ts: str) -> float:
    """Convertit un timestamp ISO en secondes depuis epoch."""
    return datetime.fromisoformat(ts).timestamp()


def forecast_lag(
    cluster_name: str,
    group_id: str,
    topic: str,
) -> dict:
    """
    Prédit l'évolution future du lag pour un groupe/topic donné.

    Retourne un dict avec :
    - slope          : vitesse de montée du lag (msgs/seconde)
    - slope_per_min  : vitesse en msgs/minute (plus lisible)
    - eta_warning    : secondes avant d'atteindre le seuil WARNING (-1 si déjà dépassé)
    - eta_critical   : secondes avant d'atteindre le seuil CRITICAL (-1 si déjà dépassé)
    - eta_warning_min  : minutes
    - eta_critical_min : minutes
    - trend          : "INCREASING" | "DECREASING" | "STABLE"
    - confidence     : "HIGH" | "MEDIUM" | "LOW" (basé sur R²)
    - r_squared      : coefficient de détermination (qualité du fit)
    - current_lag    : dernier lag connu
    - predicted_lag_5min  : lag prédit dans 5 minutes
    - predicted_lag_15min : lag prédit dans 15 minutes
    - enough_data    : True si assez de points pour prédire
    """
    warn  = CONFIG["alerts"]["warning_threshold"]
    crit  = CONFIG["alerts"]["critical_threshold"]

    # Récupère l'historique
    records = get_lag_history(
        cluster_name, group_id, topic,
        last_hours=FORECAST_WINDOW_HOURS
    )

    if len(records) < MIN_POINTS:
        return {
            "enough_data": False,
            "reason": f"Seulement {len(records)} points (minimum {MIN_POINTS})",
            "current_lag": records[-1]["total_lag"] if records else 0,
        }

    # Prépare les données pour numpy
    timestamps = np.array([_parse_timestamp(r["recorded_at"]) for r in records])
    lags       = np.array([r["total_lag"] for r in records])

    # Normalise les timestamps (commence à 0) pour éviter les erreurs numériques
    t0 = timestamps[0]
    x  = timestamps - t0
    y  = lags

    # Régression linéaire : y = slope * x + intercept
    coeffs = np.polyfit(x, y, deg=1)
    slope, intercept = coeffs[0], coeffs[1]

    # Calcul du R² (qualité de la régression)
    y_pred   = slope * x + intercept
    ss_res   = np.sum((y - y_pred) ** 2)
    ss_tot   = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Confiance basée sur R²
    if r_squared >= 0.85:
        confidence = "HIGH"
    elif r_squared >= 0.5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Tendance
    if slope > 0.5:
        trend = "INCREASING"
    elif slope < -0.5:
        trend = "DECREASING"
    else:
        trend = "STABLE"

    # Lag actuel (dernier point réel)
    current_lag = int(lags[-1])
    now_offset  = timestamps[-1] - t0

    def eta_seconds(threshold: int) -> int:
        """
        Calcule en combien de secondes le lag atteindra un seuil.
        Retourne -1 si déjà dépassé, -2 si jamais atteint (pente négative).
        """
        if current_lag >= threshold:
            return -1   # déjà dépassé
        if slope <= 0:
            return -2   # lag stable ou décroissant, ne sera jamais atteint
        # t = (threshold - intercept) / slope
        t_reach = (threshold - intercept) / slope
        seconds_from_now = t_reach - now_offset
        return max(0, int(seconds_from_now))

    eta_warn = eta_seconds(warn)
    eta_crit = eta_seconds(crit)

    # Prédictions futures
    t_5min  = now_offset + 5 * 60
    t_15min = now_offset + 15 * 60
    pred_5min  = max(0, int(slope * t_5min  + intercept))
    pred_15min = max(0, int(slope * t_15min + intercept))

    return {
        "enough_data":       True,
        "cluster_name":      cluster_name,
        "group_id":          group_id,
        "topic":             topic,
        "current_lag":       current_lag,
        "slope":             round(slope, 4),
        "slope_per_min":     round(slope * 60, 1),
        "trend":             trend,
        "confidence":        confidence,
        "r_squared":         round(r_squared, 3),
        "eta_warning_sec":   eta_warn,
        "eta_critical_sec":  eta_crit,
        "eta_warning_min":   round(eta_warn / 60, 1) if eta_warn >= 0 else eta_warn,
        "eta_critical_min":  round(eta_crit / 60, 1) if eta_crit >= 0 else eta_crit,
        "predicted_lag_5min":  pred_5min,
        "predicted_lag_15min": pred_15min,
    }


def forecast_all() -> list[dict]:
    """
    Lance la prédiction pour tous les groupes/topics connus en base.
    Appelé par l'endpoint /api/forecast.
    """
    from .db import get_latest_per_group
    rows = get_latest_per_group()

    results = []
    seen = set()
    for row in rows:
        key = (row["cluster_name"], row["group_id"], row["topic"])
        if key in seen:
            continue
        seen.add(key)

        forecast = forecast_lag(
            row["cluster_name"],
            row["group_id"],
            row["topic"],
        )
        results.append(forecast)

    # Tri : INCREASING en premier, puis par eta_critical croissant
    def sort_key(f):
        if not f.get("enough_data"):
            return (3, 0)
        if f["trend"] == "INCREASING":
            eta = f["eta_critical_sec"]
            return (0, eta if eta >= 0 else 999999)
        elif f["trend"] == "STABLE":
            return (1, 0)
        else:
            return (2, 0)

    results.sort(key=sort_key)
    return results