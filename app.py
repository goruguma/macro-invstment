import json
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from fredapi import Fred

st.set_page_config(page_title="Macro Daily Briefing", layout="wide")

COLORS = {
    "bg": "#F8F9FA",
    "text": "#343A40",
    "accent": "#495057",
    "line": "#6C757D",
    "bull": "#82A0AA",
    "bear": "#A68A8A",
    "neutral": "#ADB5BD",
    "grid": "#DEE2E6",
}


# ---------- Data Loaders ----------
@st.cache_data(ttl=60 * 60)
def get_fred_data(api_key: str):
    fred = Fred(api_key=api_key)

    nfci = fred.get_series(
        "NFCI",
        observation_start=(datetime.now() - timedelta(days=365 * 10)),
    )

    bull = fred.get_series("AAIIBULL")
    bear = fred.get_series("AAIIBEAR")
    neutral = fred.get_series("AAIINEUT")

    sentiment = (
        pd.DataFrame({"Bullish": bull, "Bearish": bear, "Neutral": neutral})
        .dropna()
        .tail(1)
        .T
        .rename(columns=lambda _: "Latest")
    )

    hy_spread = fred.get_series(
        "BAMLH0A0HYM2",
        observation_start=(datetime.now() - timedelta(days=365 * 2)),
    ).dropna()

    return nfci.dropna(), sentiment, hy_spread


@st.cache_data(ttl=60 * 60)
def get_sector_data():
    sectors = {
        "XLK": "Technology",
        "XLV": "Health Care",
        "XLF": "Financials",
        "XLY": "Consumer Discretionary",
        "XLP": "Consumer Staples",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLU": "Utilities",
        "XLC": "Communication Services",
    }
    prices = yf.download(list(sectors.keys()), period="1y", auto_adjust=True, progress=False)["Close"]
    one_month_mom = ((prices.iloc[-1] / prices.iloc[-21]) - 1) * 100

    df = pd.DataFrame(
        {
            "Ticker": one_month_mom.index,
            "Sector": [sectors[t] for t in one_month_mom.index],
            "Momentum": one_month_mom.values,
        }
    )
    return df


@st.cache_data(ttl=60 * 60)
def get_cnn_fear_greed():
    """
    CNN Fear & Greed 지수를 비공식 공개 endpoint에서 조회합니다.
    실패 시 None 반환.
    """
    endpoint = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        res = requests.get(endpoint, timeout=8)
        res.raise_for_status()
        data = res.json()

        now_score = data.get("fear_and_greed", {}).get("score")
        now_label = data.get("fear_and_greed", {}).get("rating", "N/A")

        hist = data.get("fear_and_greed_historical", {}).get("data", [])
        hist_df = pd.DataFrame(hist)
        if not hist_df.empty and "x" in hist_df.columns and "y" in hist_df.columns:
            hist_df["Date"] = pd.to_datetime(hist_df["x"], unit="ms")
            hist_df["Score"] = hist_df["y"].astype(float)
            hist_df = hist_df[["Date", "Score"]].dropna()

        return {
            "score": float(now_score) if now_score is not None else None,
            "rating": now_label,
            "history": hist_df if isinstance(hist_df, pd.DataFrame) else pd.DataFrame(),
        }
    except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError):
        return {"score": None, "rating": "N/A", "history": pd.DataFrame()}


@st.cache_data(ttl=60 * 60)
def get_put_call_ratio():
    """
    CBOE 공개 CSV에서 Put/Call Ratio 시계열을 가져옵니다.
    """
    csv_url = "https://cdn.cboe.com/data/us/options/market_statistics/daily/cboe_total_market_stats.csv"
    try:
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]

        date_col = "trade_date" if "trade_date" in df.columns else "date"
        ratio_col = next((c for c in df.columns if "put_call_ratio" in c), None)
        if ratio_col is None:
            return pd.Series(dtype=float)

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        series = (
            df[[date_col, ratio_col]]
            .dropna()
            .sort_values(date_col)
            .set_index(date_col)[ratio_col]
            .astype(float)
        )
        return series.last("180D")
    except Exception:
        return pd.Series(dtype=float)


# ---------- Sidebar ----------
st.sidebar.title("⚙️ Settings")

# 1) Streamlit Secrets에 FRED_API_KEY가 있으면 우선 사용
# 2) 없으면 사이드바 입력값 사용
secret_key = st.secrets.get("FRED_API_KEY", "")
manual_key = st.sidebar.text_input("FRED API Key", type="password")
fred_key = secret_key or manual_key

st.sidebar.caption("매일 아침 확인용 대시보드 · 데이터 캐시 1시간")
if secret_key:
    st.sidebar.success("FRED API Key: Streamlit Secrets에서 로드됨")

if not fred_key:
    st.warning("FRED API Key를 입력해 주세요. (Secrets 또는 사이드바 입력)")
    st.stop()

# ---------- Fetch ----------
nfci, sentiment, hy_spread = get_fred_data(fred_key)
sector_df = get_sector_data()
fg = get_cnn_fear_greed()
put_call = get_put_call_ratio()


