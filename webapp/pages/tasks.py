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
def chart_update_frag(
    curDataList, paused, chart_placeholders, count_placeholders
) -> None:
    if is_task_running and tasks_obj._is_running is not None:
        if len(curDataList) != num_charts:
            st.rerun(scope="app")

        # Update counts and charts
        for idx, curChartData in enumerate(curDataList):
            # Update count information
            with count_placeholders[idx]:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="📊 Raw Data Points",
                        value=f"{len(curChartData.raw_x)} X, {len(curChartData.raw_y)} Y",
                    )
                with col2:
                    st.metric(
                        label="⚡ Processed Data Points",
                        value=f"{len(curChartData.x)} X, {len(curChartData.y)} Y",
                    )

            # Update chart if not paused
            if not paused:
                fig = make_plotly_figure(curChartData)
                chart_placeholders[idx].plotly_chart(
                    fig,
                    use_container_width=True,
                )


# Check if a task is currently running
is_task_running: bool = tasks_obj._is_running is not None

# Set the main title of the page
st.title("🔧 Tasks Selector")

# Task selection widget
with st.container():
    if not is_task_running:
        st.markdown("### 🎯 Select and Run a Task")
    else:
        st.success("✅ Task is currently running")

    col_task, col_run = st.columns([3, 1])

    relevant_tasks = [
        tsk.name for tsk in tasks_obj._tasks_list if tsk.has_instruments()
    ]
    if relevant_tasks == [] and not is_task_running:
        st.warning("⚠️ No tasks available. Connect the instruments and refresh.")
        if st.button(
            "🔄 Refresh Instruments",
            on_click=tasks_obj.update_instruments,
            args=(1,),
            use_container_width=True,
        ):
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
                use_container_width=True,
            )
        with col_run:
            st.button(
                "🔄 Match Instruments",
                on_click=tasks_obj.update_instruments,
                key="refresh_matched_instruments",
                help="Refresh each task's matched instruments.",
                use_container_width=True,
            )

# Display task details and controls if a task is running
if is_task_running and tasks_obj._is_running is not None:
    cur_task: Task = tasks_obj._is_running

    st.markdown("---")
    st.markdown("### ⚙️ Current Task")

    # Task Details in a nice layout
    with st.container():
        col1, col2 = st.columns([2, 1])

        with col1:
            with st.expander("📋 Task Details", expanded=True):
                st.markdown(f"**Name:** `{cur_task.name}`")
                st.markdown(f"**Description:** {cur_task.description}")

        with col2:
            with st.expander("🔌 Instruments", expanded=True):
                if cur_task.instruments:
                    for i, instr in enumerate(cur_task.instruments, 1):
                        if instr is not None:
                            st.markdown(f"**{i}.** `{instr.data.idn}`")
                else:
                    st.info("No instruments associated.")

    # Task Controls Section
    st.markdown("### 🎛️ Task Controls")
    col_alias, col_stop = st.columns([2, 1])

    with col_alias:
        custom_alias: str = st.text_input(
            label="💾 Task Alias",
            value="",
            key="task_alias",
            help="Enter an alias for this task run (used for saving data)",
            on_change=set_custom_alias,
            placeholder="Enter a meaningful name...",
        )

    with col_stop:
        st.markdown("")  # Add spacing to align with text input
        st.markdown("")
        st.button(
            "🛑 Stop Task",
            on_click=tasks_obj.stop_task,
            key="stop_task_button",
            help="Stop the currently running task",
            use_container_width=True,
            type="primary",
        )
    # Custom GUI if specified in the task object
    #   with st.container():
    # Display Data Visualization

# Data Visualization Section
if is_task_running and tasks_obj._is_running is not None:
    st.markdown("---")
    st.markdown("### 📊 Data Visualization")

    running_task: Task = tasks_obj._is_running
    curDataList: Optional[List[ChartData]] = running_task.data

    if curDataList:
        # Control panel
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**Real-time Data Monitoring**")
            with col2:
                paused = st.checkbox("⏸️ Pause Updates", False)

        st.markdown("---")

        # Create placeholders for each chart
        chart_placeholders: List[DeltaGenerator] = []
        count_placeholders: List[DeltaGenerator] = []

        num_charts = len(curDataList)

        for i, chart in enumerate(curDataList):
            # Chart container
            with st.container():
                st.markdown(f"#### 📈 {chart.name}")

                # Metrics row
                count_placeholder: DeltaGenerator = st.empty()
                count_placeholders.append(count_placeholder)

                # Chart row
                chart_placeholder: DeltaGenerator = st.empty()
                chart_placeholders.append(chart_placeholder)

                if i < len(curDataList) - 1:  # Add separator except for last chart
                    st.markdown("---")

        # Handle paused state
        if paused:
            # Show static charts when paused
            for idx, curChartData in enumerate(curDataList):
                # Update static metrics
                with count_placeholders[idx]:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            label="📊 Raw Data Points",
                            value=f"{len(curChartData.raw_x)} X, {len(curChartData.raw_y)} Y",
                        )
                    with col2:
                        st.metric(
                            label="⚡ Processed Data Points",
                            value=f"{len(curChartData.x)} X, {len(curChartData.y)} Y",
                        )

                # Show static chart
                fig = make_plotly_figure(curChartData)
                chart_placeholders[idx].plotly_chart(
                    fig,
                    use_container_width=True,
                )
        else:
            # Use fragment for real-time updates
            chart_update_frag(
                curDataList=curDataList,
                paused=paused,
                chart_placeholders=chart_placeholders,
                count_placeholders=count_placeholders,
            )
    else:
        st.info("⏳ Waiting for data from the running task...")
elif not is_task_running:
    st.info("🚀 Start a task to see real-time data visualization.")
