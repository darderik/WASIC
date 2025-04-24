import time
from typing import List
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from tasks import ChartData, Task, Tasks
from webapp import plot_chart_native, plot_chart_plotly

tasks_obj = Tasks()


def set_custom_alias() -> None:
    changedAlias: str = st.session_state["task_alias"]
    if tasks_obj._is_running is not None:
        tasks_obj._is_running.custom_alias = changedAlias


# Check if a task is currently running
is_task_running: bool = tasks_obj._is_running is not None


# Set the main title of the page
st.title("🔧 Tasks Selector")

# Task selection widget
with st.container():
    col_task, col_run = st.columns([3, 1])

    relevant_tasks = [
        tsk.name for tsk in tasks_obj._tasks_list if tsk.has_instruments()
    ]
    if relevant_tasks == []:
        st.warning("No tasks available. Connect the instruments and refresh..")
        st.button(
            "Refresh Instruments", on_click=tasks_obj.update_instruments, args=(1,)
        )

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
                on_click=tasks_obj.run_task,
                args=(task_selectbox,),
                disabled=is_task_running,
                key="run_task_button",
                help="Start the selected task.",
            )
        with col_run:
            st.button(
                "🔄 Match Instruments",
                on_click=tasks_obj.update_instruments,
                key="refresh_matched_instruments",
                help="Refresh each task's matched instruments.",
            )

    # Display task details and controls if a task is running
    if is_task_running and tasks_obj._is_running is not None:
        with st.container():
            st.markdown("---")
            st.subheader("⚙️ Current Task")
            cur_task: Task = tasks_obj._is_running

            # Task Details
            with st.expander("📋 Task Details", expanded=True):
                st.markdown(f"**Name:** {cur_task.name}")
                st.markdown(f"**Description:** {cur_task.description}")

            # Instruments Information
            with st.expander("🔌 Instruments", expanded=True):
                if cur_task.instruments != []:
                    for instr in cur_task.instruments:
                        if instr is not None:
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
                    on_click=tasks_obj.stop_task,
                    key="stop_task_button",
                    help="Stop the currently running task.",
                    # disabled=custom_alias == "",
                )
        paused = st.checkbox("Pause Data", False)
        plots_pholder_list: List[DeltaGenerator] = []

        # Custom GUI if specified in the task object
        #   with st.container():

        # Display Data Visualization
        with st.container():
            for cur_chart in cur_task.data:
                st.markdown("---")
                st.subheader(f"📈 {cur_chart.name}")
                # Placeholder for the scatter chart
                scatter_placeholder = st.empty()
                plots_pholder_list.append(scatter_placeholder)
                # Placeholder for the scatter chart
            curDataList: List[ChartData] = tasks_obj._is_running.data
            # Continuously update the chart
            if not paused:
                while tasks_obj._is_running is not None:
                    for idx, curChartData in enumerate(curDataList):
                        plot_chart_native(curChartData, plots_pholder_list[idx])
                    # Pause loop button
                    time.sleep(2)
            else:
                for idx, curChartData in enumerate(curDataList):
                    plot_chart_plotly(curChartData, plots_pholder_list[idx])
