from typing import Optional, List, cast
from threading import Thread, Event
import time

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, NV34420
from connections import Connections
from dataclasses import dataclass


@dataclass
class relay_conf:
    grey: str
    black: str


@dataclass
class anisotropy_data_pack:
    first_chart: ChartData
    second_chart: ChartData
    # sheet_resistance_chart: ChartData


class vdp_data_pack:
    horizontal_res: ChartData
    vertical_res: ChartData
    # sheet_resistance_chart: ChartData


def meas_4w_vdp(task_obj: Task) -> None:
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
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    # Initialize ChartData objects
    horizontal_chart_1 = ChartData(
        name="Horizontal Resistance",
        y_label="R_H_1 (Ohm)",
    )
    vertical_chart_1 = ChartData(
        name="Vertical Resistance",
        y_label="R_V_1 (Ohm)",
    )

    #    sheet_resistance_chart_1 = ChartData(
    #        name="Van der Pauw Sheet Resistance",
    #        info="Sheet resistance calculated using the Van der Pauw method. Each raw_y element contains [R_h, R_v].",
    #        math_formula_y=lambda res_pair: van_der_pauw_calculation(res_pair),
    #        x_label="Samples",
    #        y_label="Sheet Resistance (Ohm/sq)",
    #    )

    # Initialize ChartData objects
    horizontal_chart_2 = ChartData(
        name="Horizontal Resistance",
        y_label="R_H_2 (Ohm)",
    )
    vertical_chart_2 = ChartData(
        name="Vertical Resistance",
        y_label="R_V_2 (Ohm)",
    )

    #    sheet_resistance_chart_2 = ChartData(
    #        name="Van der Pauw Sheet Resistance",
    #        info="Sheet resistance calculated using the Van der Pauw method. Each raw_y element contains [R_h, R_v].",
    #        math_formula_y=lambda res_pair: van_der_pauw_calculation(res_pair),
    #        x_label="Samples",
    #        y_label="Sheet Resistance (Ohm/sq)",
    #    )
    data.extend(
        [
            horizontal_chart_1,
            vertical_chart_1,
            # sheet_resistance_chart_1,
            horizontal_chart_2,
            vertical_chart_2,
            # sheet_resistance_chart_2,
        ]
    )

    # Connections singleton
    connection_obj: Connections = Connections()

    # Retrieve instruments
    relay_entry_grey: Optional[Instrument_Entry] = connection_obj.get_instrument(
        "0069004C3433511133393338"
    )
    relay_entry_black: Optional[Instrument_Entry] = connection_obj.get_instrument(
        "0035001F3133510137303835"
    )
    nv34420_entry: Optional[Instrument_Entry] = connection_obj.get_instrument("34420A")

    # Start data processing in a background thread
    # data_thread: Thread = spawn_data_processor(data, exit_flag, generic_processor)
    if relay_entry_black is None or relay_entry_grey is None or nv34420_entry is None:
        return
    # Get SCPI instrument objects
    relay_matrix_black: RelayMatrix = cast(RelayMatrix, relay_entry_black.scpi_instrument)
    relay_matrix_grey: RelayMatrix = cast(RelayMatrix, relay_entry_grey.scpi_instrument)
    nv34420: NV34420 = cast(NV34420, nv34420_entry.scpi_instrument)

    # Configure instruments
    nv34420.configure_resistance(nplc=10)
    relay_matrix_black.switch_commute_reset_all()
    relay_matrix_grey.switch_commute_reset_all()

    # Relay configurations: even of each config are R_horizontals, odd are R_vertical
    relay_config_1: List[relay_conf] = [
        relay_conf(grey="a1 b2 c3 d4", black=""),
        relay_conf(grey="a3 b4 c1 d2", black=""),
        relay_conf(grey="a2 b4 c1 d3", black=""),
        relay_conf(grey="a1 b3 c2 d4", black=""),
    ]
    relay_config_2: List[relay_conf] = [
        relay_conf(grey="a1 b2", black="c1 d2"),
        relay_conf(grey="c1 d2", black="a1 b2"),  # swap 1-2?
        relay_conf(grey="a1 c2", black="b1 d2"),
        relay_conf(grey="b1 d2", black="a1 c2"),
    ]

    relay_config_aggregate = [relay_config_1, relay_config_2]
    # Data pack aggregates
    vdp_data: List[anisotropy_data_pack] = [
        anisotropy_data_pack(
            first_chart=horizontal_chart_1, second_chart=horizontal_chart_2
        ),
        anisotropy_data_pack(
            first_chart=vertical_chart_1,
            second_chart=vertical_chart_2,
        ),
    ]

    # Main measurement loop
    while not exit_flag.is_set():
        for i, config_seq in enumerate(relay_config_aggregate):
            cur_data_pack = vdp_data[i]
            R_even_list = []
            R_odd_list = []
            for j, cur_relay_config in enumerate(config_seq):
                relay_matrix_grey.switch_commute_reset_all()
                relay_matrix_black.switch_commute_reset_all()
                if cur_relay_config.black != "":
                    relay_matrix_black.switch_commute_exclusive(cur_relay_config.black)
                if cur_relay_config.grey != "":
                    relay_matrix_grey.switch_commute_exclusive(cur_relay_config.grey)
                time.sleep(1)
                resistance = abs(nv34420.read_meas())
                time.sleep(1)
                # If index even then R_horizontals
                if j % 2 == 0:
                    R_even_list.append(resistance)
                else:
                    R_odd_list.append(resistance)
            # Avg of meas, reciprocity assumed
            R_even = sum(R_even_list) / len(R_even_list)
            R_odd = sum(R_odd_list) / len(R_odd_list)

            # Populate charts
            cur_data_pack.first_chart.y.append(R_even)
            cur_data_pack.second_chart.y.append(R_odd)

    # Clean up: join the data processing thread before exiting
    # data_thread.join()


def task_status_web() -> None:
    """This function shall be executed within a st container"""

    pass


def init_4w_vdp_34420A() -> None:
    """
    Registers the four-wire Van der Pauw measurement task.

    This task is configured to use the Agilent 34420A in 4W and two relay matrix
    """
    new_task = Task(
        name="VDP NV34420A",
        description="Four-wire measurement using NV34420A.",
        instrs_aliases=["34420A", "Relay Matrix"],
        function=meas_4w_vdp,
        custom_web_status=task_status_web,
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(new_task)
