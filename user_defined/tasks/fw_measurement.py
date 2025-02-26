from typing import Optional, List
from threading import Thread, Event
import time
import sympy as sp
from scipy.optimize import brentq
import numpy as np

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from user_defined.instruments import RelayMatrix, K2000
from user_defined.tasks.utilities import spawn_data_processor, generic_processor
from connections import Connections


conf_sample_thickness: float = 1e-6  # Sample thickness in meters


def meas_4w_vdp(data: List[ChartData], exit_flag: Event) -> None:
    """
    Performs a Van der Pauw measurement task, measuring horizontal and vertical resistances
    using preconfigured instruments and updating the relevant ChartData objects with these
    values in real time.
    Parameters:
        data (List[ChartData]): A list of ChartData instances to be updated with measured
            values and calculation results. New ChartData objects for horizontal
            resistance, vertical resistance, and van der Pauw resistivity are appended
            to this list.
        exit_flag (Event): An event used to signal that measurement should stop. When
            set, the function will exit after properly closing the data processing thread.
    Returns:
        None: This function runs indefinitely until the exit_flag is set, at which point
        it terminates.
    Behavior:
        1. Initializes and configures the relay matrix and the K2000 meter for
           four-wire resistance measurements.
        2. Spawns a data processing thread to handle measurements in the background.
        3. Repeatedly switches relay connections to measure both horizontal and vertical
           resistances, appending these readings to respective ChartData objects.
        4. Uses collected horizontal and vertical resistances to compute and store
           the sheet resistance based on the Van der Pauw method.
        5. Terminates gracefully when the exit_flag is set, ensuring the data processing
           thread is properly joined before returning.
    """
    """Van der Pauw measurement task."""
    horizontal_resistance_chart: ChartData = ChartData(
        name="Horizontal Resistance",
        y_label="Resistance (Ohm)",
    )
    vertical_resistance_chart: ChartData = ChartData(
        name="Vertical Resistance",
        y_label="Resistance (Ohm)",
    )
    vdp_sheet_resistance_chart: ChartData = ChartData(
        name="Van der Pauw Resistivity",
        info="Sheet resistance calculated using the Van der Pauw method. each raw_y element contains [R_h,R_v].",
        math_formula_y=lambda h_v_res: van_der_pauw_calculation(h_v_res),
        x_label="Samples",
        y_label="Sheet Resistance (Ohm/sq)",
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

    # Thread creation
    newThreadProcessor: Thread = spawn_data_processor(
        data, exit_flag, generic_processor
    )

    # Configure Instruments
    k2000.disable_beep()
    k2000.configure_4w_resistance(nplc=10)
    relay_matrix.switch_commute_reset_all()

    while True:
        # Measure horizontal resistance
        relay_matrix.switch_commute_exclusive("a1", "b2", "c3", "d4")
        relay_matrix.opc()
        time.sleep(0.5)
        horizontal_resistance: float = k2000.read_measurement()

        # Measure vertical resistance
        relay_matrix.switch_commute_exclusive("a2", "b3", "c4", "d1")
        relay_matrix.opc()
        time.sleep(0.5)
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

        time.sleep(2)


def van_der_pauw_calculation(
    hor_ver_resistance: List[float], sample_thickness: float = conf_sample_thickness
) -> float:
    """Calculate the sheet resistance of a sample using the Van der Pauw method."""
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
