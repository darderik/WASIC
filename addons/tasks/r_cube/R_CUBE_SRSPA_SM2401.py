from typing import Any, Optional, List, cast
import time
import logging
from tasks import Task, Tasks, ChartData, ChartData_Config
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, SM2401
from connections import Connections
from tasks.helper import str_to_bool

def meas_r_cube(task_obj: Task) -> None:
    # --------------INIT PHASE---------------- ##
    # Instruments setup
    RelayMat1: Optional[Instrument_Entry] = Connections().get_instrument("0035001F3133510137303835")
    RelayMat2: Optional[Instrument_Entry] = Connections().get_instrument("0069004C3433511133393338")
    SM1: Optional[Instrument_Entry] = Connections().get_instrument("2401")

    if RelayMat1 is None or RelayMat2 is None or SM1 is None:
        logging.error("One or more instruments could not be initialized.")
        return
    relay_matrix_1: RelayMatrix = cast(RelayMatrix, RelayMat1.scpi_instrument)
    relay_matrix_2: RelayMatrix = cast(RelayMatrix, RelayMat2.scpi_instrument)
    sm: SM2401 = cast(SM2401, SM1.scpi_instrument)
    sm.configure_fres_measure(range=0, nplc=1.0, offset_comp=True)
    sm.compliance=1e-3
    # End instrument setup

    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    # Create scatter for all 4W resistance measurements
    scatter_chart = ChartData(
        name="Unordered 4W Resistance Measurements",
        config=ChartData_Config(
            pop_raw=False,
            include_raw_on_save=True,
            atomic_save=True,
            custom_type="scatter",
            refresh_all=False,  # incremental updates only
        ),
        math_formula_y=lambda v: float(v[2]),  # identity conversion for resistance values
    )
    scatter_chart.x_series.meta.unit = "Sample label"
    scatter_chart.y_series.meta.unit = "ohm"
    scatter_chart.x_series.meta.label = "Label"
    scatter_chart.y_series.meta.label = "Resistance"

    # Parse and deserialize parameters
    current = float(task_obj.parameters.get("current", "1e-3"))
    merge_chart_files = str_to_bool(task_obj.parameters.get("merge_chart_files", "True"))


    # Add all charts to data
    data.extend([scatter_chart])
    
    ## -------------END INIT PHASE---------------- ##
    input_dictionary = {
        "I+": "C",
        "I-": "D",
        "V+": "A",
        "V-": "B",
    }
    vertices: int = 8
    # Initialize raw buffers: labels in x, numeric resistance values in y
    scatter_chart.x_series.raw = []
    scatter_chart.y_series.raw = []
    meas_idx = 0
    try:
        sm.output_on()
        for Ip_vertex in range(1, vertices + 1):
            for In_vertex in range(Ip_vertex, vertices + 1):
                for Vp_vertex in range(1, vertices + 1):
                    for Vm_vertex in range(Vp_vertex, vertices + 1):
                        # Ensure distinct vertices
                        if len({Ip_vertex, In_vertex, Vp_vertex, Vm_vertex}) < 4:
                            continue
                        if exit_flag.is_set():
                            logger.info("Exit flag set, terminating R cube measurement task.")
                            break
                        relay_matrix_1.switch_commute_reset_all()
                        relay_matrix_2.switch_commute_reset_all()
                        relay_matrix_1.opc()
                        relay_matrix_2.opc()
                        time.sleep(1)
                        switch_commute_aggregator(relay_matrix_1, relay_matrix_2, input_dictionary["I+"], Ip_vertex)
                        switch_commute_aggregator(relay_matrix_1, relay_matrix_2, input_dictionary["I-"], In_vertex)
                        switch_commute_aggregator(relay_matrix_1, relay_matrix_2, input_dictionary["V+"], Vp_vertex)
                        switch_commute_aggregator(relay_matrix_1, relay_matrix_2, input_dictionary["V-"], Vm_vertex)
                        relay_matrix_1.opc()   
                        relay_matrix_2.opc()
                        time.sleep(1) 
                        voltage,current,resistance = sm.read_fres()
                        labelling_str = [f"{meas_idx}",f"I+: {Ip_vertex} I-: {In_vertex} V+: {Vp_vertex} V-: {Vm_vertex}",f"rm_status: {input_dictionary['I+']}{Ip_vertex} {input_dictionary['I-']}{In_vertex} {input_dictionary['V+']}{Vp_vertex} {input_dictionary['V-']}{Vm_vertex}"]
                        scatter_chart.x_series.raw.append(labelling_str)
                        scatter_chart.y_series.raw.append([voltage, current, resistance,meas_idx])
                        meas_idx += 1
    except Exception as e:
        logger.error(f"Error in R cube measurement task: {e}")
    finally:
        try:
            sm.output_off()
            relay_matrix_1.switch_commute_reset_all()
            relay_matrix_2.switch_commute_reset_all()
        except Exception:
            pass
        exit_flag.set()


def init_meas_r_cube() -> None:
    """Initialize the test task and add it to the tasks list."""
    test_task = Task(
        name="R Cube Measurement",
        description="A task that measures the resistance of a cube using a 4-wire measurement technique.",
        instrs_aliases=["relay matrix","2401"],
        function=meas_r_cube,
        parameters={
            "current": "1e-3",
            "merge_chart_files": "True",
        },
    )
    Tasks().add_task(test_task)


def switch_commute_aggregator(rm1: RelayMatrix, rm2: RelayMatrix, input: str, output: int):
    if output <= 4:
        # Open input of other board
        rm1.switch_commute_exclusive(f"{input}{output}")
    else:
        rm2.switch_commute_exclusive(f"{input}{output - 4}")
