from tasks import ChartData, Tasks, Task, ChartData_Config
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
    - For histograms: Use only y_series.processed, ignore x_series.
    - For other plots: If y_series.processed is None or empty, return empty figure.
      If y_series.processed exists, check for x_series.processed.
      If x_series.processed exists, slice both to the same length.
      If not, use an index for x.
    """
    chart_data_config: ChartData_Config = chart_data.config
    custom_type = chart_data_config.custom_type
    title = chart_data.name
    x_label = chart_data.x_series.meta.label if chart_data.x_series else ""
    y_label = chart_data.y_series.meta.label if chart_data.y_series else ""

    # Get processed data
    y_processed = chart_data.y_series.processed if chart_data.y_series else None
    x_processed = chart_data.x_series.processed if chart_data.x_series else None

    # Convert to lists
    y_list = _to_list(y_processed)
    x_list = _to_list(x_processed)

    if custom_type in ("histogram", "hist"):
        # Histogram: prioritize y, then x if y is empty
        if y_list:
            # Use y if available (whether x is present or not)
            data_list = y_list
            data_label = y_label
        elif x_list:
            # Use x if y is empty but x is available
            data_list = x_list
            data_label = x_label
        else:
            # Both empty, empty histogram
            data_list = []
            data_label = y_label  # or x_label, doesn't matter
        
        fig = px.histogram(pd.DataFrame({"data": data_list}), x="data", title=title, labels={"data": data_label})
    else:
        # Other plots: scatter, line, etc.
        if not y_list:
            # No y data, return empty
            fig = px.scatter(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title, labels={"x": x_label, "y": y_label})
        else:
            if x_list:
                # Both x and y, slice to min length
                min_len = min(len(x_list), len(y_list))
                x_trim = x_list[:min_len]
                y_trim = y_list[:min_len]
            else:
                # No x, use index
                x_trim = list(range(len(y_list)))
                y_trim = y_list

            df = pd.DataFrame({"x": x_trim, "y": y_trim})

            if custom_type in ("", "scatter"):
                fig = px.scatter(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})
            else:
                # Default to line
                fig = px.line(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})

    return fig