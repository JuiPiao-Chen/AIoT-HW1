"""一鍵更新：抓取 CWA 資料 → 解析 → 存入 SQLite。

用法: python update_data.py
"""
from src.db import DB_PATH, save_forecast
from src.fetch_cwa import fetch_forecast
from src.parse_data import parse_forecast


def update() -> int:
    return save_forecast(parse_forecast(fetch_forecast()))


if __name__ == "__main__":
    n = update()
    print(f"已寫入 {n} 筆每日預報到 {DB_PATH}")
