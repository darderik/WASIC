from dash import html, register_page, callback, Output, Input
from webApp.helperFuncs.instrumentsHelper import infoHeaderForInstruments
from connections import Connections
from config import Config

register_page(__name__, path="/", name="Home")


def layout(**kwargs):
    divArr = [
        html.H1("Benvenuto nella Home Page"),
        html.P("Seleziona una delle pagine dal menu in alto."),
        html.H2("Instruments generic info"),
        html.Div(id="list-instruments-home", children=[infoHeaderForInstruments()]),
    ]
    if Config.autoUpdate:
        divArr.append(html.Button("Refresh", id="refresh-button"))
    else:
        divArr.append(html.Button("Refresh", id="refresh-button", hidden=True))
    return html.Div(divArr)


if Config.autoUpdate:

    @callback(
        Output("list-instruments-home", "children"),
        Input("refresh-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def refresh_button(n_clicks: int):
        Connections.fetchInstruments()
        return infoHeaderForInstruments()
