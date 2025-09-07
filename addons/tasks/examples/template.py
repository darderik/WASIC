from tasks import Task, Tasks, ChartData
import random
from typing import Optional, List, cast
from instruments import Instrument_Entry
from connections import Connections
from ...instruments import RaspberrySIM
import time
from threading import Thread, Event
import math
from ..utilities import spawn_data_processor, generic_processor
import logging


def example_math_formula(x: float) -> float:
    """Calculate the square root of a given float."""
    return math.sqrt(x)


def mytask_1(task_obj: Task) -> None:
    """Main function for My Task 1."""
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    # Setup Data
    cur_chart_data_1: ChartData = ChartData(
        name="Square root of values", math_formula_y=example_math_formula
    )
    data.append(cur_chart_data_1)  # Add the new chart data to the data list

    # Explicit cast required
    conn_object = Connections()
    logger = logging.getLogger(__name__)
    instr_entry: Optional[Instrument_Entry] = conn_object.get_instrument(
        "raspberry"
    )  # May also use serial number
    if instr_entry is not None:
        myInstrument: RaspberrySIM = cast(RaspberrySIM, instr_entry.scpi_instrument)
    else:
        logger.error("Instrument not found")
        exit_flag.set()
        return
    try:
        while not exit_flag.is_set():
            curV = myInstrument.voltp
            cur_chart_data_1.x.append(curV)  # append x
            cur_chart_data_1.raw_y.append(curV)  # append raw y and apply math formula
            myInstrument.voltp = random.uniform(0, 5)  # Set a random voltage value
            time.sleep(1)
    except Exception as e:
        logger.error(f"Error in task: {e}")
    finally:
        exit_flag.set()

def init_mytask_1() -> None:
    """Initialize My Task 1 by creating and adding it to the tasks list."""
    newTask: Task = Task(
        name="My Task 1",
        description="This is the first task",
        instrs_aliases=["raspberry"],
        function=mytask_1,
    )
    tasks_obj = Tasks()  # Add the new task to the tasks list
    tasks_obj.add_task(newTask)


# Add following line to an init file to register the task:
# Tasks.tasks_init_list.append(init_mytask_1)
