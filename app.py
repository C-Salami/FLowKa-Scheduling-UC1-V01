import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta

# ---------- PAGE ----------
st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------- COMPACT CSS: one-line filters, fixed footer, no vertical scroll ----------
st.markdown("""
<style>
/* Remove Streamlit's default top padding and vertical scroll */
.stAppViewContainer { padding-top: 8px; overflow: hidden; }
.block-container { padding-top: 4px; padding-bottom: 0; }
html, body, [data-testid="stAppViewContainer"] { height: 100vh; }
main { height: 100vh; }

/* Layout: header filters (6vh), chart area (74vh), footer (14vh), gap 6vh leftover for margins */
#filters { height: 6vh; display: flex; align-items: center; }
#chart-wrap { height: 74vh; }
#chart { height: 100%; }

/* Compact widgets */
.small-label div[role="radiogroup"] label, .small-label label, .small-label .stSelectbox label {
  font-size: 12px !important;
}
.small-widget div[data-baseweb="select"] > div, .small-widget .stNumberInput input {
  min-height: 34px !important; height: 34px !important;
}

/* Fixed footer prompt */
.footer {
  position: fixed; left: 0; right: 0; bottom: 0;
  background: white; border-top: 1px solid #e5e7eb;
  padding: 8px 12px; z-index: 1000;
}
.footer .inner {
  max-width: 1100px; margin: 0 auto; display: flex; gap: 8px; align-items: center;
}
.footer input[type='text'] {
  flex: 1; height: 44px; border: 1px solid #d1d5db; border-radius: 9999px;
  padding: 0 14px; font-size: 16px;
}
.footer button {
  height: 44px; padding: 0 18px; border-radius: 9999px; background: #000; color: #fff;
  border: none; font-weight: 600; cursor: pointer;
}
.footer button:hover { opacity: 0.9; }

/* Hide Streamlit footer & menu to keep it clean */
#MainMenu, footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------- DATA ----------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start","end","due_date"])
    return orders, sched

orders, schedule = load_data()

# ---------- FILTER STRIP (one line) ----------
st.markdown('<div id="filters">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1, 2, 2])

with c1:
    st.markdown('<div class="small-label small-widget">', unsafe_allow_html=True)
    max_orders = st.number_input("Orders", min_value=1, max_value=100, value=10, step=1)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="small-label small-widget">', unsafe_allow_html=True)
    w_all = sorted(schedule["wheel_type"].unique().tolist())
    wheel_sel = st.multiselect("Wheel", w_all, default=w_all, key="wheel")
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="small-label small-widget">', unsafe_allow_html=True)
    m_all = sorted(schedule["machine"].unique().tolist())
    machine_sel = st.multiselect("Machine", m_all, default=m_all, key="machine")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- FILTERING ----------
sched = schedule.query("wheel_type in @wheel_sel and machine in @machine_sel").copy()
order_first_start = sched.groupby("order_id")["start"].min().sort_values().reset_index()
keep_order_ids = order_first_start["order_id"].head(int(max_orders)).tolist()
sched = sched[sched["order_id"].isin(keep_order_ids)].copy()
if sched.empty:
    st.empty()
    st.stop()

# Precompute
sched["uid"] = (
    sched["order_id"].astype(str) + "|" +
    sched["machine"].astype(str) + "|" +
    sched["operation"].astype(str) + "|" +
    sched["sequence"].astype(str)
)
plan_start = sched["start"].min()
plan_end = min(sched["end"].max(), plan_start + timedelta(days=30))

# Colors
color_map = {
    "Urban-200":"#1f77b4", "Offroad-250":"#ff7f0e", "Racing-180":"#2ca02c",
    "HeavyDuty-300":"#d62728", "Eco-160":"#9467bd"
}
domain = list(color_map.keys())
range_ = [color_map[k] for k in domain]

# ---------- CHART (middle) ----------
st.markdown('<div id="chart-wrap">', unsafe_allow_html=True)

# Selection: click one bar picks its order_id; dblclick clears
select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")

base = alt.Chart(sched).properties(width="container", height=0.96)  # height overridden by container below

bars = (
    base.mark_bar(cornerRadius=3)
    .encode(
        y=alt.Y("machine:N", sort=m_all, title=None),
        x=alt.X("start:T", title=None, axis=alt.Axis(format="%a %b %d")),
        x2="end:T",
        color=alt.condition(
            select_order,
            alt.Color("wheel_type:N", scale=alt.Scale(domain=domain, range=range_), legend=None),
            alt.value("#dcdcdc")
        ),
        opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.25)),
        tooltip=[
            alt.Tooltip("order_id:N", title="Order"),
            alt.Tooltip("operation:N", title="Operation"),
            alt.Tooltip("sequence:Q", title="Seq"),
            alt.Tooltip("machine:N", title="Machine"),
            alt.Tooltip("start:T", title="Start"),
            alt.Tooltip("end:T", title="End"),
            alt.Tooltip("due_date:T", title="Due"),
            alt.Tooltip("wheel_type:N", title="Wheel"),
        ]
    )
    .add_params(select_order)
)

# Text labels inside bars: show order_id
labels = (
    base.mark_text(align="left", dx=6, dy=0, baseline="middle", fontSize=10, color="white")
    .encode(
        y=alt.Y("machine:N", sort=m_all, title=None),
        x=alt.X("start:T", title=None),
        text="order_id:N",
        opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.6)),
    )
)

gantt = (bars + labels).interactive(False).configure_view(stroke=None)

# Put the chart in a fixed-height container using iframe-like div
st.markdown('<div id="chart">', unsafe_allow_html=True)
st.altair_chart(gantt, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- FIXED PROMPT (bottom) ----------
st.markdown("""
<div class="footer">
  <form class="inner" method="post">
    <input name="cmd" type="text" placeholder="Type a command (e.g., move O021 Drill to M3 2025-08-26 09:00)" />
    <button type="submit">Apply</button>
  </form>
</div>
""", unsafe_allow_html=True)

# (Command handling to be wired next)
