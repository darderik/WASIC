from tasks import ChartData
from streamlit.delta_generator import DeltaGenerator
from pandas import DataFrame
import pandas as pd
import plotly.express as px


def plot_chart_native(chart_data: ChartData, pholder: DeltaGenerator) -> None:
    """
    Plot the chart data.
    """
    if not chart_data.x:
        newpdDataFrame: DataFrame = pd.DataFrame(
            data={"y": chart_data.y},
        )
        # Plot only y-axis data as scatter chart
        pholder.scatter_chart(newpdDataFrame, y="y", y_label=chart_data.y_label)
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
        pholder.scatter_chart(
            newDataFrame,
            x="x",
            y="y",
            x_label=chart_data.x_label,
            y_label=chart_data.y_label,
        )


def plot_chart_plotly(chart_data: ChartData, pholder: DeltaGenerator):
    """
    Plot the chart data using Plotly and Streamlit.
    """
    if not chart_data.x:
        # Generate an index for x if missing
        newDataFrame = pd.DataFrame(
            {
                "x": list(range(len(chart_data.y))),
                "y": chart_data.y,
            }
        )
        fig = px.scatter(
            newDataFrame,
            x="x",
            y="y",
            title=chart_data.name,
            labels={"y": chart_data.y_label, "x": chart_data.x_label},
        )
    else:
        # Create DataFrame for x and y data, ensuring equal length
        minLen = min(len(chart_data.x), len(chart_data.y))
        newDataFrame = pd.DataFrame(
            {
                "x": chart_data.x[:minLen],
                "y": chart_data.y[:minLen],
            }
        )
        fig = px.scatter(
            newDataFrame,
            x="x",
            y="y",
            title=chart_data.name,
            labels={"x": chart_data.x_label, "y": chart_data.y_label},
        )

    # Use provided placeholder or streamlit's default
    pholder.plotly_chart(fig)
