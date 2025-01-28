from tasks import ChartData
from streamlit.delta_generator import DeltaGenerator
from pandas import DataFrame
import pandas as pd


def plot_chart(chart_data: ChartData, scatter: DeltaGenerator) -> None:
    """
    Plot the chart data.
    """
    if not chart_data.x:
        newpdDataFrame: DataFrame = pd.DataFrame(
            data={"y": chart_data.y},
        )
        # Plot only y-axis data as scatter chart
        scatter.scatter_chart(newpdDataFrame, y="y", y_label=chart_data.y_label)
    else:
        # Create DataFrame for x and y data
        minLen: int = min(len(chart_data.x), len(chart_data.y))
        newDataFrame: DataFrame = pd.DataFrame(
            data={
                "x": chart_data.x[:minLen],
                "y": chart_data.y[:minLen],
            }  # Avoid uneven x-y values
        )
        # Plot scatter chart with x and y axes
        scatter.scatter_chart(
            newDataFrame,
            x="x",
            y="y",
            x_label=chart_data.x_label,
            y_label=chart_data.y_label,
        )
