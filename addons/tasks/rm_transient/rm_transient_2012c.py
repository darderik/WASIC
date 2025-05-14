from typing import Optional, List
from threading import Thread, Event
from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, TDS2012C
from addons.tasks.utilities import spawn_data_processor, generic_processor
from connections import Connections
import logging
from .rm_transient_uts import calculate_rise_time, calculate_fall_time
import time


def rm_transient(data: List[ChartData], exit_flag: Event) -> None:
    # Setup Data
    transient_rise_chart: ChartData = ChartData(
        name="Transienti in salita",
        math_formula_y=lambda transient: calculate_rise_time(transient),
        pop_raw=True,
        custom_type="histogram",
    )
    transient_fall_chart: ChartData = ChartData(
        name="Transienti in discesa",
        math_formula_y=lambda transient: calculate_fall_time(transient),
        pop_raw=True,
        custom_type="histogram",
    )
    data.append(transient_rise_chart)
    data.append(transient_fall_chart)

    # Init section -----
    conn_object = Connections()
    logger = logging.getLogger(__name__)
    scope_entry: Optional[Instrument_Entry] = conn_object.get_instrument("tds 2012c")
    rm_entry: Optional[Instrument_Entry] = conn_object.get_instrument("relay matrix")

    if scope_entry is None or rm_entry is None:
        logger.error("One or more instruments could not be initialized.")
        return
    scope: TDS2012C = scope_entry.scpi_instrument
    relay_matrix: RelayMatrix = rm_entry.scpi_instrument

    # A single data processor function should handle all charts data associated within the task
    newThreadProcessor: Optional[Thread] = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    scope.reset()
    scope.write("*CLS")
    scope.busy()
    time.sleep(1)
    scope.configure_edge_trigger(
        source="CH2",
        slope="FALL",
        level=1,
        mode="normal",
    )
    scope.set_channel_display(1, True)
    scope.set_channel_display(2, True)
    scope.horizontal_scale(100e-6)
    scope.vertical_position(1, -3)
    scope.vertical_position(2, 1)
    scope.volt_scale_ch1 = 1
    scope.volt_scale_ch2 = 1
    relay_matrix.switch_commute_reset_all()
    relay_matrix.switch_commute_exclusive("a1")
    try:
        while not exit_flag.is_set():
            # Rise acq
            scope.horizontal_position(3e-3)
            relay_matrix.opc()
            scope.single()
            scope.busy()
            relay_matrix.switch_commute_exclusive("a2")
            relay_matrix.opc()
            scope.wait_for_acquisition_complete()
            t, V = scope.get_waveform()
            if t is None or V is None or len(t) == 0 or len(V) == 0:
                logger.error("Failed to acquire waveform data")
                continue
            transient_rise_chart.raw_y.append([t, V])
            # Fall acq
            relay_matrix.opc()
            scope.single()
            scope.busy()
            relay_matrix.switch_commute_exclusive("a1")
            relay_matrix.opc()
            scope.wait_for_acquisition_complete()
            t, V = scope.get_waveform()
            if t is None or V is None or len(t) == 0 or len(V) == 0:
                logger.error("Failed to acquire waveform data")
                continue
            transient_fall_chart.raw_y.append([t, V])

    except Exception as e:
        logger.error(f"Error in task: {e}")
    finally:
        relay_matrix.switch_commute_reset_all()
        exit_flag.set()
        if newThreadProcessor is not None:
            newThreadProcessor.join()


def init_rm_transient_2012() -> None:
    newTask: Task = Task(
        name="RM Transient 2012C",
        description="Measure transient of voltage after a switch",
        instrs_aliases=["tds 2012c", "relay matrix"],
        function=rm_transient,
    )
    tasks_obj = Tasks()  # Add the new task to the tasks list
    tasks_obj.add_task(newTask)


# Add following line to an init file to register the task:
# Tasks.tasks_init_list.append(init_rm_transient)
