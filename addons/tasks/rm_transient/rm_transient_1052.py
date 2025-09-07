from typing import Optional, List, cast
from threading import Thread, Event
import time
from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, TBS1052C
from addons.tasks.utilities import spawn_data_processor, generic_processor
from connections import Connections
import logging
from .rm_transient_uts import calculate_rise_time, calculate_fall_time


def rm_transient(task_obj: Task) -> None:
    data = task_obj.data
    exit_flag = task_obj.exit_flag
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
    scope_entry: Optional[Instrument_Entry] = conn_object.get_instrument("tbs1052c")
    rm_entry: Optional[Instrument_Entry] = conn_object.get_instrument("relay matrix")

    if scope_entry is None or rm_entry is None:
        logger.error("One or more instruments could not be initialized.")
        return
    scope: TBS1052C = cast(TBS1052C, scope_entry.scpi_instrument)
    relay_matrix: RelayMatrix = cast(RelayMatrix, rm_entry.scpi_instrument)

    # A single data processor function should handle all charts data associated within the task
    newThreadProcessor: Optional[Thread] = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    # End of Init section -----
    points: int = 2000
    # Scope setup
    time.sleep(1)
    # Setup trigger with fall detection
    scope.trigger_config(
        source=2,
        slope="RISE",
        level=1,
        mode="normal",
    )
    # Hard coded positioning
    scope.vertical_position(1, -3)
    scope.vertical_position(2, 1)
    scope.vertical_scale(1, 1)
    scope.vertical_scale(2, 1)
    scope.horizontal_position(3e-3)
    # Data setup
    scope.acquire_toggle(False)
    scope.initialize_waveform_settings(
        points=points,
    )
    # Reset and ground (A1)
    relay_matrix.switch_commute_reset_all()
    relay_matrix.switch_commute_exclusive("a1")

    try:
        while not exit_flag.is_set():
            # Rise sequence
            # Set 25us for rise sequence
            scope.time_scale = 25e-6
            relay_matrix.opc()

            scope.single()
            # NCS trigger
            relay_matrix.switch_commute_exclusive("a2")
            relay_matrix.opc()
            scope.wait()
            t_rise, V_rise = scope.get_waveform(points=points)
            scope.acquire_toggle(False)
            scope.wait()
            # Set 1ms for fall sequence
            scope.time_scale = 1e-3
            scope.horizontal_position(2.3e-3)

            # Arm trigger
            scope.single()
            # NCS trigger
            relay_matrix.switch_commute_exclusive("a1")
            relay_matrix.opc()
            scope.wait()
            t_fall, V_fall = scope.get_waveform(points=points)

            # Data processing
            if t_rise is None or V_rise is None or len(t_rise) == 0 or len(V_rise) == 0:
                logger.error("Failed to acquire waveform data")
                continue
            transient_rise_chart.raw_y.append([t_rise, V_rise])
            # Fall sequence
            if t_fall is None or V_fall is None or len(t_fall) == 0 or len(V_fall) == 0:
                logger.error("Failed to acquire fall waveform data")
                continue
            transient_fall_chart.raw_y.append([t_fall, V_fall])
            scope.acquire_toggle(False)
            scope.wait()

    except Exception as e:
        logger.error(f"Error in task: {e}")
    finally:
        relay_matrix.switch_commute_reset_all()
        exit_flag.set()
        if newThreadProcessor is not None:
            newThreadProcessor.join()


def init_rm_transient_1052() -> None:
    newTask: Task = Task(
        name="RM Transient 1052C",
        description="Measure transient of voltage after a switch",
        instrs_aliases=["tbs1052c", "relay matrix"],
        function=rm_transient,
    )
    tasks_obj = Tasks()  # Add the new task to the tasks list
    tasks_obj.add_task(newTask)
