from tasks import ChartData
from streamlit.delta_generator import DeltaGenerator
from pandas import DataFrame
from copy import deepcopy
import pandas as pd
import plotly.express as px


def make_plotly_figure(chart_data: ChartData):
    if chart_data.custom_type in ("", "scatter"):
        df = pd.DataFrame(
            {
                "x": chart_data.x or list(range(len(chart_data.y))),
                "y": chart_data.y,
            }
        )
        return px.scatter(
            df,
            x="x",
            y="y",
            title=chart_data.name,
            labels={"x": chart_data.x_label, "y": chart_data.y_label},
        )
    elif chart_data.custom_type == "histogram":
        # y values on x for aesthetic reasons
        return px.histogram(
            pd.DataFrame({"x": chart_data.y}),
            y="x",
            title=chart_data.name,
            labels={"x": chart_data.y_label},
        )
    else:  # interpolated
        return px.line(
            pd.DataFrame({"x": chart_data.x, "y": chart_data.y}),
            x="x",
            y="y",
            title=chart_data.name,
            labels={"x": chart_data.x_label, "y": chart_data.y_label},
        )
