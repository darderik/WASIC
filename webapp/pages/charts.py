from pathlib import Path
from typing import List
import streamlit as st
from config import Config
from tasks.chart_io import load_charts_file
from webapp import make_plotly_figure

st.title("📊 Charts Selector")

# Initialize charts_to_plot in session state if not present
if st.session_state.get("charts_to_plot") is None:
    st.session_state["charts_to_plot"] = []

charts_to_plot: List[str] = st.session_state["charts_to_plot"]

with st.container():
    # Layout with columns for selection and buttons

    # Keep relative paths so backups/subdirectories with identical names work.
    charts_root = Path(Config().get("data_charts_path"))
    chart_files = {
        str(path.relative_to(charts_root)): path
        for path in sorted(charts_root.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".csv"
        and not path.name.lower().endswith(".meta.csv")
    }
    filenames = list(chart_files)
    chart_filename = st.selectbox(
        "Select a chart file",
        filenames,
        help="Check the custom title added when saving ChartData instance",
    )
with st.container():
    col1, col2 = st.columns([1, 1])
    with col1:
        # Button to add selected chart to plotting list
        st.button(
            "➕ Add Chart",
            on_click=lambda: charts_to_plot.append(chart_filename),
            key="add_chart_btn",
            disabled=len(filenames) == 0,
        )

    with col2:
        # Button to clear all selected charts
        st.button(
            "🗑️ Clear All",
            on_click=lambda: charts_to_plot.clear(),
            key="clear_charts_btn",
        )

with st.container():
    st.divider()
    # Display selected charts
    for current_chart in charts_to_plot:
        st.subheader(f"📈 Plotting: `{current_chart}`")
        current_path = chart_files.get(current_chart)
        if current_path is None:
            st.warning(f"Chart file no longer available: {current_chart}")
            continue
        try:
            chart_data_list = load_charts_file(current_path)
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            st.error(f"Cannot load {current_chart}: {exc}")
            continue
        for chart_data in chart_data_list:
            st.write(f"**Chart: {chart_data.name}**")
            fig = make_plotly_figure(chart_data)
            st.plotly_chart(fig, use_container_width=True)
