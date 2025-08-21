import streamlit as st
import pandas as pd
import altair as alt

# ---------------- Page setup ----------------
st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------------- Data ----------------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start", "end", "due_date"])
    return orders, sched

orders, schedule = load_data()

# ---------------- Session state (filters + ui) ----------------
if "filters_open" not in st.session_state:
    st.session_state.filters_open = True  # show sidebar initially

# Initialize filter values once (persist across toggles)
if "filt_max_orders" not in st.session_state:
    st.session_state.filt_max_orders = 12
if "filt_wheels" not in st.session_state:
    st.session_state.filt_wheels = sorted(schedule["wheel_type"].unique().tolist())
if "filt_machines" not in st.session_state:
    st.session_state.filt_machines = sorted(schedule["machine"].unique().tolist())

# ---------------- CSS ----------------
sidebar_display = "block" if st.session_state.filters_open else "none"

st.markdown(f"""
<style>
/* Fully hide sidebar when closed so main area uses 100% width */
[data-testid="stSidebar"] {{
  display: {sidebar_display};
}}

/* Top toolbar */
.topbar {{
  position: sticky; top: 0; z-index: 100;
  background: #fff; border-bottom: 1px solid #eee;
  padding: 8px 10px; margin-bottom: 6px;
}}
.topbar .inner {{
  display: flex; justify-content: space-between; align-items: center;
}}
.topbar .title {{ font-weight: 600; font-size: 16px; }}
.topbar .btn {{
  background: #000; color: #fff; border: none; border-radius: 8px;
  padding: 6px 12px; font-weight: 600; cursor: pointer;
}}
.topbar .btn:hover {{ opacity: 0.9; }}

/* Tighten spacing */
.block-container {{ padding-top: 6px; padding-bottom: 0; }}

/* Fixed bottom prompt bar */
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

/* Hide Streamlit default footer/menu */
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
            "Orders", min_value=1, max_value=100, value=st.session_state.filt_max_orders, step=1, key="max_orders_input"
        )

        wheels_all = sorted(schedule["wheel_type"].unique().tolist())
        st.session_state.filt_wheels = st.multiselect(
            "Wheel", wheels_all, default=st.session_state.filt_wheels or wheels_all, key="wheels_multiselect"
        )

        machines_all = sorted(schedule["machine"].unique().tolist())
        st.session_state.filt_machines = st.multiselect(
            "Machine", machines_all, default=st.session_state.filt_machines or machines_all, key="machines_multiselect"
        )

        if st.button("Reset filters"):
            st.session_state.filt_max_orders = 12
            st.session_state.filt_wheels = wheels_all
            st.session_state.filt_machines = machines_all
            st.rerun()

# ---------------- Apply filters ----------------
# Use session state values whether sidebar is visible or not
max_orders = int(st.session_state.filt_max_orders)

wheel_choice = st.session_state.filt_wheels
if not wheel_choice:  # if emptied, treat as all (avoid accidental blank screen)
    wheel_choice = sorted(schedule["wheel_type"].unique().tolist())

machine_choice = st.session_state.filt_machines
if not machine_choice:
    machine_choice = sorted(schedule["machine"].unique().tolist())

sched = schedule.copy()
sched = sched[sched["wheel_type"].isin(wheel_choice)]
sched = sched[sched["machine"].isin(machine_choice)]

# Keep first N orders by earliest start (within current filters)
order_priority = (
    sched.groupby("order_id", as_index=False)["start"].min().sort_values("start")
)
keep_ids = order_priority["order_id"].head(max_orders).tolist()
sched = sched[sched["order_id"].isin(keep_ids)].copy()

# ---------------- Gantt (Altair) ----------------
if sched.empty:
    st.info("No operations match the current filters.")
else:
    # Color palette per wheel type
    color_map = {
        "Urban-200": "#1f77b4",
        "Offroad-250": "#ff7f0e",
        "Racing-180": "#2ca02c",
        "HeavyDuty-300": "#d62728",
        "Eco-160": "#9467bd",
    }
    domain = list(color_map.keys())
    range_ = [color_map[k] for k in domain]

    # Selection (click order to highlight; double-click to clear)
    select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")

    # Encodings shared by layers
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

# ---------------- Fixed prompt bar ----------------
st.markdown("""
<div class="footer">
  <form class="inner" method="post">
    <input name="cmd" type="text" placeholder="Type a command (e.g., move O021 Drill to M3 2025-08-26 09:00)" />
    <button type="submit">Apply</button>
  </form>
</div>
""", unsafe_allow_html=True)
