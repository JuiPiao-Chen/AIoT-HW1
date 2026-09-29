"""Step 4: Taiwan Weather Forecast — Streamlit 網頁。

執行: streamlit run app.py
"""
import json
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.db import last_updated, load_forecast
from src.parse_data import REGION_ORDER
from update_data import update

st.set_page_config(page_title="Taiwan Weather Forecast", page_icon="🌤️", layout="wide")

WEEKDAY = "一二三四五六日"
# 分區在地圖上的代表位置（離島取澎湖附近，避免平均座標落在海上）
REGION_POS = {
    "北部": (25.02, 121.45), "中部": (24.10, 120.72), "南部": (22.95, 120.45),
    "東北部": (24.68, 121.75), "東部": (23.80, 121.45), "東南部": (22.85, 121.10),
    "離島": (23.57, 119.60),
}


def fmt(v):
    return "—" if pd.isna(v) else f"{v:.0f}"


def temp_color(t, lo=15.0, hi=38.0):
    """溫度 → RGB（藍 → 黃 → 紅）。"""
    if pd.isna(t):
        return [150, 150, 150]
    x = min(max((t - lo) / (hi - lo), 0.0), 1.0)
    if x < 0.5:
        k = x / 0.5
        return [int(40 + 215 * k), int(120 + 100 * k), int(220 - 170 * k)]
    k = (x - 0.5) / 0.5
    return [255, int(220 - 170 * k), int(50 - 20 * k)]


@st.cache_data(ttl=600)
def get_data() -> pd.DataFrame:
    return load_forecast()


def region_summary(day_df: pd.DataFrame) -> pd.DataFrame:
    """把縣市資料彙整為分區：最低溫取區內最小、最高溫取區內最大。"""
    g = day_df.groupby("region").agg(
        最低溫=("min_temp", "min"),
        最高溫=("max_temp", "max"),
        降雨機率=("pop", "max"),
        天氣=("weather", lambda s: s.mode().iat[0] if not s.mode().empty else ""),
    )
    g = g.reindex([r for r in REGION_ORDER if r in g.index])
    g["lat"] = [REGION_POS[r][0] for r in g.index]
    g["lon"] = [REGION_POS[r][1] for r in g.index]
    g.index.name = "地區"
    return g.reset_index()


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ 資料設定")
    if st.button("🔄 從 CWA 更新資料", width="stretch"):
        with st.spinner("正在向中央氣象署抓取資料..."):
            try:
                n = update()
                get_data.clear()
                st.success(f"已更新 {n} 筆資料")
            except Exception as e:  # noqa: BLE001
                st.error(f"更新失敗：{e}")
    st.caption(f"最後更新：{last_updated() or '尚無資料'}")
    st.caption("資料來源：中央氣象署開放資料平臺 F-D0047-091（臺灣各縣市未來 1 週逐 12 小時天氣預報）")

STALE_AFTER = timedelta(hours=3)  # CWA 一週預報約每 6 小時更新


def data_is_stale() -> bool:
    ts = last_updated()
    return ts is None or datetime.now() - datetime.fromisoformat(ts) > STALE_AFTER


# 資料庫為空（例如 Streamlit Cloud 重啟後）或資料過舊時，自動從 CWA 更新
if data_is_stale():
    with st.spinner("正在從中央氣象署抓取最新資料..."):
        try:
            update()
            get_data.clear()
        except Exception as e:  # noqa: BLE001
            st.warning(f"自動更新失敗，將顯示既有資料：{e}")

df = get_data()
if df.empty:
    st.error("目前沒有任何天氣資料，請確認 CWA_API_KEY 設定是否正確。")
    st.stop()

# ---------------- Header ----------------
st.title("🌤️ Taiwan Weather Forecast")
st.caption("台灣一週天氣預報｜Python × CWA API × SQLite × Streamlit")

dates = sorted(df["date"].unique())
c1, c2 = st.columns([1, 3])
with c1:
    date_labels = {f"{d}（{WEEKDAY[pd.Timestamp(d).weekday()]}）": d for d in dates}
    date = date_labels[st.selectbox("📅 選擇日期", list(date_labels))]
with c2:
    view = st.radio("地圖顯示", ["分區", "縣市"], horizontal=True)

day_df = df[df["date"] == date].copy()
regions = region_summary(day_df)

# ---------------- KPIs ----------------
hot = day_df.loc[day_df["max_temp"].idxmax()]
cold = day_df.loc[day_df["min_temp"].idxmin()]
k1, k2, k3, k4 = st.columns(4)
k1.metric("🔥 全台最高溫", f"{hot.max_temp:.0f}°C", hot.county, delta_color="off")
k2.metric("❄️ 全台最低溫", f"{cold.min_temp:.0f}°C", cold.county, delta_color="off")
if day_df["pop"].notna().any():
    wet = day_df.loc[day_df["pop"].idxmax()]
    k3.metric("☔ 最高降雨機率", f"{wet['pop']:.0f}%", wet.county, delta_color="off")
else:
    k3.metric("☔ 最高降雨機率", "—", "此日無降雨機率預報", delta_color="off")
k4.metric("🌡️ 全台平均高溫", f"{day_df.max_temp.mean():.1f}°C")

# ---------------- Map + Table ----------------
left, right = st.columns([3, 2])

