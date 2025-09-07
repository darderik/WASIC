from calendar import c
import re
from typing import Optional, List, cast
from threading import Event
import time
import math
import numpy as np

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, NV34420, SM2401
from connections import Connections


def meas_anisotropy(task_obj: Task) -> None:
    # Get instruments from connections
    conn = Connections()

    # Find serial numbers for required instruments
    relay_grey_entry: Optional[Instrument_Entry] = conn.get_instrument("0069004C3433511133393338")
    relay_black_entry: Optional[Instrument_Entry] = conn.get_instrument("0035001F3133510137303835")
    nv_entry: Optional[Instrument_Entry] = conn.get_instrument("34420A")
    sm_entry: Optional[Instrument_Entry] = conn.get_instrument("4055551")
    # ChartData objects to store measured values
    # Current I
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    i_chart: ChartData = ChartData(name="Current", y_label="A")
    vc32_chart: ChartData = ChartData(name="Vc32", y_label="V", custom_type="histogram")
    vc37_chart_18: ChartData = ChartData(name="Vc37_I18", y_label="V", custom_type="histogram")
    vc26_chart: ChartData = ChartData(name="Vc26", y_label="V", custom_type="histogram")
    vc37_chart: ChartData = ChartData(name="Vc37", y_label="V", custom_type="histogram")
    vc48_chart: ChartData = ChartData(name="Vc48", y_label="V", custom_type="histogram")
    v_top_chart: ChartData = ChartData(name="Vtop", y_label="V", custom_type="histogram")
    v_bottom_chart: ChartData = ChartData(name="Vbottom", y_label="V", custom_type="histogram")

    data.extend(
        [i_chart, vc26_chart, vc37_chart, vc48_chart, v_top_chart, v_bottom_chart, vc32_chart, vc37_chart_18]
    )

    if relay_grey_entry is None or relay_black_entry is None or nv_entry is None or sm_entry is None:
        exit_flag.set()
        return

    relay_grey: RelayMatrix = cast(RelayMatrix, relay_grey_entry.scpi_instrument)
    relay_black: RelayMatrix = cast(RelayMatrix, relay_black_entry.scpi_instrument)
    nv: NV34420 = cast(NV34420, nv_entry.scpi_instrument)
    sm: SM2401 = cast(SM2401, sm_entry.scpi_instrument)

    # Basic instrument configuration
    sm.disable_beep()
    nv.disable_beep()
    # configure SM as current source and NV for voltage measurement
    current: float = task_obj.parameters.get("current", 10e-3)  # Default to 10mA if not specified
    compliance: float = task_obj.parameters.get("compliance", 100e-3)  # Default to 100mV if not specified
    sm.configure_current_source(current=current, compliance=compliance)
    sm.output_off()
    sm.configure_current_measure(nplc=5)
    nv.configure_voltage(nplc=10)
    relay_grey.switch_commute_reset_all()
    relay_black.switch_commute_reset_all()

    # Main measurement loop (barebone)
    # Placeholder relay configurations for two orthogonal directions
    # [GREY],[BLACK]
    # #  I A1 C4
    vtop_config = [[],["a1","b2","c4","d3"]]
    vbot_config = [["b2","d3"], ["a1","c4"]]

    # # I 15
    vc26_config = [["b1","d2"],["a1","c2"]]
    vc37_config = [["b1","d3"], ["a1","c3"]]
    vc48_config = [["b1","d4"], ["a1","c4"]]

    # # I 18
    vc32_config = [ ["c4"], ["a1","b3","d2"]]
    vc37_I18_config = [["a1","b3"],["c4","d3"]]

    # Add more configurations as needed

    while True:
        current = task_obj.parameters.get("current", 10e-3)  # Default to 10mA if not specified
        compliance = task_obj.parameters.get("compliance", 100e-3)  #
        
        # Top/bottom voltage
        # Inject current using sm2401
        i_chart.y.append(current)
        # # I A1 C4
        # # # Setup relay VTOP
        switch_relay_couple(relay_grey, relay_black, vtop_config)
        v_top = delta_meas(nv, sm,current_abs=current,compliance=compliance)

        # # # Setup relay VBOT
        switch_relay_couple(relay_grey, relay_black, vbot_config)
        v_bot = delta_meas(nv, sm,current_abs=current,compliance=compliance)

        # Append vtop and vbot readings
        v_top_chart.y.append(v_top)
        v_bottom_chart.y.append(v_bot)

        # # # I 15
        # # # setup relay VC26
        switch_relay_couple(relay_grey, relay_black, vc26_config)
        vc26 = delta_meas(nv, sm,current_abs=current,compliance=compliance)
        vc26_chart.y.append(vc26)
        # # #setup relay VC37
        switch_relay_couple(relay_grey, relay_black, vc37_config)
        vc37 = delta_meas(nv, sm,current_abs=current,compliance=compliance)
        vc37_chart.y.append(vc37)
        # # #setup relay VC48
        switch_relay_couple(relay_grey, relay_black, vc48_config)
        vc48 = delta_meas(nv, sm,current_abs=current,compliance=compliance)
        vc48_chart.y.append(vc48)

        # # # I 18
        switch_relay_couple(relay_grey, relay_black, vc32_config)
        vc32 = delta_meas(nv, sm,current_abs=current,compliance=compliance)
        vc32_chart.y.append(vc32)
        # Vc37
        switch_relay_couple(relay_grey, relay_black, vc37_I18_config)
        vc37_18 = delta_meas(nv, sm,current_abs=current,compliance=compliance)
        vc37_chart_18.y.append(vc37_18)

        if exit_flag.is_set():
            break


def init_anisotropy_sm_nv_2rm() -> None:
    """Register the barebone anisotropy task."""
    newTask: Task = Task(
        name="Anisotropy Meas SM2401+34420+2RM",
        description="Barebone anisotropy measurement using two relay matrices and SM2401+34420",
        instrs_aliases=["2401","34420","relay matrix"],
        function=meas_anisotropy,
        parameters={"current": 10e-3, "compliance": 100e-3}
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(newTask)


# Optionally, tasks initialization list append could be added when wiring into app


def delta_meas(nv: NV34420, sm: SM2401,current_abs:float = 100e-6,compliance:float =10e-3) -> float:
    # Positive current direction
    sm.output_off()
    sm.configure_current_source(current=current_abs, compliance=compliance)
    sm.output_on()
    time.sleep(0.2)  # wait for settling
    v_plus = nv.measure_voltage()
    # Negative current direction
    sm.configure_current_source(current=-1*current_abs, compliance=compliance)
    time.sleep(0.2)  # wait for settling
    v_minus = nv.measure_voltage()
    sm.output_off()
    return (v_plus - v_minus) / 2


def switch_relay_couple(
    relay1: RelayMatrix, relay2: RelayMatrix, config: List[List[str]]
) -> None:
    # Setup config for relay 1
    relay1.switch_commute_reset_all()
    if config[0] != []:
        relay1.switch_commute_exclusive(*config[0])

    relay2.switch_commute_reset_all()
    if config[1] != []:
        relay2.switch_commute_exclusive(*config[1])
    return