# ---------- Header ----------
st.title("📊 Macro Daily Briefing")
st.caption(f"Last updated (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")


# ---------- Row 1 ----------
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Fear & Greed")

    score = fg["score"] if fg["score"] is not None else 50
    rating = fg["rating"]

    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"Market Sentiment ({rating})", "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": COLORS["accent"]},
                "steps": [
                    {"range": [0, 25], "color": "#D98E8E"},
                    {"range": [25, 45], "color": "#E8C4C4"},
                    {"range": [45, 55], "color": "#F1F3F5"},
                    {"range": [55, 75], "color": "#C2D2D9"},
                    {"range": [75, 100], "color": "#82A0AA"},
                ],
            },
        )
    )
    fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor="white")
    st.plotly_chart(fig_gauge, use_container_width=True)

    if fg["score"] is None:
        st.caption("CNN 데이터 조회 실패로 중립값(50) 표시")

with col2:
    st.subheader("NFCI (10-Year)")
    fig_nfci = px.line(
        nfci,
        labels={"value": "Index", "index": "Date"},
        color_discrete_sequence=[COLORS["line"]],
    )
    fig_nfci.add_hline(y=0, line_dash="dash", line_color="black")
    fig_nfci.update_layout(plot_bgcolor="white", height=350)
    st.plotly_chart(fig_nfci, use_container_width=True)
    st.caption("0보다 낮으면 금융 여건 완화, 높으면 긴축 상태로 해석합니다.")

st.markdown("---")

# ---------- Row 2 ----------
col3, col4 = st.columns(2)

with col3:
    st.subheader("AAII Investor Sentiment (Latest)")
    fig_sent = px.bar(
        sentiment,
        x=sentiment.index,
        y="Latest",
        color=sentiment.index,
        color_discrete_map={
            "Bullish": COLORS["bull"],
            "Bearish": COLORS["bear"],
            "Neutral": COLORS["neutral"],
        },
    )
    fig_sent.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Percentage",
        height=350,
        plot_bgcolor="white",
    )
    st.plotly_chart(fig_sent, use_container_width=True)

with col4:
    st.subheader("US High-Yield Spread")
    fig_hy = px.area(hy_spread, color_discrete_sequence=[COLORS["bear"]])
    fig_hy.update_layout(plot_bgcolor="white", height=350, showlegend=False)
    st.plotly_chart(fig_hy, use_container_width=True)
    st.caption("FRED(BAMLH0A0HYM2): HY 회사채 - 미국 10년물 국채 스프레드")

st.markdown("---")

# ---------- Row 3 ----------
col5, col6 = st.columns(2)

with col5:
    st.subheader("Put / Call Ratio (CBOE, 6M)")
    if put_call.empty:
        st.info("Put/Call Ratio 데이터를 불러오지 못했습니다.")
    else:
        fig_pcr = px.line(
            put_call,
            labels={"value": "Put/Call Ratio", "index": "Date"},
            color_discrete_sequence=[COLORS["accent"]],
        )
        fig_pcr.add_hline(y=1.0, line_dash="dash", line_color=COLORS["grid"])
        fig_pcr.update_layout(height=330, plot_bgcolor="white")
        st.plotly_chart(fig_pcr, use_container_width=True)

with col6:
    st.subheader("Fear & Greed Trend")
    if fg["history"].empty:
        st.info("Fear & Greed 히스토리 데이터를 불러오지 못했습니다.")
    else:
        fig_fg_hist = px.line(
            fg["history"].tail(180),
            x="Date",
            y="Score",
            color_discrete_sequence=[COLORS["line"]],
        )
        fig_fg_hist.update_layout(height=330, plot_bgcolor="white")
        st.plotly_chart(fig_fg_hist, use_container_width=True)

st.markdown("---")

# ---------- Row 4 ----------
st.subheader("Sector Momentum (1-Month Return)")
sector_df = sector_df.sort_values("Momentum", ascending=False)
fig_sector = px.bar(
    sector_df,
    x="Momentum",
    y="Sector",
    orientation="h",
    color="Momentum",
    color_continuous_scale="RdBu",
)
fig_sector.add_vline(x=0, line_dash="dash", line_color=COLORS["grid"])
fig_sector.update_layout(height=450, plot_bgcolor="white", coloraxis_showscale=False)
st.plotly_chart(fig_sector, use_container_width=True)

with st.expander("Sector Guide (간단 설명)"):
    st.markdown(
        """
- **XLK (Technology)**: 반도체·소프트웨어 등 성장주 중심.
- **XLE (Energy)**: 정유·가스 등 원자재/유가 민감 업종.
- **XLF (Financials)**: 은행·보험 중심, 금리/신용사이클 민감.
- **XLV (Health Care)**: 제약·바이오 중심, 방어적 성격.
- **XLY (Consumer Discretionary)**: 자동차·리테일 등 경기민감 소비.
- **XLP (Consumer Staples)**: 필수소비재 중심, 경기방어 업종.
- **해석**: 오른쪽으로 길수록 최근 1개월 상대 강세를 의미.
        """
    )

st.caption("권장: GitHub 연동 후 Streamlit Community Cloud 배포로 매일 자동 확인")
