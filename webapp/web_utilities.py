from tasks import ChartData, Tasks, Task
import pandas as pd
import plotly.express as px


def _to_list(value):
    """Convert many possible container/array-like inputs to a plain Python list.
    Safe for None, scalars, pandas Series, numpy arrays, lists, etc.
    """
    if value is None:
        return []
    try:
        # pandas handles many types (numpy arrays, Series, lists, scalars)
        return pd.Series(value).tolist()
    except Exception:
        try:
            return list(value)
        except Exception:
            return [value]


def make_plotly_figure(chart_data: ChartData):
    """Create a Plotly figure from a ChartData object.

    Rules:
    - If x is empty and y is present, x becomes an index range(len(y)).
    - If lengths differ, arrays are truncated to the smaller length.
    - Supported chart types: scatter (default), histogram, line (fallback).
    """
    custom_type = (getattr(chart_data, "custom_type", "") or "").lower()
    title = getattr(chart_data, "name", "")
    x_label = getattr(chart_data, "x_label", "x")
    y_label = getattr(chart_data, "y_label", "y")

    x_list = _to_list(getattr(chart_data, "x", []))
    y_list = _to_list(getattr(chart_data, "y", []))

    # If x is empty but y has values, use an index for x
    if not x_list and y_list:
        x_list = list(range(len(y_list)))

    # If y is empty but x has values, fill y with None to keep lengths consistent
    if not y_list and x_list:
        y_list = [None] * len(x_list)

    # Truncate to the minimum length to ensure x and y align
    min_len = min(len(x_list), len(y_list))
    if min_len == 0:
        # Return an empty scatter figure to avoid Plotly errors
        return px.scatter(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title, labels={"x": x_label, "y": y_label})

    x_trim = x_list[:min_len]
    y_trim = y_list[:min_len]

    df = pd.DataFrame({"x": x_trim, "y": y_trim})

    try:
        if custom_type in ("", "scatter"):
            fig = px.scatter(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})

        elif custom_type in ("histogram", "hist"):
            # Histogram of the y-values
            fig = px.histogram(df, x="y", title=title, labels={"y": y_label})
        else:
            # Default to a line plot for interpolated/continuous data
            fig = px.line(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})
    except Exception:
        # Fallback to an empty figure if plot creation fails
        fig = px.scatter(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title, labels={"x": x_label, "y": y_label})

    return fig