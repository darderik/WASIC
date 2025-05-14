from tasks import Task, Tasks, ChartData
from threading import Event
from typing import Optional, List
from threading import Thread
import random
import time
import logging
from .utilities import spawn_data_processor, generic_processor

# filepath: c:\Users\Dardo\OneDrive\Progetti\Python\WASIC\user_defined\tasks\test_task.py


def test_task_function(data: List[ChartData], exit_flag: Event) -> None:
    """A simple test task function for software testing purposes."""
    logger = logging.getLogger(__name__)
    test_chart = ChartData(
        name="Test Chart",
        math_formula_y=lambda x: x**2,
        custom_type="histogram",
        pop_raw=True,
    )
    data.append(test_chart)
    newThreadProcessor: Optional[Thread] = spawn_data_processor(
        data, exit_flag, generic_processor
    )
    try:
        while not exit_flag.is_set():
            random_value = random.gauss(0, 10)
            test_chart.raw_y.append(random_value)
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error in test task: {e}")
    finally:
        exit_flag.set()


def init_test_task() -> None:
    """Initialize the test task and add it to the tasks list."""
    test_task = Task(
        name="Test Task",
        description="A task created for testing purposes.",
        instrs_aliases=[],
        function=test_task_function,
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(test_task)


# Add the following line to an init file to register the test task:
# Tasks.tasks_init_list.append(init_test_task)
