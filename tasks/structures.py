from typing import List, Callable, Optional
from dataclasses import dataclass, field


@dataclass
class ChartData:
    """
    ChartData

    A class representing the data structure for creating and managing chart data.

    Attributes:
        name (str): The name of the chart. Defaults to "Custom Chart".
        math_formula_x (Optional[Callable]): A callable function to compute the x-axis values. Defaults to None.
        math_formula_y (Optional[Callable]): A callable function to compute the y-axis values. Defaults to None.
        raw_x (List[float]): The raw data points for the x-axis. Initialized as an empty list.
        raw_y (List[float]): The raw data points for the y-axis. Initialized as an empty list.
        x (List[float]): The processed or computed data points for the x-axis. Initialized as an empty list.
        y (List[float]): The processed or computed data points for the y-axis. Initialized as an empty list.
        x_label (str): The label for the x-axis. Defaults to "X-axis".
        y_label (str): The label for the y-axis. Defaults to "Y-axis".
        custom_name (str): A custom name for the chart. Defaults to an empty string. Used for saving the chart data.
    """

    name: str = "Custom Chart"
    info: str = ""
    math_formula_x: Optional[Callable] = None
    math_formula_y: Optional[Callable] = None
    raw_x: List = field(default_factory=list)
    raw_y: List = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    x_label: str = "X-axis"
    y_label: str = "Y-axis"
    custom_name: str = ""
    custom_type: str = ""
