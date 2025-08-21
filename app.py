import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta

st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
.stAppViewContainer { padding-top: 6px; }
.block-container { padding-top: 4px; padding-bottom: 0; }
html, body, [data-testid="stAppViewContainer"] { height: 100vh; overflow: hidden; }

/* Filters: one line */
#filters { height: 56px; display: flex; align-items: center; gap: 12px; }

/* Compact widgets */
.small label { font-size: 12px !important; margin-bottom: 2px !important; }
.small .stSelectbox, .small .stNumberInput input { min-height: 34px !important; }
.small div[data-baseweb="select"] > div { min-height: 34px !important; }

/* Fixed footer prompt */
.footer {
  position: fixed; left: 0; right: 0; bottom: 0;
  background: white; border-top: 1px solid #e5e7eb;
  padding: 10px 14px; z-index: 1000; height: 64px;
}
.footer .inner {
  max-width: 1100px; margin: 0 auto; display: flex; gap: 8px; align-items: center; height: 44px;
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

/* Hide Streamlit footer & menu */
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

# ---------- FILTER STRIP ----------
st.markdown('<div id="filters">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.markdown('<div class="small">', unsafe_allow_html=True)
    max_orders = st.number_input("Orders", 1, 100, 10, step=1)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="small">', unsafe_allow_html=True)
    wheels = sorted(schedule["wheel_type"].unique())
    wheel_choice = st.selectbox("Wheel", ["All"] + wheels, index=0)
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="small">', unsafe_allow_html=True)
    machines = sorted(schedule["machine"].unique())
    machine_choice = st.selectbox("Machine", ["All"] + machines, index=0)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- FILTERING ----------
sched = schedule.copy()
if wheel_choice != "All":
    sched = sched[sched["wheel_type"] == wheel_choice]
if machine_choice != "All":
    sched = sched[sched["machine"] == machine_choice]

order_first_start = sched.groupby("order_id")["start"].min().sort_values().reset_index()
keep_ids = order_first_start["order_id"].head(int(max_orders)).tolist()
sched = sched[sched["order_id"].isin(keep_ids)]
if sched.empty:
    st.stop()

# ---------- GANTT ----------
color_map = {
    "Urban-200":"#1f77b4", "Offroad-250":"#ff7f0e", "Racing-180":"#2ca02c",
    "HeavyDuty-300":"#d62728", "Eco-160":"#9467bd"
}
domain = list(color_map.keys())
range_ = [color_map[k] for k in domain]

select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")

base = alt.Chart(sched).properties(width="container", height=520)

bars = base.mark_bar(cornerRadius=3).encode(
    y=alt.Y("machine:N", sort=sorted(sched["machine"].unique()), title=None),
    x=alt.X("start:T", title=None, axis=alt.Axis(format="%a %b %d")),
    x2="end:T",
    color=alt.condition(
        select_order,
        alt.Color("wheel_type:N", scale=alt.Scale(domain=domain, range=range_), legend=None),
        alt.value("#dcdcdc")
    ),
    opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.25)),
    tooltip=["order_id", "operation", "sequence", "machine", "start", "end", "due_date", "wheel_type"]
).add_params(select_order)

labels = base.mark_text(
    align="left", dx=6, baseline="middle", fontSize=10, color="white"
).encode(
    y="machine:N",
    x="start:T",
    text="order_id:N",
    opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.7))
)

gantt = (bars + labels).configure_view(stroke=None)
st.altair_chart(gantt, use_container_width=True)

# ---------- FOOTER ----------
st.markdown("""
<div class="footer">
  <form class="inner" method="post">
    <input name="cmd" type="text" placeholder="Type a command (e.g., move O021 Drill to M3 2025-08-26 09:00)" />
    <button type="submit">Apply</button>
  </form>
</div>
""", unsafe_allow_html=True)
