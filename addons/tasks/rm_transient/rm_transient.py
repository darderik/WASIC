import logging
import time
from typing import Optional, List, cast

from tasks import Task, Tasks, ChartData, ChartData_Config
from connections import Connections
from instruments import Instrument_Entry
from addons.instruments import TBS1052C, RelayMatrix
from .rm_transient_uts import calculate_rise_time, calculate_fall_time

logger = logging.getLogger(__name__)

def rm_transient(task_obj: Task) -> None:
    
    # Init section -----
    conn_object = Connections()
    scope_entry: Optional[Instrument_Entry] = conn_object.get_instrument("TBS1052C")
    rm_entry: Optional[Instrument_Entry] = conn_object.get_instrument("Relay Matrix")

    if scope_entry is None or rm_entry is None:
        logger.error("One or more instruments could not be initialized.")
        return
    scope: TBS1052C = cast(TBS1052C, scope_entry.scpi_instrument)
    relay_matrix: RelayMatrix = cast(RelayMatrix, rm_entry.scpi_instrument)
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    
    # # Get parameters 
    waveform_count: int = int(task_obj.parameters.get("waveform_count", 1000))
    data_points: int = int(task_obj.parameters.get("data_points", 2000))
    five_v_combination: str = task_obj.parameters.get("5V Combination", "a1")
    gnd_combination: str = task_obj.parameters.get("GND Combination", "a2")

    
    # # Setup Data
    transient_rise_chart: ChartData = ChartData(
        name="Transienti in salita",
        config=ChartData_Config(
            pop_raw=False,
            custom_type="histogram",
            sample_points_y=waveform_count,
        ),
        math_formula_y=calculate_rise_time,
    )
    transient_fall_chart: ChartData = ChartData(
        name="Transienti in discesa",
        config=ChartData_Config(
            pop_raw=False,
            custom_type="histogram",
            sample_points_y=waveform_count,
        ),
        math_formula_y=calculate_fall_time,
    )
    data.append(transient_rise_chart)
    data.append(transient_fall_chart)

    # Add Labels
    transient_rise_chart.y_series.meta.description = "Raw values are 2D arrays which represent the waveform data. The rise time (processed) is calculated from these waveforms."
    transient_fall_chart.y_series.meta.description = "Raw values are 2D arrays which represent the waveform data. The fall time (processed) is calculated from these waveforms."
    transient_rise_chart.y_series.meta.label = "Voltage Rise Time (s)"
    transient_fall_chart.y_series.meta.label = "Voltage Fall Time (s)"
    transient_fall_chart.y_series.meta.unit = "s"
    transient_rise_chart.y_series.meta.unit = "s"
    transient_fall_chart.y_series.meta.scale = "linear"
    transient_rise_chart.y_series.meta.scale = "linear"

    # End of Init section -----

    # Scope setup
    time.sleep(1)
    # Set attenuation CH1
    ch1_attenuation: float = float(task_obj.parameters.get("CH1 Attenuation", 1))
    scope.set_probe_attenuation(1, ch1_attenuation)
    # Setup trigger with rise detection on CH2
    scope.trig_edge(source="CH2", slope="RISE")
    scope.trig_level(1.0, ch=2)
    # Hard coded positioning
    scope.set_channel_position(1, -3)
    scope.set_channel_position(2, 1)
    scope.set_channel_scale(1, 1)
    scope.set_channel_scale(2, 1)
    # Data setup
    scope.stop()
    scope.opc_wait()
    relay_matrix.switch_commute_reset_all()
    relay_matrix.switch_commute_exclusive(five_v_combination)

    # --- Horizontal setup ---
    scope.set_horizontal_delay(0)
    scope.set_trigger_position_divs(0)
    scope.set_horizontal_position(0)
    scope.enable_horizontal_delay(True)
    scope.set_record_length(data_points)

    try:
        while not exit_flag.is_set():
            # Set up for fall transient measurement (5V to GND combination)
            scope.set_time_scale(100e-6)  # Set time scale for fall transient
            scope.set_horizontal_delay(2e-3)
            scope.set_channel_position(1,-2) # Adjust channel position (vertically)
            scope.single()  # Arm the scope for single acquisition
            relay_matrix.switch_commute_exclusive(gnd_combination)  # Switch relay to GND combination
            relay_matrix.opc()  # Wait for relay scope.set_channel_position(1,-2)matrix operation to complete
            scope.opc()
            t_fall, V_fall, _ = scope.get_waveform(center_wavfrm=True, stop=data_points)  # Acquire fall waveform
            scope.stop()  # Stop the scope

            # Set up for rise transient measurement (GND combination to 5V)
            scope.set_time_scale(100e-6)  # Set time scale for rise transient
            scope.set_horizontal_delay(2e-3)  # Adjust trigger position
            scope.set_channel_position(1,-2) # Adjust channel position
            scope.single()  # Arm the scope for single acquisition
            relay_matrix.switch_commute_exclusive(five_v_combination)  # Switch relay to 5V combination
            relay_matrix.opc()  # Wait for relay matrix operation to complete
            #scope.wait_acquire_complete()
            scope.opc()
            t_rise, V_rise, _ = scope.get_waveform(center_wavfrm=True, stop = data_points)  # Acquire rise waveform

            # Save waveform data
            fall_data_wavfrm = [t_fall, V_fall]  # Save fall waveform data
            rise_data_wavfrm = [t_rise, V_rise]  # Save rise waveform data
            # Add to raw, data processor will parse
            transient_fall_chart.y_series.raw.append(fall_data_wavfrm)
            transient_rise_chart.y_series.raw.append(rise_data_wavfrm)

            # Stop the scope after processing
            scope.stop()
            #scope.wait_acquire_complete()
            scope.opc()

    except ValueError as e:
        logger.error(f"Error in task: {e}")
    finally:
        relay_matrix.switch_commute_reset_all()
        exit_flag.set()


def init_rm_transient() -> None:
    """Initialize the Relay Matrix Transient task and add it to the tasks list."""
    rm_transient_task = Task(
        name="Relay Matrix Transient",
        description="Relay Matrix Transient task.",
        instrs_aliases=["TBS1052C", "Relay Matrix"],
        function=rm_transient,
        parameters={
            "waveform_count": "1000",
            "data_points": "2000",
            "5V Combination": "a1",
            "GND Combination": "a2",
            "merge_chart_files": "True",
            "CH1 Attenuation": "1",
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(rm_transient_task)