"""Step 3: SQLite 資料庫存取。"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

TW_TZ = timezone(timedelta(hours=8))  # 雲端主機多為 UTC，統一使用台灣時間

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "weather.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast (
    county     TEXT NOT NULL,
    region     TEXT NOT NULL,
    date       TEXT NOT NULL,
    min_temp   REAL,
    max_temp   REAL,
    pop        REAL,
    humidity   REAL,
    weather    TEXT,
    lat        REAL,
    lon        REAL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (county, date)
);
"""


def now_tw() -> datetime:
    """台灣時間（不含時區資訊，方便與資料庫中的字串比較）。"""
    return datetime.now(TW_TZ).replace(tzinfo=None)


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def save_forecast(rows: list, db_path: Path = DB_PATH) -> int:
    """寫入（同縣市同日期則覆蓋更新），回傳筆數。"""
    now = now_tw().isoformat(timespec="seconds")
    with get_conn(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO forecast
               (county, region, date, min_temp, max_temp, pop, humidity, weather, lat, lon, updated_at)
               VALUES (:county, :region, :date, :min_temp, :max_temp, :pop, :humidity, :weather, :lat, :lon, :updated_at)""",
            [{**r, "updated_at": now} for r in rows],
        )
    return len(rows)


def load_forecast(db_path: Path = DB_PATH) -> pd.DataFrame:
    with get_conn(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM forecast ORDER BY date, region, county", conn)


def last_updated(db_path: Path = DB_PATH):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT MAX(updated_at) FROM forecast").fetchone()[0]
