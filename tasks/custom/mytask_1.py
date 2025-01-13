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


def mytask_1(data: Dict, exit_flag: Event) -> None:
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
        data["x"] = list()
        # Infinite loop to continuously update the instrument
        while True:
            if exit_flag.is_set():
                break
            # Generate a random integer between 0 and 100
            curInt: int = random.randint(0, 100)

            # Append the random integer to the list in dataProxy
            data["x"].append(curInt)

            # Set the voltage property of the RaspberrySIM instrument to the random integer
            curRPI_cast.voltp = curInt

            # Sleep for 2 seconds before the next iteration
            time.sleep(2)


def init_mytask_1():
    newTask: Task = Task(
        "My Task 1",
        "This is the first task",
        [Connections.get_instrument("raspberry")],
        mytask_1,
    )
    Tasks.tasks_list.append(newTask)
