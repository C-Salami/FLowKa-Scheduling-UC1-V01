import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# --- Sidebar: data source ---
st.sidebar.header("Data")
data_src = st.sidebar.radio(
    "Load schedule from:",
    ["Repo CSV (default)", "Upload CSVs"]
)

@st.cache_data
def load_repo_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    schedule = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start","end","due_date"])
    return orders, schedule

def load_uploaded():
    o = st.file_uploader("Upload orders CSV", type=["csv"], key="orders")
    s = st.file_uploader("Upload schedule CSV", type=["csv"], key="schedule")
    if o and s:
        orders = pd.read_csv(o, parse_dates=["due_date"])
        schedule = pd.read_csv(s, parse_dates=["start","end","due_date"])
        return orders, schedule
    return None, None

if data_src == "Repo CSV (default)":
    orders, schedule = load_repo_data()
else:
    orders, schedule = load_uploaded()
    if orders is None:
        st.stop()

# --- Main header ---
st.title("Scooter Wheels Scheduler")
st.caption("Machines on the Y axis • Operations by order • Color = wheel type • Calendar at top")

# --- Filters ---
colf1, colf2, colf3 = st.columns(3)
with colf1:
    wheel_filter = st.multiselect("Wheel types", sorted(schedule["wheel_type"].unique()), default=list(sorted(schedule["wheel_type"].unique())))
with colf2:
    machine_filter = st.multiselect("Machines", sorted(schedule["machine"].unique()), default=list(sorted(schedule["machine"].unique())))
with colf3:
    days_horizon = st.slider("Days to show from plan start", 3, 30, 14)

# --- Apply filters & horizon ---
sched = schedule.query("wheel_type in @wheel_filter and machine in @machine_filter").copy()
plan_start = sched["start"].min()
max_end = plan_start + timedelta(days=int(days_horizon))
sched = sched[(sched["start"] <= max_end) & (sched["end"] >= plan_start)]

# Plotly needs start/end columns for timeline
sched["Start"] = sched["start"]
sched["Finish"] = sched["end"]
sched["MachineLabel"] = sched["machine"]

# --- Gantt chart ---
color_discrete_map = {
    "Urban-200":"#1f77b4", "Offroad-250":"#ff7f0e", "Racing-180":"#2ca02c",
    "HeavyDuty-300":"#d62728", "Eco-160":"#9467bd"
}

fig = px.timeline(
    sched,
    x_start="Start", x_end="Finish",
    y="MachineLabel", color="wheel_type",
    color_discrete_map=color_discrete_map,
    hover_data=["order_id","operation","sequence","due_date"],
)

fig.update_yaxes(autorange="reversed")  # like a gantt
fig.update_layout(
    height=650,
    margin=dict(l=20, r=20, t=60, b=20),
    legend_title_text="Wheel type",
    xaxis_title="Time",
    yaxis_title="Machine",
)

# Add a calendar-like tick spacing (daily)
fig.update_xaxes(dtick=24*60*60*1000, tickformat="%a %b %d")

st.plotly_chart(fig, use_container_width=True)

# --- Orders table (optional quick look) ---
with st.expander("Peek at orders"):
    st.dataframe(orders, use_container_width=True, height=280)

# --- Prompt bar (for future interactive edits) ---
st.divider()
st.subheader("Command prompt (coming next)")
cmd = st.chat_input("Type a command, e.g., 'move O021 Drill to M3 tomorrow 09:00'")
if cmd:
    st.session_state.setdefault("cmd_history", []).append({"role": "user", "content": cmd})
    st.write(":wrench: We’ll implement real edits in the next step. You typed:", cmd)

    # Echo history
    with st.expander("Prompt history"):
        for m in st.session_state["cmd_history"]:
            st.write(f"**{m['role']}**: {m['content']}")
