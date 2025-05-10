from typing import Optional, List
from threading import Thread, Event
import time
import sympy as sp
from scipy.optimize import brentq
import numpy as np

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from user_defined.instruments import RelayMatrix, K2000, TDS2012
from user_defined.tasks.utilities import spawn_data_processor, generic_processor
from connections import Connections
import logging


def lin_fit(point1: List[float], point2: List[float], threshold: float) -> float:
    x1 = point1[0]
    y1 = point1[1]
    x2 = point2[0]
    y2 = point2[1]
    rise_time = (x2 - x1) / (y2 - y1) * (threshold - y1) + x1
    return abs(rise_time)


def calculate_rise_time(transient_pack: List[List[float]]) -> float:
    """
    Calculates the rise time of a transient signal.

    Args:
        transient_pack (List[List[float]]): A list containing two lists:
            - [0]: Time values
            - [1]: Voltage values

    Returns:
        float: The rise time (time difference between the start and end of the rise).
               Returns NaN if no valid rise is detected.
    """
    # Define thresholds
    high_threshold = 1  # Voltage threshold to end the rise

    # Extract time and voltage arrays
    cur_time = np.array(transient_pack[0])
    cur_voltage = np.array(transient_pack[1])

    # Find the first index where voltage exceeds the zero threshold
    start_index = np.argmax(cur_voltage > high_threshold)
    if start_index != 0:
        pre_start_index = start_index - 1
        above_threshold_point = [cur_time[start_index], cur_voltage[start_index]]
        below_threshold_point = [
            cur_time[pre_start_index],
            cur_voltage[pre_start_index],
        ]
        # Interpolate to find the time at which voltage crosses the zero threshold
        zero_cross_time = lin_fit(
            below_threshold_point, above_threshold_point, high_threshold
        )
    if zero_cross_time is None:
        return np.nan
    else:
        return zero_cross_time


def rm_transient(data: List[ChartData], exit_flag: Event) -> None:
    # Setup Data
    transient_rise_chart: ChartData = ChartData(
        name="Transienti in salita",
        math_formula_y=lambda transient: calculate_rise_time(transient),
    )
    data.append(transient_rise_chart)

    #    transient_fall_chart: ChartData = ChartData(
    #        name="Transienti in discesa",
    #        math_formula_y=lambda transient: calculate_fall_time(transient),
    #    )
    #    data.append(transient_fall_chart)
    # Add the charts to the data list

    # Init section -----
    conn_object = Connections()
    logger = logging.getLogger(__name__)
    scope_entry: Optional[Instrument_Entry] = conn_object.get_instrument("tds 2012")
    rm_entry: Optional[Instrument_Entry] = conn_object.get_instrument("relay matrix")

    if scope_entry is None or rm_entry is None:
        logger.error("One or more instruments could not be initialized.")
        return
    scope: TDS2012 = scope_entry.scpi_instrument
    relay_matrix: RelayMatrix = rm_entry.scpi_instrument

    # A single data processor function should handle all charts data associated within the task
    newThreadProcessor: Optional[Thread] = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    # End of Init section -----

    scope.write("*CLS")
    scope.configure_edge_trigger(
        source="CH2",
        slope="FALL",
        level=1,
        mode="normal",
    )
    scope.horizontal_scale(500e-6)
    scope.horizontal_position(1.5e-3)
    scope.write("ACQ:STATE STOP")
    relay_matrix.switch_commute_reset_all()
    try:
        while not exit_flag.is_set():
            relay_matrix.opc()
            scope.trigger_run()
            scope.busy()
            relay_matrix.switch_commute_exclusive("a2")
            relay_matrix.opc()
            scope.wait_for_acquisition_complete()
            t, V = scope.get_waveform()
            relay_matrix.switch_commute_exclusive("a1")
            if t is None or V is None or len(t) == 0 or len(V) == 0:
                logger.error("Failed to acquire waveform data")
                continue
            scope.write("ACQ:STATE STOP")
            transient_rise_chart.raw_y.append([t, V])
    except Exception as e:
        logger.error(f"Error in task: {e}")
    finally:
        relay_matrix.switch_commute_reset_all()
        exit_flag.set()
        if newThreadProcessor is not None:
            newThreadProcessor.join()


def init_rm_transient() -> None:
    newTask: Task = Task(
        name="RM Transient",
        description="Measure transient of voltage after a switch",
        instrs_aliases=["tds 2012"],
        function=rm_transient,
    )
    tasks_obj = Tasks()  # Add the new task to the tasks list
    tasks_obj.add_task(newTask)


# Add following line to an init file to register the task:
# Tasks.tasks_init_list.append(init_rm_transient)
