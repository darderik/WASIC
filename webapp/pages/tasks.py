import time
from typing import List, Optional
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from tasks import ChartData, Task, Tasks
from webapp import (
    make_plotly_figure,
)

tasks_obj = Tasks()


def set_custom_alias() -> None:
    changedAlias: str = st.session_state["task_alias"]
    if tasks_obj._is_running is not None:
        tasks_obj._is_running.custom_alias = changedAlias


@st.fragment(run_every=2)
def chart_update_frag(curDataList, paused, placeholders) -> None:
    if is_task_running and tasks_obj._is_running is not None:
        if len(curDataList) != num_charts:
            st.rerun(scope="app")
        if not paused and curDataList:
            for idx, curChartData in enumerate(curDataList):
                fig = make_plotly_figure(curChartData)
                placeholders[idx].plotly_chart(
                    fig,
                    use_container_width=True,
                )


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
    if relevant_tasks == [] and not is_task_running:
        st.warning("No tasks available. Connect the instruments and refresh..")
        refresh = st.button(
            "Refresh Instruments", on_click=tasks_obj.update_instruments, args=(1,)
        )
        if refresh:
            st.rerun(scope="app")

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
    # Custom GUI if specified in the task object
    #   with st.container():
    # Display Data Visualization

with st.expander("📊 Data Visualization", expanded=True):
    running_task: Optional[Task] = tasks_obj._is_running
    if running_task is not None:
        curDataList: Optional[List[ChartData]] = running_task.data
        chart_placeholders: List[DeltaGenerator] = []
        count_placeholders: List[DeltaGenerator] = []
        if tasks_obj._is_running is not None:
            cur_charts = cur_task.data
            num_charts = len(cur_charts)
            for chart in cur_charts:
                # Create separate placeholders for counts and charts
                count_placeholder: DeltaGenerator = st.empty()
                chart_placeholder: DeltaGenerator = st.empty()

                # Display counts in the count placeholder
                with count_placeholder:
                    st.title(chart.name)
                    st.title(
                        f"Current X Y Raw count: {len(chart.raw_x)},{len(chart.raw_y)}"
                    )
                    st.title(
                        f"Current X Y Processed count: {len(chart.x)},{len(chart.y)}"
                    )

                # Append placeholders to respective lists
                count_placeholders.append(count_placeholder)
                chart_placeholders.append(chart_placeholder)

            st.markdown("---")
            paused = st.checkbox("Pause Data", False)
            if paused:
                if curDataList is not None:
                    for idx, curChartData in enumerate(curDataList):
                        fig = make_plotly_figure(curChartData)
                        chart_placeholders[idx].plotly_chart(
                            fig,
                            use_container_width=True,
                        )
            else:
                chart_update_frag(
                    curDataList=curDataList,
                    paused=paused,
                    placeholders=chart_placeholders,
                )
