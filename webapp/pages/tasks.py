from typing import List, Optional, cast

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from tasks import ChartData, Task, Tasks
from webapp import make_plotly_figure


tasks_obj = Tasks()

CHART_TYPES = ["scatter", "line", "histogram"]


def update_task_alias() -> None:
    if tasks_obj._is_running is not None:
        tasks_obj._is_running.custom_alias = st.session_state.get("task_alias", "")


def render_data_metrics(chart: ChartData) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Raw data points",
            f"{len(chart.x_series.raw)} X, {len(chart.y_series.raw)} Y",
        )

    with col2:
        st.metric(
            "Processed data points",
            f"{len(chart.x_series.processed)} X, {len(chart.y_series.processed)} Y",
        )


def get_latest_common_index(charts: List[ChartData]) -> int:
    indices = []

    for chart in charts:
        x_count = len(chart.x_series.processed) if chart.x_series else 0
        y_count = len(chart.y_series.processed) if chart.y_series else 0

        if chart.x_series and chart.y_series:
            indices.append(min(x_count, y_count))
        else:
            indices.append(max(x_count, y_count))

    return max(min(indices), 0) if indices else 0


@st.fragment(run_every=2)
def update_charts(
    data: List[ChartData],
    paused: bool,
    chart_placeholders: List[DeltaGenerator],
    metric_placeholders: List[DeltaGenerator],
) -> None:
    if paused or tasks_obj._is_running is None:
        return

    for idx, chart in enumerate(data[: len(chart_placeholders)]):
        with metric_placeholders[idx]:
            render_data_metrics(chart)

        fig = make_plotly_figure(chart)
        chart_placeholders[idx].plotly_chart(fig, use_container_width=True)


is_task_running = tasks_obj._is_running is not None
available_tasks = [
    task.name for task in tasks_obj._tasks_list if task.has_instruments()
]


st.title("Task Manager")
st.caption("Select a task, configure its parameters, and monitor live data.")

if not available_tasks and not is_task_running:
    st.warning("No tasks are available. Check the connected instruments and refresh.")

    if st.button(
        "Refresh instruments",
        on_click=tasks_obj.update_instruments,
        args=(1,),
        use_container_width=True,
    ):
        st.rerun(scope="app")

else:
    st.header("Task setup")

    task_col, config_col, action_col = st.columns([1.5, 2, 1])

    with task_col:
        st.subheader("Task")

        if is_task_running and tasks_obj._is_running is not None:
            running_name = tasks_obj._is_running.name
            default_index = (
                available_tasks.index(running_name)
                if running_name in available_tasks
                else 0
            )
        else:
            default_index = 0

        selected_task_name = st.selectbox(
            "Select task",
            available_tasks,
            index=default_index,
            disabled=is_task_running,
        )

    with config_col:
        st.subheader("Parameters")

        selected_task = tasks_obj.get_task(selected_task_name)

        if selected_task is not None:
            parameters = selected_task.parameters or {}

            if selected_task.spec:
                edited_parameters = {}
                for name, parameter in selected_task.spec.parameters.items():
                    value = parameters.get(name, parameter.default)
                    widget_key = f"params_{selected_task.id}_{name}"
                    if parameter.choices:
                        edited_parameters[name] = st.selectbox(
                            name, parameter.choices,
                            index=parameter.choices.index(value), key=widget_key,
                            disabled=is_task_running,
                        )
                    elif parameter.type is bool:
                        edited_parameters[name] = st.checkbox(
                            name, value=bool(value), key=widget_key, disabled=is_task_running,
                        )
                    elif parameter.type in (int, float):
                        convert = parameter.type
                        edited_parameters[name] = st.number_input(
                            name, value=convert(value),
                            min_value=convert(parameter.minimum) if parameter.minimum is not None else None,
                            max_value=convert(parameter.maximum) if parameter.maximum is not None else None,
                            key=widget_key, disabled=is_task_running,
                        )
                    else:
                        edited_parameters[name] = st.text_input(
                            name, value=str(value), key=widget_key, disabled=is_task_running,
                        )
            else:
                edited_parameters = st.data_editor(
                    parameters, key=f"params_{selected_task.name}",
                    use_container_width=True, num_rows="dynamic", disabled=is_task_running,
                )

            if st.button(
                "Save parameters",
                use_container_width=True,
                type="secondary",
                disabled=is_task_running,
            ):
                if edited_parameters != parameters:
                    try:
                        selected_task.parameters = (
                            selected_task.spec.parse_parameters(edited_parameters)
                            if selected_task.spec else edited_parameters
                        )
                        st.success("Parameters updated.")
                    except (ValueError, TypeError) as exc:
                        st.error(str(exc))
                else:
                    st.info("No parameter changes to save.")

    with action_col:
        st.subheader("Actions")

        st.button(
            "Run task",
            on_click=tasks_obj.run_task,
            args=(selected_task_name,),
            disabled=is_task_running,
            key="run_task_button",
            use_container_width=True,
            type="primary",
        )

        st.button(
            "Refresh instruments",
            on_click=tasks_obj.update_instruments,
            key="refresh_matched_instruments",
            use_container_width=True,
            type="secondary",
        )


