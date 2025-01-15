import streamlit as st
from typing import List, Optional
import time
from streamlit.delta_generator import DeltaGenerator
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument
from instruments import RaspberrySIM
from tasks import Task, Tasks
from tasks import ChartData


def populate_scatter(chartData, scatter: DeltaGenerator) -> None:
    if chartData.x == []:
        # Plot only scatter
        scatter.scatter_chart(curChartData.y)
    else:
        # Plot scatter with x y
        scatter.scatter_chart({"x": curChartData.x, "y": curChartData.y})


# Set the main title of the page
st.title("🔧 Tasks Selector")

# Check if a task is currently running
is_task_running: bool = Tasks._is_running is not None

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
                        st.write(f"- **ID:** {instr.scpi_instrument.id}")
                else:
                    st.write("No instruments associated with this task.")

            # Stop Task Button
            st.button(
                "🛑 Stop Task",
                on_click=Tasks.kill_task,
                key="stop_task_button",
                help="Stop the currently running task.",
            )

        scatter_placeholder: DeltaGenerator = st.empty()
        # Display Data Visualization
        with st.container():
            st.markdown("---")
            st.subheader("📈 Task Data")

            # TODO Shall allow to have multiple scatter. Dynamic array with the same amount of charts as the elements of the curdatalist list
            # Placeholder for the scatter chart
            paused = st.toggle("Pause Data", False)
            curDataList: List[ChartData] = Tasks._is_running.data
            # Continuously update the chart
            if not paused:
                while Tasks._is_running is not None:
                    for curChartData in curDataList:
                        populate_scatter(curChartData, scatter_placeholder)
                    # Pause loop button
                    time.sleep(2)
            else:
                for curChartData in curDataList:
                    populate_scatter(curChartData, scatter_placeholder)
