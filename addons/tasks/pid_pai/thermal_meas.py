import logging
import math
import time
from typing import cast

from tasks import Task, Tasks, ChartData, ChartData_Config
from connections import Connections
from pymeasure.instruments.keithley import Keithley2000




logger = logging.getLogger(__name__)

def thermal_task_function(task_obj: Task) -> None:
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    instr_entry = Connections().get_instrument(keyword="Model 2000")
    if instr_entry is None:
        logger.error("Keithley2000 instrument not found in connections.")
        return
    k2000_instr: Keithley2000 = cast(Keithley2000, instr_entry.scpi_instrument)
    k2000_instr.beep_state = 'disabled'

    # Resistance chart
    resistance_chart = ChartData(
        name="Thermal Tracking - Resistance",
        config=ChartData_Config(
            pop_raw=True,
            include_raw_on_save=True,
            atomic_save=True,
            custom_type="line",
        ),
    )


    resistance_chart.configure_x_axis(label="Time", unit="s")
    resistance_chart.configure_y_axis(label="Resistance", unit="Ω")

    
    
    data.extend([resistance_chart])

    #Fetch parameters
    RES_MODE_WIRE = int(task_obj.parameters.get("wires_mode", "2"))
    begin_time = time.time()

    if RES_MODE_WIRE == 2:
        mode = "resistance"
    elif RES_MODE_WIRE == 4:
        mode = "resistance 4W"
    # Setup the Keithley 2000 for resistance measurement
    k2000_instr.mode = mode
    k2000_instr.auto_range()



    try:
        while not exit_flag.is_set():
            update_interval = float(task_obj.parameters.get("update_interval", "1"))
            res = float(str(k2000_instr.resistance))  # Get resistance measurement
            elapsed_time: float = time.time() - begin_time

            resistance_chart.add_processed_pair(elapsed_time, res)

            # temperature update using the configured formula for the Y series
            temperature_chart.add_processed_x(elapsed_time)
            temperature_chart.add_raw_y(res)

            time.sleep(update_interval)
    except Exception as e:
        logger.error(f"Error in thermal task: {e}")
    finally:
        exit_flag.set()

def init_thermal_tracking_task() -> None:
    """Initialize the thermal tracking task and add it to the tasks list."""
    thermal_task = Task(
        name="Thermal tracking",
        description="A task that tracks the resistance and " \
        "temperature of a thermal sensor over time using a Keithley 2000 multimeter.",
        instrs_aliases=["Model 2000"],
        function=thermal_task_function,
        parameters={
            "update_interval": "1",
            "wires_mode": "2",
            "merge_chart_files": "True",
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(thermal_task)