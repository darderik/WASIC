from dash import html, dcc, register_page, callback, Output, Input, dash_table, Patch
import pandas as pd
import plotly.express as px
from plotly.graph_objs import Figure
import datetime
import random
from typing import List

# Register the page with Dash
register_page(__name__, name="Instr 2")

# Setup array for keeping track of radio button values
radio_values = [True, True]
text_box_buffer: List[str] = [""]

## Init existing scatter
chart_2_fig: Figure = px.scatter()


# Define layout extern
def layout(**kwargs):
    curLay = html.Div(
        children=[
            html.H1("Instrument 2 Page"),
            html.Br(),
            html.H2("Parameter 1 Config of Instrument 2"),  # Begin parameter 1 block
            html.Div(
                [
                    html.Span(
                        children=[
                            html.Label(
                                "Parameter 1: dropdown",
                                style={"display": "block", "fontWeight": "bold"},
                            ),
                            dcc.Dropdown(
                                id="parameter-1-instr-2-dropdown",
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
                                id="radio-items-instr-2",
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
            html.H2("Parameter 2 Config of Instrument 2"),  # Begin parameter 2 block
            html.Div(
                [
                    dcc.RadioItems(
                        id="radio-items2-instr-2",
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
                    html.H3("Parameter 1 and 2 Config of Instrument 2 current value"),
                    html.Div(id="Parameter_values-instr-2"),
                ]
            ),
            html.Br(),  # Add a line break
            # Callback update of graph 1
            html.H1(children="Chart 1 of Instrument 2", style={"textAlign": "center"}),
            dcc.Dropdown(
                ["First Plot", "Second Plot"],
                id="chart-1-instrument-2-dropdown",
                value="First Plot",
            ),
            dcc.Graph(id="graph-1-instrument-2"),
            html.Br(),
            # Live update of the graph 2
            html.Div(
                [
                    html.H1(
                        children="Chart 2 Live of instrument 2",
                        style={"textAlign": "center"},
                    ),
                    dcc.Graph(id="graph-2-instrument-2", figure=chart_2_fig),
                    dcc.Interval(
                        id="graph-2-instance-instrument-2-update",
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
                        id="live-buffer-box-instr-2",
                        style={
                            "border": "1px solid black",
                            "padding": "10px",
                            "height": "300px",
                            "overflowY": "scroll",
                            "backgroundColor": "#f4f4f4",
                        },
                    ),
                    dcc.Interval(
                        id="live-output-container-update-instr-2",
                        interval=1 * 3000,  # in milliseconds
                        n_intervals=0,
                    ),
                ],
                id="live-output-container",
            ),
            html.Br(),
            html.Div(
                children="Data Table of instrument 2", style={"textAlign": "left"}
            ),
            dash_table.DataTable(
                data=[
                    {"name": "example", "value": 123},
                    {"name": "example2", "value": 321},
                ],
                page_size=10,
            ),
            html.Div(id="config-instrument-2"),
        ]
    )
    return curLay


# Callback to update based on radio button selection
@callback(
    Output("Parameter_values-instr-2", "children"),
    Input("radio-items-instr-2", "value"),
    Input("radio-items2-instr-2", "value"),
)
def update_config(value1, value2):
    radio_values[0] = value1
    radio_values[1] = value2
    return f"CurValue: {radio_values[0], radio_values[1]}"


# Callback to update the graph based on the dropdown selection
@callback(
    Output("graph-1-instrument-2", "figure"),
    Input("chart-1-instrument-2-dropdown", "value"),
)
def update_graph1(value):
    if value == "First Plot":
        fig: Figure = px.scatter(x=[1, 2, 3], y=[1, 2, 3])
    else:
        fig: Figure = px.scatter(x=[3, 2, 1], y=[1, 2, 3])
    return fig


# Callback to live update graph-2-instrument-2
@callback(
    Output("graph-2-instrument-2", "figure"),
    Input("graph-2-instance-instrument-2-update", "n_intervals"),
)
def update_graph2(n_intervals):

    current_time = datetime.datetime.now()
    random_value = random.randrange(1, 30, 1)
    partialFig: Patch = Patch()
    partialFig["data"][0]["x"].append(current_time)
    partialFig["data"][0]["y"].append(random_value)
    return partialFig


@callback(
    Output("live-buffer-box-instr-2", "children"),
    Input("live-output-container-update-instr-2", "n_intervals"),
)
def update_live_output(n_intervals):
    cur_line: int = len(text_box_buffer)
    current_time: datetime = datetime.datetime.now()
    random_value: int = random.randrange(1, 30, 1)
    curString: str = f"CurLine: {cur_line}->{current_time} - {random_value}\n"
    text_box_buffer.append(curString)
    return "".join(text_box_buffer)
