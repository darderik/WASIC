from dash import html, dcc, register_page, callback, Output, Input, dash_table, Patch
import plotly.express as px
from plotly.graph_objs import Figure
import datetime
import random
from typing import List
from connections import Connections
from webApp.helperFuncs import instrumentsHelper

# Register the page with Dash
register_page(__name__, name="Instr 1")

# Setup array for keeping track of radio button values
radio_values = [True, True]
text_box_buffer: List[str] = [""]

# Instrument index EDIT HERE IF COPY/PASTE
instrumentIndex = 1

## Init existing scatter
global chart_2_instr_1_fig
chart_2_instr_1_fig: Figure = Figure()

# Define layout extern
def layout(**kwargs):
    curLay = html.Div(
        children=[
            html.H1(f"Instrument {instrumentIndex} Page"),
            html.Br(),
            # Dropdown for instruments config that has multiple values(e.g. integration time, etc)
            # Radio elements mainly for booleans
            html.H2(
                f"Parameters config of instrument {instrumentIndex}"
            ),  # Begin parameter 1 block
            html.Div(
                [
                    html.Span(
                        children=[
                            html.Label(
                                "Parameter 1: dropdown",
                                style={"display": "block", "fontWeight": "bold"},
                            ),
                            dcc.Dropdown(
                                id=f"parameter-1-instr-{instrumentIndex}-dropdown",
                                options=[
                                    {"label": "True", "value": True},
                                    {"label": "False", "value": False},
                                    {"label": "Option 3", "value": 3},
                                ],
                                style={"width": "100px"},
                            ),
                        ],
                        style={
                            "display": "inline-block",
                            "margin-right": "50px",
                            "vertical-align": "top",
                        },
                    ),
                    html.Span(
                        children=[
                            html.Label(
                                "Parameter 1: radio",
                                style={"display": "block", "fontWeight": "bold"},
                            ),
                            dcc.RadioItems(
                                id=f"radio-items-instr-{instrumentIndex}",
                                options=[
                                    {"label": "True", "value": True},
                                    {"label": "False", "value": False},
                                ],
                                value=True,
                            ),
                        ],
                        style={"display": "inline-block", "vertical-align": "top"},
                    ),
                ]
            ),  # End parameter 1 block
            html.Br(),  # Add a line break
            html.H2(
                f"Parameter 2 Config of Instrument {instrumentIndex}"
            ),  # Begin parameter 2 block
            html.Div(
                [
                    dcc.RadioItems(
                        id=f"radio-items2-instr-{instrumentIndex}",
                        options=[
                            {"label": "True", "value": True},
                            {"label": "False", "value": False},
                        ],
                        value=True,
                    ),
                ]
            ),  # End parameter 2 block
            html.Div(
                [  # Begin parameter 1 and 2 show
                    html.H3(
                        f"Parameter 1 and 2 Config of Instrument {instrumentIndex} current value"
                    ),
                    html.Div(id=f"Parameter_values-instr-{instrumentIndex}"),
                ]
            ),
            html.Br(),  # Add a line break
            # Callback update of graph 1
            html.H1(
                children=f"Chart 1 of Instrument {instrumentIndex}",
                style={"textAlign": "center"},
            ),
            dcc.Dropdown(
                ["First Plot", "Second Plot"],
                id=f"chart-1-instrument-{instrumentIndex}-dropdown",
                value="First Plot",
            ),
            dcc.Graph(id=f"graph-1-instrument-{instrumentIndex}"),
            html.Br(),
            # Live update of the graph 2
            html.Div(
                [
                    html.H1(
                        children=f"Chart 2 Live of Instrument {instrumentIndex}",
                        style={"textAlign": "center"},
                    ),
                    dcc.Graph(
                        id=f"graph-2-instrument-{instrumentIndex}", figure=chart_2_instr_1_fig
                    ),
                    dcc.Interval(
                        id=f"graph-2-instance-instrument-{instrumentIndex}-update",
                        interval=1 * 3000,  # in milliseconds
                        n_intervals=0,
                    ),
                ]
            ),
            # Live update of output terminal or relevant data, textbox
            html.Div(
                [
                    html.H1("Buffer di Testo Live"),
                    html.Pre(
                        id=f"live-buffer-box-instr-{instrumentIndex}",
                        style={
                            "border": "1px solid black",
                            "padding": "10px",
                            "height": "300px",
                            "overflowY": "scroll",
                            "backgroundColor": "#f4f4f4",
                        },
                    ),
                    dcc.Interval(
                        id=f"live-output-container-update-instr-{instrumentIndex}",
                        interval=1 * 3000,  # in milliseconds
                        n_intervals=0,
                    ),
                ],
                id=f"live-output-container-instr-{instrumentIndex}",
            ),
            html.Br(),
            html.Div(
                children=f"Data Table of Instrument {instrumentIndex}",
                style={"textAlign": "left"},
            ),
            dash_table.DataTable(
                data=[
                    {"name": "example", "value": 123},
                    {"name": "example2", "value": 321},
                ],
                page_size=10,
            ),
            html.Div(id=f"config-instrument-{instrumentIndex}"),
        ]
    )
    return curLay


# Callback to update based on radio button selection
@callback(
    Output(f"Parameter_values-instr-{instrumentIndex}", "children"),
    Input(f"radio-items-instr-{instrumentIndex}", "value"),
    Input(f"radio-items2-instr-{instrumentIndex}", "value"),
)
def update_config(value1, value2):
    radio_values[0] = value1
    radio_values[1] = value2
    return f"CurValue: {radio_values[0], radio_values[1]}"


# Callback to update the graph based on the dropdown selection
@callback(
    Output(f"graph-1-instrument-{instrumentIndex}", "figure"),
    Input(f"chart-1-instrument-{instrumentIndex}-dropdown", "value"),
)
def update_graph1(value):
    if value == "First Plot":
        fig: Figure = px.scatter(x=[1, 2, 3], y=[1, 2, 3])
    else:
        fig: Figure = px.scatter(x=[3, 2, 1], y=[1, 2, 3])
    return fig


# Callback to live update graph-2-instrument-1
@callback(
    Output(f"graph-2-instrument-{instrumentIndex}", "figure"),
    Input(f"graph-2-instance-instrument-{instrumentIndex}-update", "n_intervals"),
    prevent_initial_call=True
)
def update_graph2(n_intervals):
    current_time = datetime.datetime.now()
    random_value = random.randrange(1, 30, 1)
    patched_fig: Patch = Patch()
    patched_fig["data"][0]["x"].append(current_time)
    patched_fig["data"][0]["y"].append(random_value)
    return patched_fig


# Text box
@callback(
    Output(f"live-buffer-box-instr-{instrumentIndex}", "children"),
    Input(f"live-output-container-update-instr-{instrumentIndex}", "n_intervals"),
)
def update_live_output(n_intervals):
    cur_line: int = len(text_box_buffer)
    current_time: datetime = datetime.datetime.now()
    random_value: int = random.randrange(1, 30, 1)
    curString: str = f"CurLine: {cur_line}->{current_time} - {random_value}\n"
    text_box_buffer.append(curString)
    return "".join(text_box_buffer)
