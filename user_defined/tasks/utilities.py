from tasks import ChartData
from typing import List, Callable
from threading import Event, Thread
import time


def spawn_data_processor(
    data: List[ChartData], exit_flag: Event, task_processor: Callable
) -> Thread:
    for chart_data in data:
        if (
            chart_data.math_formula_y is not None
            or chart_data.math_formula_x is not None
        ):
            # Start the processor thread to handle data updates
            newThreadProcessor: Thread = Thread(
                target=task_processor, args=(data, exit_flag)
            )
            newThreadProcessor.start()  # Begin the background processing thread
            break  # Exit the loop after starting the thread
    return newThreadProcessor


def apply_formula(target: List[float], raw: List, formula) -> None:
    cur_index = len(target)
    if cur_index < len(raw):
        list_copy = raw.copy()[cur_index:]
        for value in list_copy:
            new_value: float = formula(value)
            target.append(new_value)


# The processor shall handle each chart data associated with the task
# If even a single chartdata has a math formula, the processor gets spawned
def generic_processor(data: List[ChartData], exit_flag: Event) -> None:
    """Process chart data by applying mathematical formulas."""
    last_iteration: bool = False
    while True:
        for chart_data in data:
            if chart_data.math_formula_y is not None:
                apply_formula(chart_data.y, chart_data.raw_y, chart_data.math_formula_y)
            if chart_data.math_formula_x is not None:
                apply_formula(chart_data.x, chart_data.raw_x, chart_data.math_formula_x)
        if last_iteration:
            break
        if exit_flag.is_set():
            last_iteration = True
        time.sleep(1)  # Sleep for 1 second