if is_task_running and tasks_obj._is_running is not None:
    running_task: Task = tasks_obj._is_running

    st.divider()
    st.header("Running task")

    details_col, instruments_col = st.columns([2, 1])

    with details_col:
        with st.container(border=True):
            st.subheader("Details")
            st.markdown(f"**Name:** `{running_task.name}`")

            if running_task.description:
                st.markdown(f"**Description:** {running_task.description}")
            else:
                st.caption("No description available.")

    with instruments_col:
        with st.container(border=True):
            st.subheader("Instruments")

            if running_task.instruments:
                for index, instrument in enumerate(running_task.instruments, start=1):
                    if instrument is not None:
                        st.markdown(f"**{index}.** `{instrument.data.idn}`")
            else:
                st.info("No instruments associated with this task.")

    alias_col, stop_col = st.columns([3, 1])

    with alias_col:
        st.text_input(
            "Task alias",
            value=running_task.custom_alias or "",
            key="task_alias",
            on_change=update_task_alias,
            help="Optional custom name for the running task.",
        )

    with stop_col:
        st.write("")
        st.button(
            "Stop task",
            on_click=tasks_obj.stop_task,
            key="stop_task_button",
            use_container_width=True,
            type="primary",
        )


if is_task_running and tasks_obj._is_running is not None:
    running_task = tasks_obj._is_running
    data: Optional[List[ChartData]] = running_task.data

    st.divider()
    st.header("Live data")

    if not data:
        st.info("Waiting for data from the running task...")
    else:
        plot_from_index_key = f"plot_from_index_{running_task.name}"

        shared_start_indices = {chart.config.start_index for chart in data}
        default_start_index = (
            shared_start_indices.pop()
            if len(shared_start_indices) == 1
            else 0
        )

        if plot_from_index_key not in st.session_state:
            st.session_state[plot_from_index_key] = default_start_index

        with st.container(border=True):
            st.subheader("Display controls")

            reset_col, all_col, pause_col, index_col = st.columns([1, 1, 1, 1])

            with reset_col:
                if st.button("Reset view", use_container_width=True):
                    start_index = get_latest_common_index(data)

                    for chart in data:
                        chart.config.start_index = start_index

                    st.session_state[plot_from_index_key] = start_index

            with all_col:
                if st.button("Show all data", use_container_width=True):
                    for chart in data:
                        chart.config.start_index = 0

                    st.session_state[plot_from_index_key] = 0

            with pause_col:
                paused = st.checkbox("Pause updates", value=False)

            with index_col:
                st.number_input(
                    "Start index",
                    min_value=0,
                    step=1,
                    key=plot_from_index_key,
                )

        plot_from_index = st.session_state[plot_from_index_key]

        for chart in data:
            chart.config.start_index = plot_from_index

        chart_placeholders: List[DeltaGenerator] = []
        metric_placeholders: List[DeltaGenerator] = []

        for idx, chart in enumerate(data):
            chart = cast(ChartData, chart)

            with st.container(border=True):
                st.subheader(chart.name)

                current_type = (
                    chart.config.custom_type
                    if chart.config.custom_type in CHART_TYPES
                    else "scatter"
                )

                chart.config.custom_type = st.selectbox(
                    "Chart type",
                    CHART_TYPES,
                    index=CHART_TYPES.index(current_type),
                    key=f"chart_type_{running_task.name}_{idx}",
                )

                metric_placeholder = st.empty()
                chart_placeholder = st.empty()

                metric_placeholders.append(metric_placeholder)
                chart_placeholders.append(chart_placeholder)

                if paused:
                    with metric_placeholder:
                        render_data_metrics(chart)

                    fig = make_plotly_figure(chart)
                    chart_placeholder.plotly_chart(fig, use_container_width=True)

        update_charts(
            data=data,
            paused=paused,
            chart_placeholders=chart_placeholders,
            metric_placeholders=metric_placeholders,
        )

elif not is_task_running:
    st.info("Start a task to display live data.")