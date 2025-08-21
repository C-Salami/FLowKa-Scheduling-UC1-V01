import streamlit as st
import pandas as pd
import altair as alt

from nlp_extractor import extract_intent
from nlp_validate import validate_intent
from nlp_apply import apply_delay, apply_move, apply_swap

# ---------------- Page setup ----------------
st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------------- Data ----------------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start", "end", "due_date"])
    return orders, sched

orders, base_schedule = load_data()

# Working schedule in session (so edits persist)
if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = base_schedule.copy()

# ---------------- State: sidebar open by default ----------------
if "filters_open" not in st.session_state:
    st.session_state.filters_open = True

# Initialize/persist filters
if "filt_max_orders" not in st.session_state:
    st.session_state.filt_max_orders = 12
if "filt_wheels" not in st.session_state:
    st.session_state.filt_wheels = sorted(base_schedule["wheel_type"].unique().tolist())
if "filt_machines" not in st.session_state:
    st.session_state.filt_machines = sorted(base_schedule["machine"].unique().tolist())

# ---------------- CSS ----------------
sidebar_display = "block" if st.session_state.filters_open else "none"
st.markdown(f"""
<style>
[data-testid="stSidebar"] {{ display: {sidebar_display}; }}
.topbar {{
  position: sticky; top: 0; z-index: 100;
  background: #fff; border-bottom: 1px solid #eee;
  padding: 8px 10px; margin-bottom: 6px;
}}
.topbar .inner {{ display: flex; justify-content: space-between; align-items: center; }}
.topbar .title {{ font-weight: 600; font-size: 16px; }}
.topbar .btn {{
  background: #000; color: #fff; border: none; border-radius: 8px;
  padding: 6px 12px; font-weight: 600; cursor: pointer;
}}
.topbar .btn:hover {{ opacity: 0.9; }}

.block-container {{ padding-top: 6px; padding-bottom: 0; }}

.footer {{
  position: fixed; left: 0; right: 0; bottom: 0;
  background: #fff; border-top: 1px solid #e5e7eb;
  padding: 10px 14px; height: 64px; z-index: 1000;
}}
.footer .inner {{
  max-width: 1100px; margin: 0 auto; display: flex; gap: 8px;
  align-items: center; height: 44px;
}}
.footer input[type='text'] {{
  flex: 1; height: 44px; border: 1px solid #d1d5db; border-radius: 9999px;
  padding: 0 14px; font-size: 16px;
}}
.footer button {{
  height: 44px; padding: 0 18px; border-radius: 9999px; background: #000; color: #fff;
  border: none; font-weight: 600; cursor: pointer;
}}
.footer button:hover {{ opacity: 0.9; }}
#MainMenu, footer {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# ---------------- Top toolbar ----------------
st.markdown('<div class="topbar"><div class="inner">', unsafe_allow_html=True)
st.markdown('<div class="title">Scooter Wheels Scheduler</div>', unsafe_allow_html=True)
toggle_label = "Hide Filters" if st.session_state.filters_open else "Show Filters"
if st.button(toggle_label, key="toggle_filters_btn"):
    st.session_state.filters_open = not st.session_state.filters_open
    st.rerun()
st.markdown('</div></div>', unsafe_allow_html=True)

# ---------------- Sidebar (render only when open) ----------------
if st.session_state.filters_open:
    with st.sidebar:
        st.header("Filters ⚙️")
        st.session_state.filt_max_orders = st.number_input(
            "Orders", 1, 100, value=st.session_state.filt_max_orders, step=1, key="max_orders_input"
        )
        wheels_all = sorted(base_schedule["wheel_type"].unique().tolist())
        st.session_state.filt_wheels = st.multiselect(
            "Wheel", wheels_all, default=st.session_state.filt_wheels or wheels_all, key="wheels_multiselect"
        )
        machines_all = sorted(base_schedule["machine"].unique().tolist())
        st.session_state.filt_machines = st.multiselect(
            "Machine", machines_all, default=st.session_state.filt_machines or machines_all, key="machines_multiselect"
        )
        if st.button("Reset filters"):
            st.session_state.filt_max_orders = 12
            st.session_state.filt_wheels = wheels_all
            st.session_state.filt_machines = machines_all
            st.rerun()

# ---------------- Apply filters ----------------
max_orders = int(st.session_state.filt_max_orders)
wheel_choice = st.session_state.filt_wheels or sorted(base_schedule["wheel_type"].unique().tolist())
machine_choice = st.session_state.filt_machines or sorted(base_schedule["machine"].unique().tolist())

# Filter the *working* schedule
sched = st.session_state.schedule_df.copy()
sched = sched[sched["wheel_type"].isin(wheel_choice)]
sched = sched[sched["machine"].isin(machine_choice)]
order_priority = sched.groupby("order_id", as_index=False)["start"].min().sort_values("start")
keep_ids = order_priority["order_id"].head(max_orders).tolist()
sched = sched[sched["order_id"].isin(keep_ids)].copy()

# ---------------- Gantt (Altair) ----------------
if sched.empty:
    st.info("No operations match the current filters.")
else:
    color_map = {
        "Urban-200": "#1f77b4",
        "Offroad-250": "#ff7f0e",
        "Racing-180": "#2ca02c",
        "HeavyDuty-300": "#d62728",
        "Eco-160": "#9467bd",
    }
    domain = list(color_map.keys())
    range_ = [color_map[k] for k in domain]

    select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")
    y_machines_sorted = sorted(sched["machine"].unique().tolist())

    base_enc = {
        "y": alt.Y("machine:N", sort=y_machines_sorted, title=None),
        "x": alt.X("start:T", title=None, axis=alt.Axis(format="%a %b %d")),
        "x2": "end:T",
    }

    bars = alt.Chart(sched).mark_bar(cornerRadius=3).encode(
        color=alt.condition(
            select_order,
            alt.Color("wheel_type:N", scale=alt.Scale(domain=domain, range=range_), legend=None),
            alt.value("#dcdcdc"),
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
        ],
    )

    labels = alt.Chart(sched).mark_text(
        align="left", dx=6, baseline="middle", fontSize=10, color="white"
    ).encode(
        text="order_id:N",
        opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.7)),
    )

    gantt = (
        alt.layer(bars, labels, data=sched)
        .encode(**base_enc)
        .add_params(select_order)
        .properties(width="container", height=520)
        .configure_view(stroke=None)
    )

    st.altair_chart(gantt, use_container_width=True)

# ---------------- Intelligence input & apply ----------------
user_cmd = st.chat_input("Type a command (delay/move/swap)…")
if user_cmd:
    try:
        payload = extract_intent(user_cmd)
        ok, msg = validate_intent(payload, orders, st.session_state.schedule_df)
        if not ok:
            st.toast(f"Cannot apply: {msg}", icon="⚠️")
        else:
            if payload["intent"] == "delay_order":
                st.session_state.schedule_df = apply_delay(
                    st.session_state.schedule_df,
                    payload["order_id"],
                    days=payload.get("days") or 0,
                    hours=payload.get("hours") or 0,
                )
                st.toast(f"Delayed {payload['order_id']}", icon="✅")
            elif payload["intent"] == "move_order":
                st.session_state.schedule_df = apply_move(
                    st.session_state.schedule_df,
                    payload["order_id"],
                    payload["_target_dt"],
                )
                st.toast(f"Moved {payload['order_id']} to {payload['_target_dt']}", icon="✅")
            elif payload["intent"] == "swap_orders":
                st.session_state.schedule_df = apply_swap(
                    st.session_state.schedule_df,
                    payload["order_id"], payload["order_id_2"]
                )
                st.toast(f"Swapped {payload['order_id']} ↔ {payload['order_id_2']}", icon="✅")
            st.rerun()
    except Exception as e:
        st.toast(f"Parser error: {e}", icon="❌")

# ---------------- Fixed prompt bar (visual only) ----------------
st.markdown("""
<div class="footer">
  <form class="inner" method="post">
    <input name="cmd" type="text" placeholder="Type a command (e.g., delay O021 one day / move O009 2025-08-30 09:00 / swap O014 O027)" />
    <button type="submit">Apply</button>
  </form>
</div>
""", unsafe_allow_html=True)
