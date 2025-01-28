from tasks import Task, Tasks, ChartData
from typing import Optional, List
from instruments import Instrument_Entry
from user_defined.instruments import RelayMatrix, K2000
from connections import Connections
import time
from threading import Thread, Event
from user_defined.tasks.utilities import (
    spawn_data_processor,
    apply_formula,
    generic_processor,
)
import sympy as sp
from scipy.optimize import brentq
import numpy as np


conf_sample_thickness: float = 1e-6  # Sample thickness in meters


def van_der_pauw_calculation(
    hor_ver_resistance: List[float], sample_thickness: float = conf_sample_thickness
) -> float:
    """Calculate the resistivity of a sample using the Van der Pauw method."""
    horizontal_resistance, vertical_resistance = hor_ver_resistance
    R_s = sp.Symbol("R_s")  # Sheet resistance
    R_h: float = abs(horizontal_resistance)
    R_v: float = abs(vertical_resistance)
    vdp_equation = sp.Eq(sp.exp(-sp.pi * R_h / R_s) + sp.exp(-sp.pi * R_v / R_s) - 1, 0)
    vdp_numeric_equation = sp.lambdify(R_s, vdp_equation.lhs, modules="numpy")
    try:
        sheet_resistance: float = brentq(vdp_numeric_equation, 1e-20, 1e6)
    except ValueError:
        sheet_resistance = np.nan
    return sheet_resistance


def meas_4w_vdp(data: List[ChartData], exit_flag: Event) -> None:
    """Van der Pauw measurement task."""
    horizontal_resistance_chart: ChartData = ChartData(
        name="Horizontal Resistance",
    )
    vertical_resistance_chart: ChartData = ChartData(
        name="Vertical Resistance",
    )
    vdp_sheet_resistance_chart: ChartData = ChartData(
        name="Van der Pauw Resistivity",
        info="Sheet resistance calculated using the Van der Pauw method. each raw_y element contains [R_h,R_v].",
        math_formula_y=lambda h_v_res: van_der_pauw_calculation(h_v_res),
    )
    data.extend(
        [
            horizontal_resistance_chart,
            vertical_resistance_chart,
            vdp_sheet_resistance_chart,
        ]
    )
    # Fetch relay matrix and k2000 maybe with SN
    relay_matrix_entry: Optional[Instrument_Entry] = Connections.get_instrument(
        "relay matrix"
    )
    k2000_entry: Optional[Instrument_Entry] = Connections.get_instrument("model 2000")

    if relay_matrix_entry is None or k2000_entry is None:
        return
    relay_matrix: RelayMatrix = relay_matrix_entry.scpi_instrument
    k2000: K2000 = k2000_entry.scpi_instrument

    newThreadProcessor: Thread = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    # Configure Instruments
    k2000.configure_4w_resistance()
    relay_matrix.switch_commute_reset_all()

    while True:
        # Measure horizontal resistance
        relay_matrix.switch_commute_exclusive("a1", "b2", "c3", "d4")
        relay_matrix.opc()
        horizontal_resistance: float = k2000.read_measurement()

        # Measure vertical resistance
        relay_matrix.switch_commute_exclusive("a2", "b3", "c4", "d1")
        relay_matrix.opc()
        vertical_resistance: float = k2000.read_measurement()

        # Update the charts
        horizontal_resistance_chart.y.append(horizontal_resistance)
        vertical_resistance_chart.y.append(vertical_resistance)

        # Different structure, needed for computign the sheet resistance
        vdp_sheet_resistance_chart.raw_y.append(
            [horizontal_resistance, vertical_resistance]
        )
        if exit_flag.is_set():
            newThreadProcessor.join()
            break  # Exit the loop if the exit flag is set

        time.sleep(1)


def init_4w_vdp() -> None:
    newTask: Task = Task(
        name="VDP Meas K2000+RM",
        description="4W measure using Keithley 2000 and relay matrix",
        instrs_aliases=["model 2000", "relay matrix"],
        function=meas_4w_vdp,
    )
    Tasks.tasks_list.append(newTask)  # Add the new task to the tasks list


# Add the task initialization function to the list of task initialization functions
Tasks.tasks_init_list.append(init_4w_vdp)
