"""
Persistance SQLite — historique du lag avec support multi-cluster.
Nouvelle colonne : cluster_name
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from .config_loader import CONFIG

DB_PATH = Path(__file__).parent.parent / "lag_history.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lag_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT    NOT NULL DEFAULT 'default',
                group_id     TEXT    NOT NULL,
                topic        TEXT    NOT NULL,
                total_lag    INTEGER NOT NULL,
                status       TEXT    NOT NULL,
                group_state  TEXT    NOT NULL DEFAULT 'Unknown',
                recorded_at  TEXT    NOT NULL
            )
        """)
        # Migration pour les bases existantes
        try:
            conn.execute("ALTER TABLE lag_history ADD COLUMN group_state TEXT NOT NULL DEFAULT 'Unknown'")
        except Exception:
            pass

def save_lag(cluster_name: str, group_id: str, topic: str,
             total_lag: int, status: str, group_state: str = "Unknown"):
    now = datetime.utcnow().isoformat()
    with _get_connection() as conn:
        conn.execute(
            """INSERT INTO lag_history
               (cluster_name, group_id, topic, total_lag, status, group_state, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cluster_name, group_id, topic, total_lag, status, group_state, now)
        )
        conn.commit()
        

def get_lag_history(cluster_name: str, group_id: str, topic: str, last_hours: int = 1) -> list[dict]:
    since = (datetime.utcnow() - timedelta(hours=last_hours)).isoformat()
    with _get_connection() as conn:
        rows = conn.execute(
            """SELECT recorded_at, total_lag, status FROM lag_history
               WHERE cluster_name=? AND group_id=? AND topic=? AND recorded_at>=?
               ORDER BY recorded_at ASC""",
            (cluster_name, group_id, topic, since)
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_per_group(cluster_name: str = None) -> list[dict]:
    with _get_connection() as conn:
        if cluster_name:
            rows = conn.execute(
                """SELECT cluster_name, group_id, topic, total_lag, status, group_state,
                          MAX(recorded_at) as recorded_at
                   FROM lag_history WHERE cluster_name=?
                   GROUP BY cluster_name, group_id, topic
                   ORDER BY total_lag DESC""",
                (cluster_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT cluster_name, group_id, topic, total_lag, status, group_state,
                          MAX(recorded_at) as recorded_at
                   FROM lag_history
                   GROUP BY cluster_name, group_id, topic
                   ORDER BY cluster_name, total_lag DESC"""
            ).fetchall()
    return [dict(row) for row in rows]


def purge_old_records():
    retention = CONFIG["monitor"]["history_retention_days"]
    cutoff = (datetime.utcnow() - timedelta(days=retention)).isoformat()
    with _get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM lag_history WHERE recorded_at < ?",
            (cutoff,)
        ).rowcount
        conn.commit()
    return deleted