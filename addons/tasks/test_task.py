from tasks import Task, Tasks, ChartData,ChartData_Config
from threading import Event
from typing import Optional, List
from threading import Thread
import random
import time
import logging
import math
from connections import Connections
from tasks import str_to_bool
# filepath: c:\Users\Dardo\OneDrive\Progetti\Python\WASIC\user_defined\tasks\test_task.py


def test_task_function(task_obj: Task) -> None:
    """A test task function that generates various types of charts for testing purposes."""
    # --------------INIT PHASE---------------- ##
    data = task_obj.data
    exit_flag = task_obj.exit_flag
    logger = logging.getLogger(__name__)

    # Create different test charts
    scatter_chart = ChartData(
        name="Scatter Test - Random Points",
        config=ChartData_Config(
            pop_raw=False,
            include_raw_on_save=True,
            atomic_save=True,
            sample_points_x=1000,
            sample_points_y=1000,
            custom_type="scatter",
        ),
    )
    scatter_chart.x_series.meta.unit = "s"
    scatter_chart.y_series.meta.unit = "V"
    scatter_chart.x_series.meta.label = "Time"
    scatter_chart.y_series.meta.label = "Voltage"
    
    line_chart = ChartData(
        name="Line Test - Sine Wave",
        config=ChartData_Config(
            pop_raw=True,
            include_raw_on_save=True,
            atomic_save=True,
            sample_points_x=1000,
            sample_points_y=1000,
            custom_type="line",
        ),
    )
    line_chart.x_series.meta.unit = "s"
    line_chart.y_series.meta.unit = "A"
    line_chart.x_series.meta.label = "Time"
    line_chart.y_series.meta.label = "Current"
    
    histogram_chart = ChartData(
        name="Histogram Test - Normal Distribution",
        config=ChartData_Config(
            pop_raw=True,
            include_raw_on_save=True,
            atomic_save=True,
            sample_points_x=1000,
            sample_points_y=1000,
            custom_type="histogram",
        ),
    )
    histogram_chart.y_series.meta.unit = "counts"
    histogram_chart.x_series.meta.label = "Value"
    histogram_chart.x_series.meta.unit = "Random points"
    histogram_chart.y_series.meta.label = "Frequency"
    
    formula_chart = ChartData(
        name="Formula Test - Custom Function",
        config=ChartData_Config(
            pop_raw=True,
            include_raw_on_save=True,
            atomic_save=True,
            sample_points_x=1000,
            sample_points_y=1000,
            custom_type="formula",
        ),
        math_formula_x=lambda t: t,
        math_formula_y=lambda t: 10 * math.exp(-0.1 * t) * math.sin(t),
    )
    formula_chart.x_series.meta.unit = "s"
    formula_chart.y_series.meta.unit = "mV"
    formula_chart.x_series.meta.label = "Time"
    formula_chart.y_series.meta.label = "Signal"
    
    # Parse and deserialize parameters
    scatter_max_x = float(task_obj.parameters.get("scatter_max_x", "100"))
    scatter_max_y = float(task_obj.parameters.get("scatter_max_y", "10000"))
    sine_amplitude = float(task_obj.parameters.get("sine_amplitude", "50"))
    histogram_mean = float(task_obj.parameters.get("histogram_mean", "50"))
    histogram_std = float(task_obj.parameters.get("histogram_std", "15"))
    merge_chart_files = str_to_bool(task_obj.parameters.get("merge_chart_files", "True"))


    # Add all charts to data
    data.extend([scatter_chart, line_chart, histogram_chart, formula_chart])
    
    # Initialize time counter for sine wave
    time_counter: float = 0.0
    
    ## -------------END INIT PHASE---------------- ##
    try:
        while not exit_flag.is_set():
            update_interval = float(task_obj.parameters.get("update_interval", "0.1"))

            # Generate scatter plot data - random points
            scatter_x = random.uniform(0, scatter_max_x)
            scatter_y = random.uniform(0, scatter_max_y)
            scatter_chart.x_series.processed.append(scatter_x)
            scatter_chart.y_series.processed.append(scatter_y)
            
            # Generate line plot data - sine wave
            line_x = time_counter
            line_y = sine_amplitude * (1 + math.sin(time_counter / 5))  # Sine wave with period 10π
            line_chart.x_series.processed.append(line_x)
            line_chart.y_series.processed.append(line_y)
            
            # Generate histogram data - normal distribution
            hist_value = random.gauss(histogram_mean, histogram_std)  # Mean and std dev from parameters
            histogram_chart.x_series.processed.append(hist_value)
            
            # Generate formula chart data - custom function
            formula_x = time_counter
            formula_y = 10 * math.exp(-0.1 * time_counter) * math.sin(time_counter)
            formula_chart.x_series.raw.append(formula_x)
            formula_chart.y_series.raw.append(formula_y)
            
            time_counter += update_interval
            time.sleep(update_interval)  # Update interval from parameters
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
            "update_interval": "1",
            "scatter_max_x": "100",
            "scatter_max_y": "10000",
            "sine_amplitude": "50",
            "histogram_mean": "50",
            "histogram_std": "15",
            "merge_chart_files": "True",
        },
    )
    tasks_obj = Tasks()
    tasks_obj.add_task(test_task)


# Add the following line to an init file to register the test task:
# Tasks.tasks_init_list.append(init_test_task)
