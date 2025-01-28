from tasks import Task, Tasks, ChartData
import random
from typing import Optional, Any, Union, Dict, List
from instruments import Instrument_Entry
from connections import Connections
from multiprocessing.managers import ValueProxy
from ...instruments import RaspberrySIM
from easy_scpi import Instrument
import time
from threading import Thread, Event, Lock
import math
from ..utilities import spawn_data_processor, apply_formula, generic_processor


def example_math_formula(x: float) -> float:
    """Calculate the square root of a given float."""
    return math.sqrt(x)


def mytask_1(data: List[ChartData], exit_flag: Event) -> None:
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

    # Get the instrument entry for "raspberry" from Connections
    curRPI_Entry: Optional[Instrument_Entry] = Connections.get_instrument("raspberry")

    # Get the SCPI instrument from the entry if it exists, otherwise set to None
    curRPI: Optional[Instrument] = (
        curRPI_Entry.scpi_instrument if curRPI_Entry is not None else None
    )

    # If the SCPI instrument is found
    if curRPI is not None:
        # Cast the SCPI instrument to a RaspberrySIM type
        # So we can access custom properties and methods
        curRPI_cast: RaspberrySIM = curRPI
        # Infinite loop to continuously update the instrument
        while True:
            if exit_flag.is_set():
                newThreadProcessor.join()
                break  # Exit the loop if the exit flag is set
            # Generate a random integer between 0 and 100
            # Send SCPI set of voltage property
            curRPI_cast.voltp = random.randint(0, 100)
            curRead: float = float(curRPI_cast.voltp)  # Convert voltage to float

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


def init_mytask_1() -> None:
    """Initialize My Task 1 by creating and adding it to the tasks list."""
    newTask: Task = Task(
        name="My Task 1",
        description="This is the first task",
        instrs_aliases=["raspberry"],
        function=mytask_1,
    )
    Tasks.tasks_list.append(newTask)  # Add the new task to the tasks list


# Add the task initialization function to the list of task initialization functions
Tasks.tasks_init_list.append(init_mytask_1)
