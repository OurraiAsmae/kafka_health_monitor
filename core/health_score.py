"""
Health Score Global — score de 0 à 100 résumant la santé de tous les clusters.

FORMULE :
    score = 100
    - penalite_critical  (jusqu'à -60 points)
    - penalite_warning   (jusqu'à -25 points)
    - penalite_etat      (jusqu'à -15 points)

INTERPRETATION :
    90-100 : Excellent
    70-89  : Bon
    50-69  : Moyen
    30-49  : Mauvais
    0-29   : Critique
"""
from .config_loader import CONFIG


def _compute_single_score(results: list) -> int:
    """
    Calcule un score brut pour une liste de résultats.
    Fonction interne sans recursion — utilisée pour les scores par cluster.
    """
    if not results:
        return 100

    total   = len(results)
    n_crit  = sum(1 for r in results if r.status == "CRITICAL")
    n_warn  = sum(1 for r in results if r.status == "WARNING")
    n_empty = sum(1 for r in results if getattr(r, "group_state", "") in ("Empty", "Dead"))

    penalty = (
        round((n_crit  / total) * 60) +
        round((n_warn  / total) * 25) +
        round((n_empty / total) * 15)
    )
    return max(0, min(100, 100 - penalty))


def _grade(score: int) -> tuple[str, str]:
    """Retourne le grade et la couleur associés au score."""
    if score >= 90: return "Excellent", "#22c55e"
    if score >= 70: return "Bon",       "#4ade80"
    if score >= 50: return "Moyen",     "#facc15"
    if score >= 30: return "Mauvais",   "#fb923c"
    return             "Critique",  "#f87171"


def _empty_score() -> dict:
    return {
        "score": 100, "grade": "Aucune donnee", "color": "#64748b",
        "total_groups": 0, "n_critical": 0, "n_warning": 0,
        "n_ok": 0, "n_empty": 0,
        "details": {
            "penalty_critical": 0, "penalty_warning": 0, "penalty_state": 0,
            "pct_critical": 0.0, "pct_warning": 0.0,
        },
        "by_cluster": [],
    }


def compute_health_score(results: list) -> dict:
    """
    Calcule le Health Score global à partir des résultats de lag.
    Utilise _compute_single_score pour les clusters — pas de recursion.
    """
    if not results:
        return _empty_score()

    total   = len(results)
    n_crit  = sum(1 for r in results if r.status == "CRITICAL")
    n_warn  = sum(1 for r in results if r.status == "WARNING")
    n_empty = sum(1 for r in results if getattr(r, "group_state", "") in ("Empty", "Dead"))

    pct_crit  = n_crit  / total if total > 0 else 0
    pct_warn  = n_warn  / total if total > 0 else 0
    pct_empty = n_empty / total if total > 0 else 0

    penalty_critical = round(pct_crit  * 60)
    penalty_warning  = round(pct_warn  * 25)
    penalty_state    = round(pct_empty * 15)

    score = max(0, min(100, 100 - penalty_critical - penalty_warning - penalty_state))
    grade, color = _grade(score)

    # Scores par cluster — utilise _compute_single_score sans recursion
    cluster_map: dict[str, list] = {}
    for r in results:
        cluster_map.setdefault(r.cluster_name, []).append(r)

    by_cluster = []
    for cname, clist in cluster_map.items():
        by_cluster.append({
            "cluster_name": cname,
            "score":      _compute_single_score(clist),
            "n_critical": sum(1 for r in clist if r.status == "CRITICAL"),
            "n_warning":  sum(1 for r in clist if r.status == "WARNING"),
            "n_ok":       sum(1 for r in clist if r.status == "OK"),
            "total":      len(clist),
        })

    return {
        "score":        score,
        "grade":        grade,
        "color":        color,
        "total_groups": total,
        "n_critical":   n_crit,
        "n_warning":    n_warn,
        "n_ok":         total - n_crit - n_warn,
        "n_empty":      n_empty,
        "details": {
            "penalty_critical": penalty_critical,
            "penalty_warning":  penalty_warning,
            "penalty_state":    penalty_state,
            "pct_critical":     round(pct_crit  * 100, 1),
            "pct_warning":      round(pct_warn  * 100, 1),
        },
        "by_cluster": by_cluster,
    }