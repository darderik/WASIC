from threading import local
from tasks import ChartData
from streamlit.delta_generator import DeltaGenerator
from pandas import DataFrame
from copy import deepcopy
import pandas as pd
import plotly.express as px


def make_plotly_figure(chart_data: ChartData):
    if chart_data.custom_type in ("", "scatter"):
        local_y = deepcopy(chart_data.y)
        local_x = deepcopy(chart_data.x)
        if (len(local_x)==0):# X axis is just an index
            local_x = list(range(len(local_y)))
            df = pd.DataFrame(
                {
                    "x": local_x,
                    "y": local_y,
                }
            )
        else:
            min_len = min(len(local_x), len(local_y))
            df = pd.DataFrame(
                {
                    "x": local_x[:min_len],
                    "y": local_y[:min_len],
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
