from tasks import ChartData
from typing import List, Callable
from threading import Event, Thread
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def spawn_data_processor(
    data: List[ChartData], exit_flag: Event, task_processor: Callable
) -> Optional[Thread]:
    newThreadProcessor: Optional[Thread] = None
    for chart_data in data:
        if (
            chart_data.math_formula_y is not None
            or chart_data.math_formula_x is not None
        ):
            # Start the processor thread to handle data updates
            newThreadProcessor = Thread(target=task_processor, args=(data, exit_flag))
            newThreadProcessor.start()  # Begin the background processing thread
            break  # Exit the loop after starting the thread
    return newThreadProcessor


def apply_formula(target: List[float], raw: List, formula: Callable, pop: bool) -> None:
    cur_index = len(target)
    raw_len = len(raw)
    if cur_index < len(raw) and not pop:
        for i in range(cur_index, raw_len):
            value = raw[i]
            new_value: float = formula(value)
            target.append(new_value)
    elif pop:
        for i in range(raw_len):
            value = raw[i]
            new_value = formula(value)
            target.append(new_value)
        for _ in range(raw_len):
            raw.pop(0)


# The processor shall handle each chart data associated with the task
# If even a single chartdata has a math formula, the processor gets spawned
def generic_processor(data: List[ChartData], exit_flag: Event) -> None:
    """Process chart data by applying mathematical formulas."""
    last_iteration: bool = False
    while True:
        if exit_flag.is_set():
            last_iteration = True
        try:
            for chart_data in data:
                if (
                    len(chart_data.x) > chart_data.sample_points_x
                    and chart_data.sample_points_x != 0
                    or len(chart_data.y) > chart_data.sample_points_y
                    and chart_data.sample_points_y != 0
                ):
                    exit_flag.set()
                if chart_data.math_formula_y is not None:
                    apply_formula(
                        chart_data.y,
                        chart_data.raw_y,
                        chart_data.math_formula_y,
                        chart_data.pop_raw,
                    )
                if chart_data.math_formula_x is not None:
                    apply_formula(
                        chart_data.x,
                        chart_data.raw_x,
                        chart_data.math_formula_x,
                        chart_data.pop_raw,
                    )
        except Exception as e:
            logger.error(f"Error in data processing: {e}")
            continue
        if last_iteration:
            break
        time.sleep(1)  # Sleep for 1 second
