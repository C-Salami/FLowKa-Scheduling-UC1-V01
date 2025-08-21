import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
/* Sidebar toggle button */
button[data-testid="collapsedControl"] {
    position: fixed;
    top: 10px; left: 10px;
    background: #000; color: #fff; font-weight: bold;
    border-radius: 4px; border: none;
    width: 28px; height: 28px; cursor: pointer;
    z-index: 2000;
}
</style>
""", unsafe_allow_html=True)

# ---------- DATA ----------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start","end","due_date"])
    return orders, sched

orders, schedule = load_data()

# ---------- SIDEBAR FILTERS ----------
with st.sidebar:
    st.header("Filters ⚙️")
    max_orders = st.number_input("Orders", 1, 100, 10, step=1)

    wheels = sorted(schedule["wheel_type"].unique())
    wheel_choice = st.multiselect("Wheel", wheels, default=wheels)

    machines = sorted(schedule["machine"].unique())
    machine_choice = st.multiselect("Machine", machines, default=machines)

# ---------- FILTERING ----------
sched = schedule.copy()
if wheel_choice:
    sched = sched[sched["wheel_type"].isin(wheel_choice)]
if machine_choice:
    sched = sched[sched["machine"].isin(machine_choice)]
keep_ids = (sched.groupby("order_id")["start"].min()
            .sort_values().index.tolist())[:int(max_orders)]
sched = sched[sched["order_id"].isin(keep_ids)]
if sched.empty: st.stop()

# ---------- GANTT ----------
color_map = {
    "Urban-200":"#1f77b4","Offroad-250":"#ff7f0e","Racing-180":"#2ca02c",
    "HeavyDuty-300":"#d62728","Eco-160":"#9467bd"
}
domain = list(color_map.keys())
range_ = [color_map[k] for k in domain]
select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")

base = alt.Chart(sched).properties(width="container", height=520).configure_view(stroke=None)

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
    tooltip=["order_id","operation","sequence","machine","start","end","due_date","wheel_type"]
).add_params(select_order)

labels = base.mark_text(
    align="left", dx=6, baseline="middle", fontSize=10, color="white"
).encode(
    y="machine:N", x="start:T", text="order_id:N",
    opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.7))
)

st.altair_chart(bars + labels, use_container_width=True)

# ---------- FIXED PROMPT ----------
st.markdown("""
<div class="footer" style="
  position: fixed; left: 0; right: 0; bottom: 0;
  background: white; border-top: 1px solid #e5e7eb;
  padding: 10px 14px; height: 64px; z-index: 1000;">
  <div class="inner" style="
    max-width: 1100px; margin: 0 auto; display: flex; gap: 8px;
    align-items: center; height: 44px;">
    <input name="cmd" type="text"
      placeholder="Type a command (e.g., move O021 Drill to M3 2025-08-26 09:00)"
      style="flex:1; height:44px; border:1px solid #d1d5db; border-radius:9999px;
             padding:0 14px; font-size:16px;" />
    <button type="submit" style="
      height:44px; padding:0 18px; border-radius:9999px;
      background:#000; color:#fff; border:none; font-weight:600; cursor:pointer;">
      Apply
    </button>
  </div>
</div>
""", unsafe_allow_html=True)
