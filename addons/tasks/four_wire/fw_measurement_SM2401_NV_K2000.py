from typing import Optional, List, cast
from threading import Thread, Event
import time
import sympy as sp
from scipy.optimize import brentq
import numpy as np

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, K2000, SM2401, NV34420
from addons.tasks.utilities import spawn_data_processor, generic_processor
from connections import Connections
import streamlit as st


def meas_4w_vdp(data: List[ChartData], exit_flag: Event) -> None:
    """
    Performs a four-wire resistance measurement using the Van der Pauw method.

    This task performs the following steps:
      1. Creates and updates ChartData objects for horizontal resistance, vertical resistance,
         sheet resistance, and temperature (derived from probe resistance).
      2. Retrieves the required instrument entries (relay matrix, K2000, SM2401, and NV34420).
      3. Configures each instrument for the measurement.
      4. Spawns a background data processing thread.
      5. Enters a loop that:
           a. Alternates relay connections to measure horizontal and vertical resistances.
           b. Employs a delta measurement technique
           c. Calculates the sheet resistance via the Van der Pauw method.
           d. Updates the ChartData objects accordingly.
      6. Exits loop and cleans up once the exit_flag is set.

    Parameters:
        data (List[ChartData]): List of ChartData objects to which measured values are appended.
        exit_flag (Event): Event to signal when to terminate the measurement loop.
    """
    # Initialize ChartData objects
    horizontal_chart = ChartData(
        name="Horizontal Resistance",
        y_label="Resistance (Ohm)",
    )
    vertical_chart = ChartData(
        name="Vertical Resistance",
        y_label="Resistance (Ohm)",
    )
    temperature_chart = ChartData(
        name="Temperature vs Probe Resistance",
        y_label="Temperature (K)",
        x_label="Probe Resistance (Ohm)",
        math_formula_y=lambda resistance: R_probe_temp(resistance),
    )
    sheet_resistance_chart = ChartData(
        name="Van der Pauw Sheet Resistance",
        info="Sheet resistance calculated using the Van der Pauw method. Each raw_y element contains [R_h, R_v].",
        math_formula_y=lambda res_pair: van_der_pauw_calculation(res_pair),
        math_formula_x=lambda resistance: R_probe_temp(resistance),
        x_label="Temperature (K)",
        y_label="Sheet Resistance (Ohm/sq)",
    )
    data.extend(
        [
            horizontal_chart,
            vertical_chart,
            sheet_resistance_chart,
            temperature_chart,
        ]
    )
    # Connections singleton
    connection_obj: Connections = Connections()

    # Retrieve instruments
    relay_entry: Optional[Instrument_Entry] = connection_obj.get_instrument(
        "relay matrix"
    )
    k2000_entry: Optional[Instrument_Entry] = connection_obj.get_instrument(
        "model 2000"
    )
    sm2401_entry: Optional[Instrument_Entry] = connection_obj.get_instrument(
        "model 2401"
    )
    nv34420_entry: Optional[Instrument_Entry] = connection_obj.get_instrument("34420A")

    if (
        relay_entry is None
        or k2000_entry is None
        or sm2401_entry is None
        or nv34420_entry is None
    ):
        return

    # Get SCPI instrument objects
    relay_matrix: RelayMatrix = cast(RelayMatrix, relay_entry.scpi_instrument)
    k2000: K2000 = cast(K2000, k2000_entry.scpi_instrument)
    sm2401: SM2401 = cast(SM2401, sm2401_entry.scpi_instrument)
    nv34420: NV34420 = cast(NV34420, nv34420_entry.scpi_instrument)

    # Configure instruments
    k2000.disable_beep()
    sm2401.disable_beep()
    k2000.configure_2w_resistance(nplc=3)
    sm2401.output_off()
    sm2401.configure_current_source(current=1e-3, compliance=1e-3)
    sm2401.configure_current_measure(nplc=5)
    nv34420.configure_voltage(nplc=10)
    relay_matrix.switch_commute_reset_all()

    # Main measurement loop
    while not exit_flag.is_set():
        # Relay configurations: first for horizontal (R_h) and then vertical (R_v) measurement
        relay_configurations = [
            ["a1", "b2", "c3", "d4"],  # Horizontal measurement
            ["a2", "b1", "c4", "d3"],  # Vertical measurement
        ]
        measured_resistances: List[float] = []
        probe_resistances: List[float] = []
        sm2401.output_on()

        for config in relay_configurations:
            # Read the probe resistance before switching relays
            # probe_R = k2000.read_measurement()

            # Switch relay configuration
            relay_matrix.switch_commute(*config)

            # Perform delta measurements due to thermo-electric effects
            probe_resistances.append(k2000.read_measurement())
            sm2401.current = abs(sm2401.current)
            time.sleep(11e-3)  # Wait for the current to stabilize with autorange on
            I_pos = sm2401.read_meas()
            V_pos = nv34420.read_meas()  # TODO: sleep?

            probe_resistances.append(k2000.read_measurement())
            sm2401.current = -abs(sm2401.current)
            time.sleep(11e-3)
            I_neg = sm2401.read_meas()
            V_neg = nv34420.read_meas()

            # Calculate corrected voltage and average current
            V_corr = (V_pos - V_neg) / 2
            I_avg = (I_pos + I_neg) / 2
            resistance = V_corr / I_avg if I_avg != 0 else np.nan
            measured_resistances.append(resistance)

        # Update charts with the new readings
        horizontal_chart.y.append(measured_resistances[0])
        vertical_chart.y.append(measured_resistances[1])
        avg_probe_R = sum(probe_resistances) / len(probe_resistances)
        temperature_chart.x.append(avg_probe_R)
        temperature_chart.raw_y.append(avg_probe_R)
        sheet_resistance_chart.raw_y.append(
            measured_resistances
            if len(measured_resistances) == 2
            else [measured_resistances[0], measured_resistances[1]]
        )
        sheet_resistance_chart.raw_x.append(avg_probe_R)


