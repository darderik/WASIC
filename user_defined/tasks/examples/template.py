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
