from ..task import Task
import random
from typing import Optional, Any, Union, Dict
from instruments import Instrument_Entry
from connections import Connections
from multiprocessing.managers import ValueProxy
from instruments import RaspberrySIM
from easy_scpi import Instrument
import time
from threading import Thread, Event, Lock
from ..task import Task, Tasks
from ..structures import ChartData
from typing import List, Optional


def mytask_1(data: List[ChartData], exit_flag: Event) -> None:
    # Check instruments not

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
        cur_chart_data_1: ChartData = ChartData("Example Chart", list(), list())
        data.append(cur_chart_data_1)
        # Infinite loop to continuously update the instrument
        while True:
            if exit_flag.is_set():
                # Do something with data
                break
            # Generate a random integer between 0 and 100
            curRPI_cast.voltp = random.randint(0, 100)
            curRead: float = float(curRPI_cast.voltp)
            # Append the random integer to the list in dataProxy. We want only an axis, thus scatter
            cur_chart_data_1.y.append(curRead)

            # Set the voltage property of the RaspberrySIM instrument to the random integer

            # Sleep for 2 seconds before the next iteration
            time.sleep(1e-6)


def init_mytask_1():
    newTask: Task = Task(
        name="My Task 1",
        description="This is the first task",
        instrs_aliases=["raspberry"],
        function=mytask_1,
    )
    Tasks.tasks_list.append(newTask)
