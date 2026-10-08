from tasks import ChartData, ChartData_Config
from wasic_api import TaskSpec, TaskContext, ParameterSpec
import random
import logging
import math


def test_task_function(task_obj: TaskContext) -> None:
    """Generate four charts using only the injected run context; no hardware required."""
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
    scatter_max_x = task_obj.parameters["scatter_max_x"]
    scatter_max_y = task_obj.parameters["scatter_max_y"]
    sine_amplitude = task_obj.parameters["sine_amplitude"]
    histogram_mean = task_obj.parameters["histogram_mean"]
    histogram_std = task_obj.parameters["histogram_std"]

    
    # Add all charts to data
    data.extend([scatter_chart, line_chart, histogram_chart, formula_chart])
    
    # Initialize time counter for sine wave
    time_counter: float = 0.0
    
    ## -------------END INIT PHASE---------------- ##
    try:
        while not exit_flag.is_set():
            update_interval = task_obj.parameters["update_interval"]

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
            exit_flag.wait(update_interval)
    except Exception as e:
        logger.error(f"Error in test task: {e}")
    finally:
        exit_flag.set()


# Complete hardware-free addon example: no manager access or init function.
PLUGIN = TaskSpec(
    id="test_charts",
    name="Test Charts",
    description="Generate scatter, sine, histogram and formula charts without hardware.",
    run=test_task_function,
    parameters={
        "update_interval": ParameterSpec(float, 1.0, minimum=0.01),
        "scatter_max_x": ParameterSpec(float, 100.0, minimum=0),
        "scatter_max_y": ParameterSpec(float, 10000.0, minimum=0),
        "sine_amplitude": ParameterSpec(float, 50.0),
        "histogram_mean": ParameterSpec(float, 50.0),
        "histogram_std": ParameterSpec(float, 15.0, minimum=0),
        "merge_chart_files": ParameterSpec(bool, True),
    },
)
