"""
Intelligent Recommendation Engine — Operational Excellence.
Analyze lag trend, consumer group state, and historical data to provide proactive advice.
"""
from typing import List, Dict, Optional
from datetime import datetime
from .config_loader import CONFIG
from .forecasting import forecast_lag

def get_recommendations() -> List[Dict]:
    """
    Analyzes current state and returns human-readable recommendations.
    """
    from .db import get_latest_per_group
    rows = get_latest_per_group()
    
    recommendations = []
    
    for row in rows:
        cluster = row["cluster_name"]
        group_id = row["group_id"]
        topic = row["topic"]
        current_lag = row["total_lag"]
        state = row["group_state"]
        
        # Get trend analysis
        forecast = forecast_lag(cluster, group_id, topic)
        trend = forecast.get("trend", "STABLE")
        
        rec = analyze_row(cluster, group_id, topic, current_lag, state, trend, forecast)
        if rec:
            recommendations.append(rec)
            
    # Sort by severity: CRITICAL first, then WARNING, then INFO
    severity_map = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    recommendations.sort(key=lambda x: severity_map.get(x["severity"], 99))
    
    # Limit to top 3 most critical
    return recommendations[:3]

def analyze_row(cluster, group_id, topic, current_lag, state, trend, forecast) -> Optional[Dict]:
    """
    Internal logic to generate advice based on state and trend.
    """
    # 1. Under-provisioned: Lag is increasing and group is stable
    if trend == "INCREASING" and state == "STABLE":
        return {
            "id": f"{cluster}-{group_id}-{topic}-under",
            "cluster": cluster,
            "group_id": group_id,
            "topic": topic,
            "type": "PERFORMANCE",
            "severity": "WARNING",
            "title": "Under-provisioned Consumer",
            "advice": f"Consumer count for topic '{topic}' might be too low. Lag is increasing at {forecast.get('slope_per_min', 0)} msgs/min despite STABLE group state.",
            "action": "Consider increasing consumer count or optimizing processing logic."
        }

    # 2. Inactive group with lag
    if current_lag > CONFIG["alerts"]["warning_threshold"] and state in ["EMPTY", "DEAD"]:
        return {
            "id": f"{cluster}-{group_id}-{topic}-offline",
            "cluster": cluster,
            "group_id": group_id,
            "topic": topic,
            "type": "AVAILABILITY",
            "severity": "CRITICAL",
            "title": "Consumers Offline",
            "advice": f"Significant lag ({current_lag}) detected for group '{group_id}', but no active consumers are connected.",
            "action": "Restart consumer instances to process pending messages."
        }

    # 3. High Lag with Stable Trend (Stalled?)
    if current_lag > CONFIG["alerts"]["critical_threshold"] and trend == "STABLE" and state == "STABLE":
        return {
            "id": f"{cluster}-{group_id}-{topic}-stalled",
            "cluster": cluster,
            "group_id": group_id,
            "topic": topic,
            "type": "STABILITY",
            "severity": "CRITICAL",
            "title": "Possible Processing Bottleneck",
            "advice": f"High stable lag ({current_lag}) detected. Consumers are active but not reducing the backlog.",
            "action": "Investigate if consumers are hung or if processing time per message has increased."
        }

    # 4. Rebalancing instability
    if state in ["PREPARING_REBALANCE", "COMPLETING_REBALANCE"]:
        return {
            "id": f"{cluster}-{group_id}-{topic}-rebalance",
            "cluster": cluster,
            "group_id": group_id,
            "topic": topic,
            "type": "STABILITY",
            "severity": "INFO",
            "title": "Group Rebalancing",
            "advice": f"Group '{group_id}' is currently rebalancing.",
            "action": "Monitoring stability. If this persists, check for network issues or consumer churn."
        }

    return None
