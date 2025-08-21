import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta

st.set_page_config(page_title="Scooter Wheels Scheduler", layout="wide")

# -------------------- LOAD DATA (repo CSVs) --------------------
@st.cache_data
def load_data():
    orders = pd.read_csv("data/scooter_orders.csv", parse_dates=["due_date"])
    sched = pd.read_csv("data/scooter_schedule.csv", parse_dates=["start", "end", "due_date"])
    return orders, sched

orders, schedule = load_data()

# -------------------- MINIMAL FILTER STRIP --------------------
# (Small row above the chart. No extra text/tables elsewhere.)
c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="center")

with c1:
    # Show only first N distinct orders by earliest start
    max_orders = st.number_input("Orders to show", min_value=1, max_value=100, value=10, step=1)
with c2:
    wheel_types = sorted(schedule["wheel_type"].unique().tolist())
    wheel_sel = st.multiselect("Wheel", wheel_types, default=wheel_types)
with c3:
    machines = sorted(schedule["machine"].unique().tolist())
    machine_sel = st.multiselect("Machine", machines, default=machines)

# Apply filters
sched = schedule.query("wheel_type in @wheel_sel and machine in @machine_sel").copy()

# Choose first N orders by earliest start within the current filter
order_first_start = (
    sched.groupby("order_id")["start"].min().sort_values().reset_index()
)
keep_order_ids = order_first_start["order_id"].head(int(max_orders)).tolist()
sched = sched[sched["order_id"].isin(keep_order_ids)].copy()

# If nothing left, stop quietly
if sched.empty:
    st.write("")  # keep layout clean
    st.stop()

# Precompute fields for Gantt
sched["uid"] = (
    sched["order_id"].astype(str) + "|" +
    sched["machine"].astype(str) + "|" +
    sched["operation"].astype(str) + "|" +
    sched["sequence"].astype(str)
)

plan_start = sched["start"].min()
# Default horizon: show up to last op among the selected orders
plan_end = sched["end"].max()
# Limit horizon to 30 days maximum to keep chart responsive
plan_end = min(plan_end, plan_start + timedelta(days=30))

# -------------------- CHART (ALTAIR) --------------------
# Color palette (same as earlier)
color_map = {
    "Urban-200":"#1f77b4", "Offroad-250":"#ff7f0e", "Racing-180":"#2ca02c",
    "HeavyDuty-300":"#d62728", "Eco-160":"#9467bd"
}
# Convert to scale domain/range
domain = list(color_map.keys())
range_ = [color_map[k] for k in domain]

# Selection: click a bar -> select that order_id.
select_order = alt.selection_point(fields=["order_id"], on="click", clear="dblclick")

base = alt.Chart(sched).properties(height=600)

bars = (
    base
    .mark_bar(cornerRadius=3)
    .encode(
        y=alt.Y("machine:N", sort=sorted(machines), title=None),
        x=alt.X("start:T", title=None, axis=alt.Axis(format="%a %b %d")),
        x2="end:T",
        color=alt.condition(
            select_order,
            alt.Color("wheel_type:N", scale=alt.Scale(domain=domain, range=range_), legend=None),
            alt.value("#dcdcdc")  # light gray when not selected
        ),
        opacity=alt.condition(select_order, alt.value(1.0), alt.value(0.25)),
        tooltip=[
            alt.Tooltip("order_id:N", title="Order"),
            alt.Tooltip("wheel_type:N", title="Wheel"),
            alt.Tooltip("operation:N", title="Operation"),
            alt.Tooltip("sequence:Q", title="Seq"),
            alt.Tooltip("machine:N", title="Machine"),
            alt.Tooltip("start:T", title="Start"),
            alt.Tooltip("end:T", title="End"),
            alt.Tooltip("due_date:T", title="Due"),
        ]
    )
    .add_params(select_order)
)

# Draw a top "calendar ruler" by adding a rule every day with labels (via axis ticks)
# (Altair's time axis already gives nice daily ticks when the domain spans days.)
gantt = bars.properties(width="container").configure_axis(labelFontSize=12).configure_view(stroke=None)

# Render only the chart (no extra sections)
st.plotly_chart  # silence linter that may suggest plotly; we intentionally use Altair

st.altair_chart(gantt, use_container_width=True)

# -------------------- PROMPT BAR (FIXED FOOTER) --------------------
# Create a fixed footer with custom CSS so it mimics a chat input with black button.
st.markdown("""
<style>
.footer {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  background: white;
  border-top: 1px solid #e5e7eb;
  padding: 10px 16px;
  z-index: 1000;
}
.footer .inner {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  gap: 8px;
  align-items: center;
}
.footer input[type='text'] {
  flex: 1;
  height: 44px; /* similar to ChatGPT input */
  border: 1px solid #d1d5db;
  border-radius: 9999px;
  padding: 0 14px;
  font-size: 16px;
}
.footer button {
  height: 44px; /* match input height */
  padding: 0 18px;
  border-radius: 9999px;
  background: #000;
  color: #fff;
  border: none;
  font-weight: 600;
  cursor: pointer;
}
.footer button:hover { opacity: 0.9; }
</style>
<div class="footer">
  <form class="inner" method="post">
    <input name="cmd" type="text" placeholder="Type a command to modify the schedule (e.g., move O021 Drill to M3 tomorrow 09:00)" />
    <button type="submit">Apply</button>
  </form>
</div>
""", unsafe_allow_html=True)

# Handle form submission from the custom footer
# Streamlit can't directly read the HTML form, so we mirror it with st.experimental_get_query_params hack via forms.
# Simpler approach: add invisible Streamlit form synced via widget state:
with st.form("hidden_form", clear_on_submit=True):
    _cmd = st.text_input(" ", key="cmd_input", value="", label_visibility="collapsed")
    _submitted = st.form_submit_button("hidden_submit")

# Sync the HTML input to Streamlit's state via a small JS bridge (optional).
# For now, keep it simple: use the visible chat-like bar via Streamlit's chat_input as a fallback:
_ = st.chat_input("")

# NOTE: Next step we'll wire the footer to actual edits (move/resize/reassign) and trigger a re-render.
