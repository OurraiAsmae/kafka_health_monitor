"""
Tests du Predictive Lag Forecasting.

On vérifie :
- La régression linéaire sur des données parfaitement linéaires
- Le calcul de l'ETA (temps avant d'atteindre un seuil)
- Les cas limites (données insuffisantes, lag décroissant)
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from core.forecasting import forecast_lag, MIN_POINTS


def _make_records(start_lag: int, slope: int, n: int) -> list[dict]:
    """
    Génère N points de lag parfaitement linéaires.
    Utile pour tester la régression dans des conditions contrôlées.

    EXEMPLE : start_lag=100, slope=50, n=5
    → lag: 100, 150, 200, 250, 300 (toutes les 5 secondes)
    """
    now = datetime.utcnow()
    records = []
    for i in range(n):
        ts = (now - timedelta(seconds=(n - 1 - i) * 5)).isoformat()
        records.append({
            "recorded_at": ts,
            "total_lag": start_lag + slope * i,
            "status": "OK",
        })
    return records


class TestForecastLag:

    def test_insufficient_data_returns_flag(self):
        """Moins de MIN_POINTS points → enough_data=False."""
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(100, 10, MIN_POINTS - 1)
            result = forecast_lag("dev", "my-group", "orders")

        assert result["enough_data"] is False
        assert "reason" in result

    def test_linear_trend_detected(self):
        """
        Sur des données parfaitement linéaires, la régression
        doit détecter une tendance INCREASING avec R² ≈ 1.0.
        """
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(
                start_lag=0, slope=100, n=20
            )
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["enough_data"] is True
        assert result["trend"] == "INCREASING"
        assert result["r_squared"] > 0.99
        assert result["confidence"] == "HIGH"

    def test_stable_trend_detected(self):
        """Lag constant → tendance STABLE."""
        records = _make_records(start_lag=500, slope=0, n=20)
        # Ajoute un peu de bruit pour éviter ss_tot=0
        for i, r in enumerate(records):
            r["total_lag"] += (i % 3)

        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = records
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["enough_data"] is True
        assert result["trend"] == "STABLE"

    def test_decreasing_trend_detected(self):
        """Lag décroissant → tendance DECREASING."""
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(
                start_lag=5000, slope=-100, n=20
            )
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["enough_data"] is True
        assert result["trend"] == "DECREASING"

    def test_eta_critical_already_exceeded(self):
        """Si le lag actuel dépasse déjà le seuil → eta = -1."""
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(
                start_lag=10000, slope=100, n=20
            )
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["eta_critical_sec"] == -1

    def test_prediction_positive_values(self):
        """Les prédictions à +5min et +15min sont toujours >= 0."""
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(
                start_lag=0, slope=50, n=20
            )
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["predicted_lag_5min"]  >= 0
        assert result["predicted_lag_15min"] >= 0

    def test_prediction_grows_with_positive_slope(self):
        """Avec un slope positif, la prédiction à 15min > prédiction à 5min."""
        with patch("core.forecasting.get_lag_history") as mock_db:
            mock_db.return_value = _make_records(
                start_lag=0, slope=100, n=20
            )
            with patch("core.forecasting.CONFIG", {
                "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
                "monitor": {"refresh_interval": 5},
            }):
                result = forecast_lag("dev", "my-group", "orders")

        assert result["predicted_lag_15min"] > result["predicted_lag_5min"]