# --- Imports and dependencies ---
from typing import Optional, List, cast
import time
import logging
from threading import Event

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import NV34420
from connections import Connections


# --- Main Task Function ---
def noise_9v_task(task_obj: Task) -> None:
    """Measure voltage from NV34420 and push values to a ChartData against time (seconds).

    The task will create a single ChartData object and append time (s) to raw_x and
    measured voltage to raw_y. It will also append the same values to x/y so the
    web UI can display processed data immediately.
    """
    logger = logging.getLogger(__name__)
    data = task_obj.data
    exit_flag = task_obj.exit_flag

    # --- Chart Setup ---
    # Create chart for voltage vs time
    voltage_chart = ChartData(
        name="9V Noise (V vs s)",
        y_label="Voltage (V)",
        custom_type="histogram",
        pop_raw=True,
        sample_points_y=500,
    )

    data.append(voltage_chart)

    # --- Instrument Connection ---
    # Get connections and instrument entry
    conn = Connections()
    nv_entry: Optional[Instrument_Entry] = conn.get_instrument("34420A")
    if nv_entry is None:
        logger.error("NV34420 instrument (alias '34420A') not found. Aborting noise_9v_task.")
        exit_flag.set()
        return

    nv34420: NV34420 = cast(NV34420, nv_entry.scpi_instrument)

    # --- Instrument Configuration ---
    # Configure the instrument for voltage measurement (use a slow NPLC for lower noise if needed)
    nplc: float = float(task_obj.parameters.get("nplc", "1")) if task_obj.parameters else 0.1
    # New: sample_count parameter
    sample_count: int = int(task_obj.parameters.get("sample_count", "50000")) if task_obj.parameters else 50000
    try:
        nv34420.configure_voltage(range=-1, nplc=nplc)
        nv34420.trigger_configure(source="IMM", delay=0.0, count=1)
        nv34420.set_sample_count(count=sample_count)
    except Exception:
        # Non-fatal: continue but measurements may be less optimal
        logger.warning("Failed to configure NV34420 for voltage. Continuing with defaults.")

    # --- Timing Setup ---

    try:
        while not exit_flag.is_set():
            # --- Parameters fetching ---
            time_limit = float(task_obj.parameters.get("time_limit", "1e24") if task_obj.parameters else "1e24")
            
            # --- Measurement ---
            start_time = time.time()
            vals = cast(List[float],nv34420.read_meas().tolist())
            idx: int = 0
            for val in vals:
                voltage_chart.x.append(start_time+(idx+0.5)*nplc/50)
                voltage_chart.y.append(val)
                idx += 1
            t = time.time() - start_time
            if (t>=time_limit):
                break
    except Exception as e:
        logger.exception(f"Unhandled exception in noise_9v_task: {e}")
    finally:
        exit_flag.set()


# --- Task Registration ---
def init_noise_9v_task() -> None:
    """Register the NV34420 9V noise measurement task."""
    new_task = Task(
        name="Noise 9V - NV34420",
        description="Measure battery noise with NV34420 and stream voltage vs time.",
        instrs_aliases=["34420A"],
        function=noise_9v_task,
        parameters={
            "nplc": "5",
            "time_limit": "1e9",
            "sample_count": "50000",
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(new_task)