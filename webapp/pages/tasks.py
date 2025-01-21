import streamlit as st
from typing import List, Optional
import time
from streamlit.delta_generator import DeltaGenerator
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument
from user_defined import RaspberrySIM
from tasks import Task, Tasks
from tasks import ChartData
import pandas as pd


def populate_scatter(chartData: ChartData, scatter: DeltaGenerator) -> None:
    minimumLength: int = min(len(chartData.x), len(chartData.y))
    if len(chartData.x) == 0:  # Plot only y
        # Plot only scatter
        scatter.scatter_chart(
            [round(curVal, 2) for curVal in chartData.y],
            x_label=chartData.x_label,
            y_label=chartData.y_label,
        )
    else:
        # Plot scatter with x y
        # This check is to avoid out of sync x - y values
        newDataFrame = pd.DataFrame(
            data={
                "x": [round(curVal, 2) for curVal in chartData.x[:minimumLength]],
                "y": [round(curVal, 2) for curVal in chartData.y[:minimumLength]],
            }
        )
        scatter.scatter_chart(
            newDataFrame,
            x="x",
            y="y",
            x_label=chartData.x_label,
            y_label=chartData.y_label,
        )


def set_custom_alias() -> None:
    changedAlias: str = st.session_state["task_alias"]
    Tasks._is_running.custom_alias = changedAlias


# Check if a task is currently running
is_task_running: bool = Tasks._is_running is not None


# Set the main title of the page
st.title("🔧 Tasks Selector")

# Task selection widget
with st.container():
    col_task, col_run = st.columns([3, 1])

    relevant_tasks = [tsk.name for tsk in Tasks.tasks_list if tsk.has_instruments()]
    if relevant_tasks == []:
        st.warning(
            "No tasks available. Connect the instruments. Attempting to refresh.."
        )
        Tasks.update_instruments()
    else:
        with col_task:
            task_selectbox: str = st.selectbox(
                "Select Task",
                relevant_tasks,
                disabled=is_task_running,
                help="Choose a task to execute.",
            )

        with col_run:
            st.button(
                "🚀 Run Task",
                on_click=Tasks.run_task,
                args=(task_selectbox,),
                disabled=is_task_running,
                key="run_task_button",
                help="Start the selected task.",
            )
        with col_run:
            st.button(
                "🔄 Match Instruments",
                on_click=Tasks.update_instruments,
                key="refresh_matched_instruments",
                help="Refresh each task's matched instruments.",
            )

    # Display task details and controls if a task is running
    if is_task_running:
        with st.container():
            st.markdown("---")
            st.subheader("⚙️ Current Task")
            cur_task: Task = Tasks._is_running

            # Task Details
            with st.expander("📋 Task Details", expanded=True):
                st.markdown(f"**Name:** {cur_task.name}")
                st.markdown(f"**Description:** {cur_task.description}")

            # Instruments Information
            with st.expander("🔌 Instruments", expanded=True):
                if cur_task.instruments != []:
                    for instr in cur_task.instruments:
                        st.write(f"- **ID:** {instr.data.idn}")
                else:
                    st.write("No instruments associated with this task.")

            # Stop Task Button, but first force the user to insert an alias for the task (will be contained in save file)
            col_stop_task, col_custom_alias = st.columns([3, 1])
            with col_custom_alias:
                custom_alias: str = st.text_input(
                    label="Insert Alias for Task",
                    value="",
                    key="task_alias",
                    help="Insert alias BEFORE stopping the task.",
                    on_change=set_custom_alias,
                )

            with col_stop_task:
                st.button(
                    "🛑 Stop Task",
                    on_click=Tasks.kill_task,
                    key="stop_task_button",
                    help="Stop the currently running task.",
                    disabled=custom_alias == "",
                )

        plots_list: List[DeltaGenerator] = []

        # Display Data Visualization
        with st.container():
            for cur_chart in cur_task.data:
                st.markdown("---")
                st.subheader(f"📈 {cur_chart.name}")
                # Placeholder for the scatter chart
                scatter_placeholder = st.empty()
                plots_list.append(scatter_placeholder)
            # TODO Shall allow to have multiple scatter. Dynamic array with the same amount of charts as the elements of the curdatalist list
            # Placeholder for the scatter chart
            paused = st.checkbox("Pause Data", False)
            curDataList: List[ChartData] = Tasks._is_running.data
            # Continuously update the chart
            if not paused:
                while Tasks._is_running is not None:
                    for idx, curChartData in enumerate(curDataList):
                        populate_scatter(curChartData, plots_list[idx])
                    # Pause loop button
                    time.sleep(2)
            else:
                for idx, curChartData in enumerate(curDataList):
                    populate_scatter(curChartData, plots_list[idx])