def R_probe_temp(resistance: float) -> float:
    """
    Converts probe resistance to temperature.

    Parameters:
        resistance (float): Probe resistance in Ohms.

    Returns:
        float: Estimated temperature in Kelvin.
    """
    return 5.2 * resistance + 0.2


def van_der_pauw_calculation(resistances: List[float]) -> float:
    """
    Calculates the sheet resistance using the Van der Pauw method.

    This method uses the measured horizontal and vertical resistances to solve for
    the sheet resistance R_s from the equation:
        exp(-π*R_h/R_s) + exp(-π*R_v/R_s) = 1

    Parameters:
        resistances (List[float]): List containing [R_h, R_v] (in Ohms).

    Returns:
        float: Calculated sheet resistance (Ohm/sq) or NaN if the calculation fails.
    """
    R_h, R_v = [abs(r) for r in resistances]
    R_s = sp.Symbol("R_s")  # Sheet resistance symbol
    equation = sp.Eq(sp.exp(-sp.pi * R_h / R_s) + sp.exp(-sp.pi * R_v / R_s) - 1, 0)
    numeric_eq = sp.lambdify(R_s, equation.lhs, modules="numpy")
    try:
        sheet_resistance = float(brentq(numeric_eq, 1e-20, 1e6))
    except ValueError:
        sheet_resistance = np.nan
    return sheet_resistance


def task_status_web() -> None:
    """This function shall be executed within a st container"""

    pass


def init_4w_vdp_NV_K2000() -> None:
    """
    Registers the four-wire Van der Pauw measurement task.

    This task is configured to use the Keithley 2000 for resistance measurements and
    a relay matrix for switching configurations.
    """
    new_task = Task(
        name="VDP K2000 NV34420 SM2401",
        description="Four-wire measurement using Keithley 2000 for temperature and NV34420 for voltage and SM2401 for current.",
        instrs_aliases=["model 2000", "relay matrix", "model 2401", "34420"],
        function=meas_4w_vdp,
        custom_web_status=task_status_web,
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(new_task)
