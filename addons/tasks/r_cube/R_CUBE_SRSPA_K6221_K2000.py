from typing import Optional, cast
import time
import logging
from tasks import Task, Tasks, ChartData, ChartData_Config
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, K2000, K6221
from connections import Connections
from tasks.helper import str_to_bool

"""R Cube Measurement (K6221 current source + K2000 voltmeter)

Current sourced by Keithley 6221/6220 (K6221 class), voltage sensed by K2000.
Resistance R = V / I. Delta mode optionally reverses current polarity:
V_eff = (V+ - V-) / 2.
"""


def meas_r_cube_source_k6221_k2000(task_obj: Task) -> None:
    relay_mat_1: Optional[Instrument_Entry] = Connections().get_instrument("0035001F3133510137303835")
    relay_mat_2: Optional[Instrument_Entry] = Connections().get_instrument("0069004C3433511133393338")
    src_entry: Optional[Instrument_Entry] = Connections().get_instrument("Model 6221")  # alias as registered
    k2_entry: Optional[Instrument_Entry] = Connections().get_instrument("model 2000")

    if relay_mat_1 is None or relay_mat_2 is None or src_entry is None or k2_entry is None:
        logging.error("Instrument init failure (Relay matrices / K6221 / K2000).")
        return

    rm1: RelayMatrix = cast(RelayMatrix, relay_mat_1.scpi_instrument)
    rm2: RelayMatrix = cast(RelayMatrix, relay_mat_2.scpi_instrument)
    src: K6221 = cast(K6221, src_entry.scpi_instrument)
    dmm: K2000 = cast(K2000, k2_entry.scpi_instrument)

    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    chart = ChartData(
        name="R Cube (K6221+K2000) Resistance",
        config=ChartData_Config(
            pop_raw=False,
            include_raw_on_save=True,
            atomic_save=True,
            custom_type="scatter",
            refresh_all=False,
        ),
        math_formula_y=lambda v: float(v[2]),
    )
    chart.x_series.meta.unit = "Label"
    chart.x_series.meta.label = "Configuration"
    chart.y_series.meta.unit = "ohm"
    chart.y_series.meta.label = "Resistance"

    # Parameters
    current = float(task_obj.parameters.get("current", "1e-3"))
    compliance = float(task_obj.parameters.get("compliance", "0"))
    source_range = float(task_obj.parameters.get("source_range", "0"))
    delta_mode = str_to_bool(task_obj.parameters.get("delta_mode", "True"))
    settle_s = float(task_obj.parameters.get("settle_time_s", "0.5"))
    vertices = int(task_obj.parameters.get("vertices", "8"))
    nplc = float(task_obj.parameters.get("nplc", "1.0"))

    data.extend([chart])

    mapping = {"I+": "C", "I-": "D", "V+": "A", "V-": "B"}

    chart.x_series.raw = []
    chart.y_series.raw = []
    meas_idx = 0

    def route(tag: str, node: int) -> None:
        switch_commute_aggregator(rm1, rm2, mapping[tag], node)

    # Configure source
    try:
        src.source_autorange=True
        src.current = current
    except Exception as e:
        logger.warning(f"K6221 source config failed: {e}")

    # Configure meter
    try:
        dmm.configure_voltage_dc(range=-1)
        dmm.nplc = nplc
        dmm.autozero = True
    except Exception:
        pass

    def measure_voltage() -> float:
        try:
            vals = dmm.measure_voltage_dc()
            return float(vals[0]) if vals else float('nan')
        except Exception as e:
            logger.error(f"Voltage measurement failed: {e}")
            return float('nan')

    try:
        src.output_on()
        for i_pos in range(1, vertices + 1):
            for i_neg in range(i_pos, vertices + 1):
                for v_pos in range(1, vertices + 1):
                    for v_neg in range(v_pos, vertices + 1):
                        if len({i_pos, i_neg, v_pos, v_neg}) < 4:
                            continue
                        if exit_flag.is_set():
                            logger.info("Exit flag set; terminating K6221+K2000 task.")
                            return
                        rm1.switch_commute_reset_all(); rm2.switch_commute_reset_all()
                        rm1.opc(); rm2.opc()
                        route("I+", i_pos); route("I-", i_neg); route("V+", v_pos); route("V-", v_neg)
                        rm1.opc(); rm2.opc(); time.sleep(settle_s)
                        v_plus = measure_voltage()
                        if delta_mode:
                            try:
                                src.current = -current
                            except Exception:
                                logger.warning("K6221 current reversal failed; delta disabled for this point.")
                                v_minus = float('nan')
                                v_eff = v_plus
                            else:
                                time.sleep(settle_s)
                                v_minus = measure_voltage()
                                try:
                                    src.current = current
                                except Exception:
                                    pass
                                v_eff = (v_plus - v_minus) / 2.0
                        else:
                            v_minus = float('nan')
                            v_eff = v_plus
                        R = v_eff / (abs(current) if abs(current) > 0 else 1.0)
                        label = [
                            f"{meas_idx}",
                            f"I+:{i_pos} I-:{i_neg} V+:{v_pos} V-:{v_neg}",
                            f"rm:{mapping['I+']}{i_pos} {mapping['I-']}{i_neg} {mapping['V+']}{v_pos} {mapping['V-']}{v_neg}",
                        ]
                        chart.x_series.raw.append(label)
                        chart.y_series.raw.append([v_plus, v_minus, R, current, meas_idx])
                        meas_idx += 1
    except Exception as e:
        logger.error(f"Error in KS6221+K2000 R cube task: {e}")
    finally:
        try:
            src.current = 0.0
            src.output_off()
            rm1.switch_commute_reset_all(); rm2.switch_commute_reset_all()
        except Exception:
            pass
        exit_flag.set()


def init_meas_r_cube_source_k6221_k2000() -> None:
    """Register the K6221+K2000 R cube task."""
    t = Task(
        name="R Cube (K6221 source + K2000 volt)",
        description="Enumerate cube resistances using K6221 sourcing current and K2000 measuring voltage with optional delta mode.",
        instrs_aliases=["Model 6221", "model 2000", "relay matrix"],
        function=meas_r_cube_source_k6221_k2000,
        parameters={
            "current": "1e-3",
            "compliance": "15",
            "source_range": "0",
            "delta_mode": "True",
            "settle_time_s": "0.5",
            "vertices": "8",
            "nplc": "1.0",
            "merge_chart_files": "True",
        },
    )
    Tasks().add_task(t)


def switch_commute_aggregator(rm1: RelayMatrix, rm2: RelayMatrix, input_letter: str, output_vertex: int) -> None:
    if output_vertex <= 4:
        rm1.switch_commute_exclusive(f"{input_letter}{output_vertex}")
    else:
        rm2.switch_commute_exclusive(f"{input_letter}{output_vertex - 4}")
