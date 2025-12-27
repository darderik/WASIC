from typing import Optional, cast
import time
import logging
from tasks import Task, Tasks, ChartData, ChartData_Config
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, SM2401, K2000
from connections import Connections
from tasks.helper import str_to_bool

"""R Cube Measurement (SM2401 source + K2000 volt meter)

Current sourced by SM2401, voltage sensed by K2000, resistance R = V/I.
Delta mode: measure V+ with +I, then V- with -I, V_eff = (V+ - V-)/2 to cancel offsets.
"""

def meas_r_cube_source_k2000(task_obj: Task) -> None:
    # -------------- INIT PHASE ---------------- ##
    relay_mat_1: Optional[Instrument_Entry] = Connections().get_instrument("0035001F3133510137303835")
    relay_mat_2: Optional[Instrument_Entry] = Connections().get_instrument("0069004C3433511133393338")
    sm_entry: Optional[Instrument_Entry] = Connections().get_instrument("2401")
    k2_entry: Optional[Instrument_Entry] = Connections().get_instrument("model 2000")

    if relay_mat_1 is None or relay_mat_2 is None or sm_entry is None or k2_entry is None:
        logging.error("Instrument init failure (Relay matrices / SM2401 / K2000).")
        return

    rm1: RelayMatrix = cast(RelayMatrix, relay_mat_1.scpi_instrument)
    rm2: RelayMatrix = cast(RelayMatrix, relay_mat_2.scpi_instrument)
    smu: SM2401 = cast(SM2401, sm_entry.scpi_instrument)
    dmm: K2000 = cast(K2000, k2_entry.scpi_instrument)

    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    resistance_chart = ChartData(
        name="R Cube (SM2401+K2000) Resistance",
        config=ChartData_Config(
            pop_raw=False,
            include_raw_on_save=True,
            atomic_save=True,
            custom_type="scatter",
            refresh_all=False,
        ),
        math_formula_y=lambda v: float(v[2]),  # resistance stored at index 2
    )
    resistance_chart.x_series.meta.unit = "Label"
    resistance_chart.x_series.meta.label = "Configuration"
    resistance_chart.y_series.meta.unit = "ohm"
    resistance_chart.y_series.meta.label = "Resistance"

    # Parameters
    current = float(task_obj.parameters.get("current", "1e-3"))
    compliance = float(task_obj.parameters.get("compliance", "0"))
    delta_mode = str_to_bool(task_obj.parameters.get("delta_mode", "True"))
    settle_s = float(task_obj.parameters.get("settle_time_s", "0.5"))
    vertices = int(task_obj.parameters.get("vertices", "8"))
    nplc = float(task_obj.parameters.get("nplc", "1.0"))
    overall_iterations = int(task_obj.parameters.get("overall_iterations", "1"))
    # Unused placeholder retained for compatibility
    merge_chart_files = str_to_bool(task_obj.parameters.get("merge_chart_files", "True"))
    
    # Mapping parameters (split for Streamlit compatibility)
    mapping_iplus = task_obj.parameters.get("mapping_I+", "C")
    mapping_iminus = task_obj.parameters.get("mapping_I-", "D")
    mapping_vplus = task_obj.parameters.get("mapping_V+", "A")
    mapping_vminus = task_obj.parameters.get("mapping_V-", "B")

    data.extend([resistance_chart])

    mapping = {"I+": mapping_iplus, "I-": mapping_iminus, "V+": mapping_vplus, "V-": mapping_vminus}

    resistance_chart.x_series.raw = []
    resistance_chart.y_series.raw = []
    meas_idx = 0

    def route(path_label: str, node: int) -> None:
        switch_commute_aggregator(rm1, rm2, mapping[path_label], node)

    # Configure source & meter
    try:
        smu.configure_current_source(current=current, compliance=compliance)
    except Exception as e:
        logger.warning(f"SM2401 current source config failed: {e}")
    try:
        dmm.configure_voltage_dc()
        dmm.nplc = nplc  # Set integration time for DC voltage
    except Exception:
        pass

    def measure_voltage() -> float:
        try:
            vals = dmm.measure_voltage_dc()  # returns list
            return float(vals[0]) if vals else float('nan')
        except Exception as e:
            logger.error(f"Voltage measurement failed: {e}")
            return float('nan')

    try:
        smu.output_on()
        for iteration in range(overall_iterations):
            for i_pos in range(1, vertices + 1):
                for i_neg in range(i_pos, vertices + 1):
                    for v_pos in range(1, vertices + 1):
                        for v_neg in range(v_pos, vertices + 1):
                            if len({i_pos, i_neg, v_pos, v_neg}) < 4:
                                continue
                            if exit_flag.is_set():
                                logger.info("Exit flag set; terminating task.")
                                return
                            rm1.switch_commute_reset_all(); rm2.switch_commute_reset_all()
                            rm1.opc(); rm2.opc()
                            route("I+", i_pos); route("I-", i_neg); route("V+", v_pos); route("V-", v_neg)
                            rm1.opc(); rm2.opc(); time.sleep(settle_s)
                            v_plus = measure_voltage()
                            if delta_mode:
                                # Reverse current polarity
                                try:
                                    smu.current = -current
                                except Exception:
                                    logger.warning("SM2401 current reversal failed; delta disabled for this point.")
                                    v_minus = float('nan')
                                    v_eff = v_plus
                                else:
                                    time.sleep(settle_s)
                                    v_minus = measure_voltage()
                                    # Restore current
                                    try:
                                        smu.current = current
                                    except Exception:
                                        pass
                                    v_eff = (v_plus - v_minus) / 2.0
                            else:
                                v_minus = float('nan')
                                v_eff = v_plus
                            R = v_eff / (abs(current) if abs(current) > 0 else 1.0)
                            label = [f"{meas_idx}", f"I+:{i_pos} I-:{i_neg} V+:{v_pos} V-:{v_neg}", f"rm:{mapping['I+']}{i_pos} {mapping['I-']}{i_neg} {mapping['V+']}{v_pos} {mapping['V-']}{v_neg}"]
                            resistance_chart.x_series.raw.append(label)
                            resistance_chart.y_series.raw.append([v_plus, v_minus,R,current, meas_idx])
                            meas_idx += 1
    except Exception as e:
        logger.error(f"Error in SM2401+K2000 R cube task: {e}")
    finally:
        try:
            smu.current = 0.0
            smu.output_off()
            rm1.switch_commute_reset_all(); rm2.switch_commute_reset_all()
        except Exception:
            pass
        exit_flag.set()


def init_meas_r_cube_source_k2000_sm2401() -> None:
    """Register the SM2401+K2000 R cube task."""
    t = Task(
        name="R Cube (SM2401 source + K2000 volt)",
        description="Enumerate cube resistances using SM2401 sourcing current and K2000 measuring voltage with optional delta mode.",
        instrs_aliases=["2401", "model 2000", "relay matrix"],
        function=meas_r_cube_source_k2000,
        parameters={
            "current": "10e-3",
            "compliance": "20",
            "delta_mode": "True",
            "settle_time_s": "0.3",
            "vertices": "8",
            "nplc": "1.0",
            "overall_iterations": "1",
            "merge_chart_files": "True",
            "mapping_I+": "C",
            "mapping_I-": "D",
            "mapping_V+": "A",
            "mapping_V-": "B",
        },
    )
    Tasks().add_task(t)


def switch_commute_aggregator(rm1: RelayMatrix, rm2: RelayMatrix, input_letter: str, output_vertex: int) -> None:
    if output_vertex <= 4:
        rm1.switch_commute_exclusive(f"{input_letter}{output_vertex}")
    else:
        rm2.switch_commute_exclusive(f"{input_letter}{output_vertex - 4}")
