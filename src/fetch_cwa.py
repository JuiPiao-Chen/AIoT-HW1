"""Step 1: 呼叫 CWA 開放資料 API，取得「臺灣各縣市未來1週逐12小時天氣預報」(F-D0047-091)。"""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091"
RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw_F-D0047-091.json"

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_api_key() -> str:
    key = os.getenv("CWA_API_KEY")
    if not key:
        raise RuntimeError("找不到 CWA_API_KEY，請在 .env 中設定（參考 .env.example）")
    return key


def fetch_forecast(save_raw: bool = True) -> dict:
    """下載一週縣市預報 JSON，並（可選）存一份原始檔到 data/。"""
    resp = requests.get(API_URL, params={"Authorization": get_api_key(), "format": "JSON"}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("success") != "true":
        raise RuntimeError(f"CWA API 回傳失敗: {data}")
    if save_raw:
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        RAW_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    d = fetch_forecast()
    locs = d["records"]["Locations"][0]["Location"]
    print(f"取得 {len(locs)} 個縣市資料，已存到 {RAW_PATH}")
