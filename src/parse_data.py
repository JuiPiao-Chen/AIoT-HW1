"""Step 2: 解析 CWA JSON，整理成「縣市 x 日期」的每日預報。"""
from collections import defaultdict

# 參考 CWA 農業氣象預報的六大分區；離島縣市另列「離島」
REGION_OF = {
    "基隆市": "北部", "臺北市": "北部", "新北市": "北部", "桃園市": "北部", "新竹市": "北部", "新竹縣": "北部",
    "苗栗縣": "中部", "臺中市": "中部", "彰化縣": "中部", "南投縣": "中部", "雲林縣": "中部",
    "嘉義市": "南部", "嘉義縣": "南部", "臺南市": "南部", "高雄市": "南部", "屏東縣": "南部",
    "宜蘭縣": "東北部",
    "花蓮縣": "東部",
    "臺東縣": "東南部",
    "澎湖縣": "離島", "金門縣": "離島", "連江縣": "離島",
}
REGION_ORDER = ["北部", "中部", "南部", "東北部", "東部", "東南部", "離島"]

# 各元素在 ElementValue 內對應的欄位名
_FIELDS = {
    "最高溫度": "MaxTemperature",
    "最低溫度": "MinTemperature",
    "12小時降雨機率": "ProbabilityOfPrecipitation",
    "天氣現象": "Weather",
    "平均相對濕度": "RelativeHumidity",
}


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None  # CWA 缺值常以 "-" 表示


def parse_forecast(data: dict) -> list:
    """回傳 list[dict]，每筆為一個縣市某一天的預報。

    一天有白天/晚上兩個 12 小時時段：最低溫取兩時段最小值、最高溫取最大值，
    降雨機率取最大值，天氣現象取當天第一個時段（通常為白天）。
    """
    rows = []
    for loc in data["records"]["Locations"][0]["Location"]:
        name = loc["LocationName"]
        # daily[date][element] = list of values（依時間排序）
        daily = defaultdict(lambda: defaultdict(list))
        for elem in loc["WeatherElement"]:
            field = _FIELDS.get(elem["ElementName"])
            if not field:
                continue
            for t in elem["Time"]:
                date = t["StartTime"][:10]
                daily[date][field].append(t["ElementValue"][0].get(field))

        for date in sorted(daily):
            d = daily[date]
            mins = [x for x in map(_to_num, d["MinTemperature"]) if x is not None]
            maxs = [x for x in map(_to_num, d["MaxTemperature"]) if x is not None]
            pops = [x for x in map(_to_num, d["ProbabilityOfPrecipitation"]) if x is not None]
            hums = [x for x in map(_to_num, d["RelativeHumidity"]) if x is not None]
            rows.append({
                "county": name,
                "region": REGION_OF.get(name, "其他"),
                "date": date,
                "min_temp": min(mins) if mins else None,
                "max_temp": max(maxs) if maxs else None,
                "pop": max(pops) if pops else None,
                "humidity": round(sum(hums) / len(hums)) if hums else None,
                "weather": d["Weather"][0] if d["Weather"] else None,
                "lat": float(loc["Latitude"]),
                "lon": float(loc["Longitude"]),
            })
    return rows
