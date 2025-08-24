import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.environ.get("COST_TRACKER_DB", os.path.join(os.path.dirname(__file__), "costs.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL, -- 'groq' | 'gemini'
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    calls INTEGER NOT NULL DEFAULT 1,
    cost REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_usage_created_at ON usage(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage(provider);
CREATE INDEX IF NOT EXISTS idx_usage_user_provider ON usage(user_id, provider);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_usage(record: Dict[str, Any]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO usage (user_id, provider, model, input_tokens, output_tokens, calls, cost, created_at)
            VALUES (:user_id, :provider, :model, :input_tokens, :output_tokens, :calls, :cost, COALESCE(:created_at, datetime('now')))
            """,
            record,
        )
        return cur.lastrowid


def recent_usage(limit: int = 50) -> List[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM usage
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def aggregate_summary(start_iso: Optional[str], end_iso: Optional[str]) -> Dict[str, Any]:
    with get_conn() as conn:
        where = []
        params: Tuple[Any, ...] = tuple()
        if start_iso:
            where.append("created_at >= ?")
            params += (start_iso,)
        if end_iso:
            where.append("created_at < ?")
            params += (end_iso,)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        # totals
        total = conn.execute(
            f"SELECT COALESCE(SUM(cost),0.0) AS cost, COALESCE(SUM(input_tokens+output_tokens),0) AS tokens, COALESCE(SUM(calls),0) AS calls FROM usage{where_sql}",
            params,
        ).fetchone()

        # by provider
        by_provider_rows = conn.execute(
            f"SELECT provider, COALESCE(SUM(cost),0.0) AS cost, COALESCE(SUM(input_tokens+output_tokens),0) AS tokens, COALESCE(SUM(calls),0) AS calls FROM usage{where_sql} GROUP BY provider",
            params,
        ).fetchall()
        by_provider = {row["provider"]: {"cost": row["cost"], "tokens": row["tokens"], "calls": row["calls"]} for row in by_provider_rows}

        return {
            "total": {"cost": total["cost"], "tokens": total["tokens"], "calls": total["calls"]},
            "by_provider": by_provider,
        }


def timeseries(granularity: str = "day", days: int = 7, provider: Optional[str] = None) -> List[Dict[str, Any]]:
    granularity = granularity.lower()
    if granularity not in ("hour", "day"):
        granularity = "day"

    with get_conn() as conn:
        group_fmt = "%Y-%m-%d" if granularity == "day" else "%Y-%m-%d %H:00"
        where = ["created_at >= datetime('now', ?)"]
        params: Tuple[Any, ...] = (f"-{days} days",)
        if provider:
            where.append("provider = ?")
            params += (provider,)
        where_sql = " WHERE " + " AND ".join(where)

        cur = conn.execute(
            f"""
            SELECT strftime('{group_fmt}', created_at) AS bucket,
                   COALESCE(SUM(cost),0.0) AS cost,
                   COALESCE(SUM(input_tokens+output_tokens),0) AS tokens,
                   COALESCE(SUM(calls),0) AS calls
            FROM usage
            {where_sql}
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            params,
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def period_bounds(period: str) -> Tuple[Optional[str], Optional[str]]:
    period = period.lower()
    if period == "day":
        start = "date('now')"
        end = "date('now','+1 day')"
    elif period == "week":
        start = "date('now','-6 days')"
        end = "date('now','+1 day')"
    elif period == "month":
        start = "date('now','start of month')"
        end = "date('now','start of month','+1 month')"
    else:
        start = None
        end = None

    def eval_expr(expr: Optional[str]) -> Optional[str]:
        if not expr:
            return None
        with get_conn() as conn:
            return conn.execute(f"SELECT {expr} AS d").fetchone()["d"]

    return eval_expr(start), eval_expr(end)
