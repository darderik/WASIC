import streamlit as st
from connections import Connections
import pandas as pd
from config import Config
from easy_scpi import Instrument
from typing import List
from instruments import Instrument_Entry, RaspberrySIM
from serial import Serial
import time


def verify_instruments(mode: int = 0):
    """Verify or fetch all instruments based on the mode."""
    if mode == 0:
        Connections.verify_instruments()
    else:
        Connections.fetch_all_instruments(Config.instrAliasesList)

    # Update session state with the instruments data
    st.session_state["instr_table"] = pd.DataFrame(
        {
            "Instrument Name": [
                instr.data.alias for instr in Connections.InstrumentsList
            ],
            "COM PORT": [
                instr.scpi_instrument.port for instr in Connections.InstrumentsList
            ],
            "BAUD RATE": [
                instr.scpi_instrument.resource_params["baud_rate"]
                for instr in Connections.InstrumentsList
            ],
            "IDN": [instr.scpi_instrument.id for instr in Connections.InstrumentsList],
        }
    )


def send_command(instr_selected: Instrument_Entry, command: str) -> None:
    try:
        instr_selected.write_wrapper(command)
        if "?" in command:  # This is a query, expect a response
            st.session_state[
                f"{curInstrSelected}_buffer_output"
            ] += f"{instr_selected.data.alias}: {command} -> {instr_selected.read_wrapper()}\n"
    except RuntimeError as exception:
        st.error(f"An error occurred: {exception}")


def save_config():
    Connections.save_config()


st.title("WASIC - Web Application for SCPI Instrument Control")

# Initialize the instruments table in session state if not already present
if "instr_table" not in st.session_state:
    st.session_state["instr_table"] = pd.DataFrame(
        {
            "Instrument Name": [
                instr.data.alias for instr in Connections.InstrumentsList
            ],
            "COM PORT": [
                instr.scpi_instrument.port for instr in Connections.InstrumentsList
            ],
            "BAUD RATE": [
                instr.scpi_instrument.resource_params["baud_rate"]
                for instr in Connections.InstrumentsList
            ],
            "IDN": [instr.scpi_instrument.id for instr in Connections.InstrumentsList],
        }
    )

# Application title
st.subheader("Connected Instruments", divider=True)

# Display the instruments table
st.table(st.session_state["instr_table"])

# Create columns for button alignment
col1, col2 = st.columns([3, 1])

# Button to refresh the data
with col1:
    st.button("Refresh", on_click=verify_instruments)

# Button to full refresh the data, aligned to the right
with col2:
    st.button("Full Refresh", on_click=verify_instruments, args=(1,))

# Button to full refresh the data, aligned to the right
with col1:
    st.button("Save", on_click=save_config)

# Load previous config save
with col2:
    st.button("Load", on_click=Connections.load_config)
    verify_instruments(mode=0)

# Terminal box section
st.subheader("Terminal box", divider=True)

# List of instruments for the selectbox
instrument_formatted: List[str] = [
    f"{instr.data.alias}, IDN:{instr.data.idn}" for instr in Connections.InstrumentsList
]

# Selectbox to choose an instrument
curInstrSelected: str = st.selectbox("Instrument", instrument_formatted)
if curInstrSelected is not None:
    # Initialize buffer output in session state if not already present
    if f"{curInstrSelected}_buffer_output" not in st.session_state:
        st.session_state[f"{curInstrSelected}_buffer_output"] = ""

    # Get the selected instrument object
    curinstrumentIndex: int = instrument_formatted.index(curInstrSelected)
    curinstrumentObject: Instrument_Entry = Connections.InstrumentsList[
        curinstrumentIndex
    ]
    # Text input for user command
    user_input: str = st.text_input(
        "Input to device:", value="", placeholder="Type a command"
    )

    # Button to send the command to the device
    st.button("Send", on_click=send_command, args=(curinstrumentObject, user_input))

    # Text area to display the output from the device
    buffer_output: str = st.text_area(
        "Output from device:",
        value=st.session_state[f"{curInstrSelected}_buffer_output"],
        height=200,
        max_chars=None,
        key=None,
        disabled=True,
    )
