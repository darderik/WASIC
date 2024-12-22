from dash import html
from dash import dcc
from connections import Connections


def infoHeaderForInstruments(instrumentIndex: int):
    toReturn = []
    if len(Connections.Instruments) == 0:
        toReturn = "No Instruments Connected"
    else:
        toReturn = [
            html.Label(f"Instrument {instrumentIndex} Alias"),
            dcc.Input(id=f"instrument-{instrumentIndex}-alias", type="text", value=f"Instrument {instrumentIndex}"),
            html.Label(f"Instrument {instrumentIndex} Serial Port:"),
            f"The port for instrument {instrumentIndex}:{Connections.Instruments[instrumentIndex-1].port}",
        ]
    return toReturn


# Get generic info for all instruments
def infoHeaderForInstruments():
    toReturn = []
    if len(Connections.Instruments) == 0:
        toReturn = "No Instruments Connected"
    else:
        for instrument, idx in enumerate(Connections.Instruments):
            toReturn += [
                html.H3(f"Instrument {idx} Data"),
                html.Label(f"Instrument {idx} Serial Port:"),
                f"The port for instrument 1{instrument.port}"
            ]
    return toReturn
