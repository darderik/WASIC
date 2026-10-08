"""Measurement addon with a named instrument role and validated parameters."""
import time

from tasks import ChartData, ChartData_Config
from wasic_api import TaskSpec, TaskContext, ParameterSpec


def thermal_task_function(ctx: TaskContext) -> None:
    meter = ctx.instruments["meter"]
    meter.beep_state = "disabled"
    meter.mode = "resistance" if ctx.parameters["wires_mode"] == 2 else "resistance 4W"
    meter.auto_range()

    chart = ChartData(
        name="Thermal Tracking - Resistance",
        config=ChartData_Config(
            pop_raw=True, include_raw_on_save=True, atomic_save=True, custom_type="line",
        ),
    )
    chart.configure_x_axis(label="Time", unit="s")
    chart.configure_y_axis(label="Resistance", unit="\u03a9")
    ctx.data.append(chart)
    begin_time = time.monotonic()
    while not ctx.exit_flag.is_set():
        chart.add_processed_pair(time.monotonic() - begin_time, float(meter.resistance))
        ctx.exit_flag.wait(ctx.parameters["update_interval"])


PLUGIN = TaskSpec(
    id="thermal_tracking",
    name="Thermal tracking",
    description="Track thermal sensor resistance using a Keithley 2000 multimeter.",
    run=thermal_task_function,
    instruments={"meter": "keithley2000"},
    parameters={
        "update_interval": ParameterSpec(float, 1.0, minimum=0.01),
        "wires_mode": ParameterSpec(int, 2, choices=(2, 4)),
        "merge_chart_files": ParameterSpec(bool, True),
    },
)
