"""Runtime dashboard cho Day 13 lab: đọc data/logs.jsonl và vẽ 6 panel theo config/dashboard.yaml.

Chạy: python -m streamlit run scripts/dashboard.py
Cần: pip install streamlit pandas
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_PATH = Path("data/logs.jsonl")
TIME_RANGE_MINUTES = 60
SLO_LATENCY_MS = 3000
GUARDRAIL_ERROR_RATE_PCT = 2.0
GUARDRAIL_COST_USD = 2.5
GUARDRAIL_QUALITY_MIN = 0.75


@st.cache_data(ttl=30)
def load_logs() -> pd.DataFrame:
    records = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame.from_records(records)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df


st.set_page_config(page_title="K4-L3B Day 13 Monitoring", layout="wide")
st.title("K4-L3B Day 13 Monitoring & LLMOps")

df = load_logs()
if df.empty:
    st.warning("Chưa có log. Chạy API + `python scripts/load_test.py` để tạo data/logs.jsonl.")
    st.stop()

now = datetime.now(timezone.utc)
cutoff = now - timedelta(minutes=TIME_RANGE_MINUTES)
df = df[df["ts"] >= cutoff]
st.caption(
    f"Nguồn: `{LOG_PATH}` | Time range: {TIME_RANGE_MINUTES} phút gần nhất "
    f"({df['ts'].min():%H:%M} – {df['ts'].max():%H:%M} UTC) | Refresh: 30s"
)

sent = df[df["event"] == "response_sent"].copy()
received = df[df["event"] == "request_received"]
failed = df[df["event"] == "request_failed"]

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Latency percentiles and TTFT (ms)")
    if sent.empty:
        st.info("Chưa có event response_sent.")
    else:
        p50, p95, p99 = sent["latency_ms"].quantile([0.50, 0.95, 0.99])
        ttft_p95 = sent["ttft_ms"].quantile(0.95)
        st.caption(
            f"P50={p50:.0f} | P95={p95:.0f} | P99={p99:.0f} | TTFT P95={ttft_p95:.0f} ms — "
            f"threshold SLO P95 ≤ {SLO_LATENCY_MS} ms"
        )
        st.bar_chart(
            pd.DataFrame(
                {"value_ms": {"P50": p50, "P95": p95, "P99": p99, "TTFT P95": ttft_p95}}
            ),
            color="#4c78a8",
        )
        st.metric("Latency P95", f"{p95:.0f} ms", f"SLO ≤ {SLO_LATENCY_MS} ms")
        st.line_chart(sent.set_index("ts")[["latency_ms", "ttft_ms"]])

with col2:
    st.subheader("2. Request traffic (requests/minute)")
    per_min = received.set_index("ts").resample("1min").size()
    rate = per_mean = per_min.mean() if len(per_min) else 0
    st.caption(f"Total requests: {len(received)} | mean {rate:.1f} req/min — threshold ≥ 1 req/min")
    st.bar_chart(per_min)

col3, col4 = st.columns(2)

with col3:
    st.subheader("3. Error rate & retrieval success (%)")
    total = len(received)
    error_rate = (len(failed) / total * 100) if total else 0.0
    tool_rows = df[df["tool_success"].notna()]
    retrieval_success = (
        (tool_rows["tool_success"].astype(bool).mean() * 100) if len(tool_rows) else 100.0
    )
    st.caption(
        f"Error rate={error_rate:.2f}% (threshold ≤ {GUARDRAIL_ERROR_RATE_PCT}%) | "
        f"Retrieval success={retrieval_success:.1f}%"
    )
    if "error_type" in df.columns and df["error_type"].notna().any():
        st.caption("Error breakdown: " + str(df["error_type"].value_counts().to_dict()))
    st.bar_chart(pd.DataFrame({"percent": {"error_rate": error_rate, "retrieval_success": retrieval_success}}))

with col4:
    st.subheader("4. Cost over time (USD)")
    if sent.empty:
        st.info("Chưa có dữ liệu cost.")
    else:
        cost_per_min = sent.set_index("ts")["cost_usd"].resample("1min").sum()
        total_cost = sent["cost_usd"].sum()
        st.caption(
            f"Total cost=${total_cost:.4f} — threshold ≤ ${GUARDRAIL_COST_USD} | "
            f"unit: USD per minute"
        )
        st.line_chart(cost_per_min)

col5, col6 = st.columns(2)

with col5:
    st.subheader("5. Input and output tokens")
    tokens_in = int(sent["tokens_in"].sum()) if not sent.empty else 0
    tokens_out = int(sent["tokens_out"].sum()) if not sent.empty else 0
    st.caption(f"tokens_in={tokens_in} | tokens_out={tokens_out} | threshold tổng ≤ 50000 tokens")
    st.bar_chart(pd.DataFrame({"tokens": {"tokens_in": tokens_in, "tokens_out": tokens_out}}))

with col6:
    st.subheader("6. Quality proxy (score 0–1)")
    mean_quality = sent["quality_score"].mean() if not sent.empty else 0.0
    st.caption(
        f"Mean quality={mean_quality:.2f} — threshold ≥ {GUARDRAIL_QUALITY_MIN} | unit: score 0 to 1"
    )
    if not sent.empty:
        st.line_chart(sent.set_index("ts")["quality_score"].resample("1min").mean())
