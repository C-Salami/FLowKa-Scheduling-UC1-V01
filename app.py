import streamlit as st
import pandas as pd
import altair as alt

# ---------------- Page setup ----------------
st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# ---------------- State: sidebar open by default ----------------
if "filters_open" not in st.session_state:
    st.session_state["filters_open"] = True  # open at first load

# ---------------- CSS ----------------
st.markdown(f"""
<style>
/* Slide the sidebar in/out smoothly */
[data-testid="stSidebar"] {{
  width: {'18rem' if st.session_state['filters_open'] else '0'} !important;
  min-width: {'18rem' if st.session_state['filters_open'] else '0'} !important;
  overflow: hidden;
  transition: width 0.2s ease-in-out;
}}

/* Top toolbar */
.topbar {{
  position: sticky; top: 0; z-index: 100;
  background: #fff; border-bottom: 1px solid #eee;
  padding: 8px 8px 6px 8px; margin-bottom: 6px;
}}
.topbar .inner {{
  display: flex; justify-content: space-between; align-items: center;
}}
.topbar .title {{
  font-weight: 600; font-size: 16px;
}}
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

# ---------------- Top toolbar with explicit toggle ----------------
colA, colB = st.columns([1, 1])
with colA:
    st.markdown('<div class="topbar"><div class="inner">', unsafe_allow_html=True)
    st.markdown('<div class="title">Scooter Wheels Scheduler</div>', unsafe_allow_html=True)
with colB:
    # Draw a normal Streamlit button; we style via CSS class on the next line
    toggle_label = "Hide Filters" if st.session_state["filters_open"] else "Show Filters"
    # We wrap in markdown so we can apply the CSS class
    st.markdown(f'<div style="text-align:right;"><button onclick="window.location.reload()" class="btn">{toggle_label}</button></div>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)

# Implement the toggle with a Streamlit button right below (so it works server-side)
# (We hide this button visually by giving it empty label, but it flips the state.)
clicked = st.button("", key="toggle_filters_internal")
if clicked:
    st.session_state["filters_open"] = not st.session_state["filters_open"]

# Tip: If you prefer, replace the two-button trick above with st.form_submit_button in a small form.

# ---------------- Data ----------------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start", "end", "due_date"])
    return orders, sched

orders, schedule = load_data()

# ---------------- Sidebar filters (slide-out) ----------------
with st.sidebar:
    st.header("Filters ⚙️")
    max_orders = st.number_input("Orders", min_value=1, max_value=100, value=10, step=1)

    wheels = sorted(schedule["wheel_type"].unique())
    wheel_choice = st.multiselect("Wheel", wheels, default=wheels)

    machines = sorted(schedule["machine"].unique())
    machine_choice = st.multiselect("Machine", machines, default=machines)

# ---------------- Filtering ----------------
sched = schedule.copy()
if wheel_choice:
    sched = sched[sched["wheel_type"].isin(wheel_choice)]
if machine_choice:
    sched = sched[sched["machine"].isin(machine_choice)]

order_priority = (
    sched.groupby("order_id", as_index=False)["start"].min().sort_values("start")
)
keep_ids = order_priority["order_id"].head(int(max_orders)).tolist()
sched = sched[sched["order_id"].isin(keep_ids)].copy()

if sched.empty:
    st.info("No operations match the current filters.")
    st.markdown("""
    <div class="footer">
      <form class="inner" method="post">
        <input name="cmd" type="text" placeholder="Type a command (e.g., move O021 Drill to M3 2025-08-26 09:00)" />
        <button type="submit">Apply</button>
      </form>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------- Gantt (Altair) ----------------
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

base_enc = {
    "y": alt.Y("machine:N", sort=sorted(sched["machine"].unique()), title=None),
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
