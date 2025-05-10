from connections import Connections
from user_defined.instruments import TDS2012, RelayMatrix

import numpy as np
import plotly.graph_objects as go
from typing import List
from tasks import Tasks
import time


def test_function():
    # Connections().fetch_all_instruments()
    Tasks().run_task("Test Task")


def plot_waveform(time: List[float], voltage: List[float], channel: int = 1):
    """
    Plots waveform data using Plotly.

    Args:
        time: List of time values in seconds.
        voltage: List of voltage values in volts.
        channel: Oscilloscope channel number (for labeling).
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time, y=voltage, mode="lines", name=f"CH{channel}"))

    fig.update_layout(
        title=f"Waveform - Channel {channel}",
        xaxis_title="Time (s)",
        yaxis_title="Voltage (V)",
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        height=500,
        width=800,
    )

    fig.show()