with left:
    st.subheader("🗺️ 天氣地圖")
    if view == "分區":
        pts = regions.rename(columns={"地區": "name", "最低溫": "min_temp", "最高溫": "max_temp",
                                      "降雨機率": "pop", "天氣": "weather"})
        radius = 22000
    else:
        pts = day_df.rename(columns={"county": "name"})
        radius = 9000
    # 配色範圍依本週最高溫區間，讓各地差異更明顯
    lo, hi = df["max_temp"].min(), df["max_temp"].max()
    if view == "分區":
        labels = pts.apply(lambda r: f"{r['name']} {fmt(r.min_temp)}-{fmt(r.max_temp)}°", axis=1)
    else:  # 縣市點太密，只標最高溫，名稱放在 tooltip
        labels = pts["max_temp"].map(lambda v: f"{fmt(v)}°")
    pts = pts.assign(
        color=pts["max_temp"].apply(lambda t: temp_color(t, lo, hi)),
        label=labels,
        tip_min=pts["min_temp"].map(fmt),
        tip_max=pts["max_temp"].map(fmt),
        tip_pop=pts["pop"].map(fmt),
    )
    layers = [
        pdk.Layer("ScatterplotLayer", pts, get_position="[lon, lat]", get_fill_color="color",
                  get_radius=radius, opacity=0.75, stroked=True, get_line_color=[255, 255, 255],
                  line_width_min_pixels=2, pickable=True),
        pdk.Layer("TextLayer", pts, get_position="[lon, lat]", get_text="label", get_size=13 if view == "分區" else 11,
                  get_color=[30, 30, 30], get_pixel_offset=[0, -22] if view == "分區" else [0, -14],
                  # pydeck 會把字串當 JS 運算式，所以用 json.dumps 包成字串常值
                  character_set=json.dumps("".join(sorted(set("".join(pts["label"])))), ensure_ascii=False),
                  font_family=json.dumps('"Noto Sans TC", "Noto Sans CJK TC", "Microsoft JhengHei", "PingFang TC", sans-serif'), font_weight=700,
                  outline_width=3, outline_color=[255, 255, 255], font_settings={"sdf": True}),
    ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=23.75, longitude=120.9, zoom=6.3),
            tooltip={"text": "{name}\n{weather}\n氣溫 {tip_min}–{tip_max}°C\n降雨機率 {tip_pop}%"},
            map_style="light",
        ),
        height=560,
    )
    st.caption("圓點顏色代表最高溫（依本週溫度區間）：藍（涼）→ 黃 → 紅（熱）。滑鼠移到圓點上可看詳細資訊。")

with right:
    st.subheader(f"📋 {date} 分區預報")
    st.dataframe(
        regions[["地區", "最低溫", "最高溫", "降雨機率", "天氣"]],
        hide_index=True,
        width="stretch",
        column_config={
            "最低溫": st.column_config.NumberColumn(format="%d °C"),
            "最高溫": st.column_config.NumberColumn(format="%d °C"),
            "降雨機率": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100),
        },
    )

    st.subheader("🏙️ 縣市明細")
    sel = st.selectbox("篩選地區", ["全部"] + [r for r in REGION_ORDER if r in day_df.region.unique()])
    cdf = (day_df if sel == "全部" else day_df[day_df.region == sel]).assign(
        pop=lambda d: d["pop"].map(lambda v: "—" if pd.isna(v) else f"{v:.0f}%"))
    st.dataframe(
        cdf[["county", "region", "min_temp", "max_temp", "pop", "humidity", "weather"]].rename(
            columns={"county": "縣市", "region": "地區", "min_temp": "最低溫", "max_temp": "最高溫",
                     "pop": "降雨機率", "humidity": "濕度", "weather": "天氣"}),
        hide_index=True,
        width="stretch",
        height=300,
        column_config={
            "最低溫": st.column_config.NumberColumn(format="%d °C"),
            "最高溫": st.column_config.NumberColumn(format="%d °C"),
            "濕度": st.column_config.NumberColumn(format="%d%%"),
        },
    )

# ---------------- Weekly trend ----------------
st.subheader("📈 一週氣溫趨勢")
t1, t2 = st.columns([1, 3])
with t1:
    counties = sorted(df["county"].unique(), key=lambda c: (REGION_ORDER.index(df[df.county == c].region.iat[0]), c))
    county = st.selectbox("選擇縣市", counties, index=counties.index("臺北市") if "臺北市" in counties else 0)
    cw = df[df.county == county].assign(
        day=lambda d: d["date"].map(lambda x: f"{x[5:7]}/{x[8:]}({WEEKDAY[pd.Timestamp(x).weekday()]})"),
        pop_txt=lambda d: d["pop"].map(lambda v: "—" if pd.isna(v) else f"{v:.0f}%"),
    )
    st.dataframe(
        cw[["day", "weather", "pop_txt"]].rename(columns={"day": "日期", "weather": "天氣", "pop_txt": "降雨"}),
        hide_index=True, width="stretch",
    )
with t2:
    long = cw.melt(id_vars="day", value_vars=["max_temp", "min_temp"], var_name="type", value_name="temp")
    long["type"] = long["type"].map({"max_temp": "最高溫", "min_temp": "最低溫"})
    base = alt.Chart(long).encode(
        x=alt.X("day:O", title="日期", sort=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("temp:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
        color=alt.Color("type:N", title="", scale=alt.Scale(domain=["最高溫", "最低溫"],
                                                            range=["#e4572e", "#2e86de"])),
    )
    chart = base.mark_line(point=True, strokeWidth=3) + base.mark_text(dy=-12, fontSize=12).encode(
        text=alt.Text("temp:Q", format=".0f"))
    st.altair_chart(chart.properties(height=320), use_container_width=True)

with st.expander("🗄️ 查看 SQLite 原始資料"):
    st.dataframe(df, hide_index=True, width="stretch")
