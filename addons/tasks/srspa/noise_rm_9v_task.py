from typing import Optional, cast, List
import time
import logging

from tasks import Task, Tasks, ChartData
from instruments import Instrument_Entry
from addons.instruments import NV34420, RelayMatrix
from connections import Connections


def noise_rm_9v_task(task_obj: Task) -> None:
    """Measure voltage from NV34420 while using a RelayMatrix for commutation.

    This task creates a ChartData (time in seconds on X) and appends measurements.
    Relay commutation is left as a skeleton for the user to fill in.
    """
    logger = logging.getLogger(__name__)
    data = task_obj.data
    exit_flag = task_obj.exit_flag

    # Chart for voltage vs time
    voltage_chart = ChartData(
        name="9V Noise with Relay (V vs s)",
        x_label="Time (s)",
        y_label="Voltage (V)",
        custom_type="histogram",
        pop_raw=True,
        sample_points_y=500,
    )
    data.append(voltage_chart)

    # Get connections and instruments
    conn = Connections()
    nv_entry: Optional[Instrument_Entry] = conn.get_instrument("34420A")
    # Use one of the relay serials used elsewhere in the project
    relay_entry: Optional[Instrument_Entry] = conn.get_instrument(
        "0069004C3433511133393338"
    )

    if nv_entry is None:
        logger.error("NV34420 instrument (alias '34420A') not found. Aborting task.")
        exit_flag.set()
        return

    if relay_entry is None:
        logger.error("Relay Matrix instrument (serial '0035001F3133510137303835') not found. Aborting task.")
        exit_flag.set()
        return

    nv34420: NV34420 = cast(NV34420, nv_entry.scpi_instrument)
    relay_matrix: RelayMatrix = cast(RelayMatrix, relay_entry.scpi_instrument)

    # Parameters
    nplc: float = float(task_obj.parameters.get("nplc", "10")) if task_obj.parameters else 10.0
    sample_count: int = int(task_obj.parameters.get("sample_count", "50000")) if task_obj.parameters else 50000
    time_limit = float(task_obj.parameters.get("time_limit", "1e24")) if task_obj.parameters else 1e24

    # Try to configure instruments (non-fatal warnings on failure)
    try:
        nv34420.configure_voltage(range=-1, nplc=nplc)
        # Match noise_9v behavior: immediate trigger and large sample buffer
        nv34420.trigger_configure(source="IMM", delay=0.0, count=1)
        nv34420.set_sample_count(count=sample_count)
    except Exception:
        logger.warning("Failed to configure NV34420 for voltage; continuing with defaults.")

    try:
        relay_matrix.switch_commute_reset_all()
    except Exception:
        logger.warning("Failed to reset relay matrix; ensure connection is valid.")

    start_time = time.time()
    relay_matrix.switch_commute_exclusive("a1","b2")
    try:
        while not exit_flag.is_set():
            # Stop if time limit exceeded
            if (time.time() - start_time) >= time_limit:
                break

            # Placeholder for relay commutation sequence
            # Example (commented):
            # relay_matrix.switch_commute_exclusive("a1")
            # time.sleep(0.05)  # settle
            # relay_matrix.switch_commute_exclusive("b2")

            try:
                # Align with noise_9v: read a chunk and timestamp using NPLC
                chunk_start = time.time()
                vals: List[float] = cast(List[float],nv34420.read_meas().tolist())
                idx: int = 0
                for val in vals:
                    voltage_chart.x.append(chunk_start + (idx + 0.5) * nplc / 50)
                    voltage_chart.y.append(float(val))
                    idx += 1
            except Exception as e:
                logger.error(f"Error reading NV34420: {e}")

            # Optional pacing if needed

    except Exception as e:
        logger.exception(f"Unhandled exception in noise_rm_9v_task: {e}")
    finally:
        exit_flag.set()


def init_noise_rm_9v_task() -> None:
    """Register the noise measurement task that uses a relay matrix."""
    new_task = Task(
        name="Noise 9V RM - NV34420",
        description="Measure battery noise with NV34420 using a Relay Matrix for commutation; commutation skeleton provided.",
        instrs_aliases=["34420A", "Relay Matrix"],
        function=noise_rm_9v_task,
        parameters={
            "nplc": "5",
            "time_limit": "1e9",
            "sample_count": "50000",
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(new_task)
