import streamlit as st
from typing import List
from pathlib import Path
import json
from tasks import ChartData
from streamlit.delta_generator import DeltaGenerator
import pandas as pd
from webapp import plot_chart
from pandas.core.frame import DataFrame

st.title("📊 Charts Selector")

# Initialize charts_to_plot in session state if not present
if st.session_state.get("charts_to_plot") is None:
    st.session_state["charts_to_plot"] = []

charts_to_plot: List[str] = st.session_state["charts_to_plot"]

with st.container():
    # Layout with columns for selection and buttons

    # Fetch JSON files from data/charts directory
    jsons_objs: List[Path] = list(Path("data/charts").rglob("*.json"))
    jsons_list: List[str] = [json_obj.name for json_obj in jsons_objs]
    chart_filename = st.selectbox(
        "Select a chart file",
        jsons_list,
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
        current_json_obj: Path = jsons_objs[jsons_list.index(current_chart)]

        # Load the JSON file containing chart data
        with open(current_json_obj, "r") as cur_file:
            chart_data_dict = json.load(cur_file)
            chart_data: ChartData = ChartData(**chart_data_dict)

        st.markdown(f"**Chart Title:** {chart_data.name}")
        scatter = st.empty()
        plot_chart(chart_data, scatter)
        st.divider()
