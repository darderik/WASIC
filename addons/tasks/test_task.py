from tasks import Task, Tasks, ChartData
from threading import Event
from typing import Optional, List
from threading import Thread
import random
import time
import logging
import math
from .utilities import spawn_data_processor, generic_processor
from connections import Connections

# filepath: c:\Users\Dardo\OneDrive\Progetti\Python\WASIC\user_defined\tasks\test_task.py


def test_task_function(task_obj: Task) -> None:
    """A test task function that generates various types of charts for testing purposes."""
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    # Create different test charts
    scatter_chart = ChartData(
        name="Scatter Test - Random Points",
        math_formula_y=lambda x: x**2,
        custom_type="scatter",
        pop_raw=True,
    )
    
    line_chart = ChartData(
        name="Line Test - Sine Wave",
        math_formula_y=lambda x: x,
        custom_type="line",
        pop_raw=True,
    )
    
    histogram_chart = ChartData(
        name="Histogram Test - Normal Distribution",
        math_formula_y=lambda x: x,
        custom_type="histogram",
        pop_raw=True,
    )

    # Add all charts to data
    data.extend([scatter_chart, line_chart, histogram_chart])
    
    # Initialize time counter for sine wave
    time_counter = 0
    
    try:
        while not exit_flag.is_set():
            # Generate scatter plot data - random points
            scatter_x = random.uniform(0, 100)
            scatter_y = random.uniform(0, 10000)
            scatter_chart.raw_x.append(scatter_x)
            scatter_chart.raw_y.append(scatter_y)
            
            # Generate line plot data - sine wave
            line_x = time_counter
            line_y = 50 * (1 + math.sin(time_counter / 5))  # Sine wave with period 10π
            line_chart.raw_x.append(line_x)
            line_chart.raw_y.append(line_y)
            
            # Generate histogram data - normal distribution
            hist_value = random.gauss(50, 15)  # Mean of 50, std dev of 15
            histogram_chart.y.append(hist_value)
            
            time_counter += 0.1
            time.sleep(0.1)  # Faster updates for more dynamic visualization
            
    except Exception as e:
        logger.error(f"Error in test task: {e}")
    finally:
        exit_flag.set()


def init_test_task() -> None:
    """Initialize the test task and add it to the tasks list."""
    test_task = Task(
        name="Test Charts",
        description="A task that generates three different types of charts: scatter plot with random points, line plot with sine wave, and histogram with normal distribution.",
        instrs_aliases=[],
        function=test_task_function,
        parameters={
            "update_interval": 0.1,
            "scatter_max_x": 100,
            "scatter_max_y": 10000,
            "sine_amplitude": 50,
            "histogram_mean": 50,
            "histogram_std": 15
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(test_task)


# Add the following line to an init file to register the test task:
# Tasks.tasks_init_list.append(init_test_task)
