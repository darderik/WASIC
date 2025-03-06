import time
import math
from threading import Thread, Event, Lock
from typing import List
from multiprocessing.managers import ValueProxy

from ...instruments import K2000
from easy_scpi import Instrument
from ..utilities import spawn_data_processor, apply_formula, generic_processor
from tasks import ChartData, Task, Tasks
import random
from typing import Optional, Any, Union, Dict
from instruments import Instrument_Entry
from connections import Connections


def example_math_formula(x: float) -> float:
    """Calculate the square root of a given float."""
    return math.sqrt(abs(x))


def mytask_k2000(data: List[ChartData], exit_flag: Event) -> None:
    """Main function for My Task 1."""
    # Setup Data
    cur_chart_data_1: ChartData = ChartData(
        name="Square root of values", math_formula_y=example_math_formula
    )
    cur_chart_data_2: ChartData = ChartData(
        name="Real values vs Square root", math_formula_y=example_math_formula
    )
    data.append(cur_chart_data_1)  # Add the new chart data to the data list
    data.append(cur_chart_data_2)  # Add the new chart data to the data list

    # A single data processor function should handle all charts data associated within the task
    newThreadProcessor: Thread = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    newThreadProcessor.start()
    # Connections singleton
    connections_obj: Connections = Connections()
    # Get the instrument entry for "raspberry" from Connections
    curK2000_entry: Optional[Instrument_Entry] = connections_obj.get_instrument(
        "Model 2000"
    )

    # Get the SCPI instrument from the entry if it exists, otherwise set to None
    curK2000: Optional[K2000] = (
        curK2000_entry.scpi_instrument if curK2000_entry is not None else None
    )

    # If the SCPI instrument is found
    if curK2000 is not None:
        curK2000.measure_voltage_dc()

        curK2000.autorange = 1

        # Cast the SCPI instrument to a RaspberrySIM type
        # So we can access custom properties and methods
        K2000_cast: K2000 = curK2000
        # Infinite loop to continuously update the instrument
        while True:
            if exit_flag.is_set():
                newThreadProcessor.join()
                break  # Exit the loop if the exit flag is set
            # Generate a random integer between 0 and 100

            # Send SCPI set of voltage property
            curRead: float = float(
                K2000_cast.read_measurement()
            )  # Convert voltage to float

            # Update the chart data with the new read value
            if cur_chart_data_1.math_formula_y is not None:
                cur_chart_data_1.raw_y.append(curRead)  # Update raw y data
            else:
                cur_chart_data_1.y.append(curRead)  # Update y data directly

            cur_chart_data_2.raw_y.append(curRead)  # Update raw y data
            cur_chart_data_2.x.append(curRead)  # Update x data

            # Set the voltage property of the RaspberrySIM instrument to the random integer
            # (Assuming additional operations here)

            # Sleep for a very short duration before the next iteration
            time.sleep(1)


def init_mytask_k2000() -> None:
    """Initialize My Task 1 by creating and adding it to the tasks list."""
    newTask: Task = Task(
        name="K2000 task",
        description="This is the first task",
        instrs_aliases=["Model 2000"],
        function=mytask_k2000,
    )
    tasks_obj: Tasks = Tasks()
    tasks_obj.add_task(newTask)  # Add the new task to the tasks list
