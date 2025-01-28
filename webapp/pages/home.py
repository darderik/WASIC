import streamlit as st
from connections import Connections
import pandas as pd
from config import Config
from easy_scpi import Instrument
from typing import List
from instruments import Instrument_Entry
from user_defined import RaspberrySIM


def verify_instruments(mode: int = 0):
    """Verify or fetch all instruments based on the mode."""
    if mode == 0:
        Connections.verify_instruments()
    else:
        for instr in Connections.InstrumentsList:
            instr.scpi_instrument.disconnect()
            Connections.InstrumentsList.remove(instr)

        Connections.fetch_all_instruments(Config.instrAliasesList)
    # Update session state with the instruments data
    st.session_state["instr_table"] = pd.DataFrame(
        {
            "Instrument Name": [
                instr.data.idn for instr in Connections.InstrumentsList
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
    st.rerun()  # Hack to refresh the page


def send_command(instr_selected: Instrument_Entry, command: str, uid: str) -> None:
    try:
        if "?" in command:  # This is a query, expect a response
            result: str = instr_selected.query_wrapper(command)
            st.session_state[
                f"{uid}_buffer_output"
            ] += f"{instr_selected.data.alias}: {command} --> {result}\n"
            st.success("Command executed successfully!")
        else:
            instr_selected.write_wrapper(command)
            st.session_state[
                f"{uid}_buffer_output"
            ] += f"{instr_selected.data.alias}: {command}\n"
            st.success("Command executed successfully")
    except RuntimeError as exception:
        st.error(f"An error occurred: {exception}")


def save_config():
    Connections.save_config()
    st.success("Configuration saved successfully!")


def load_config():
    Connections.load_config()
    verify_instruments()
    st.success("Configuration loaded successfully!")


# Set the main title of the page
st.title("WASIC - Web Application for SCPI Instrument Control")

# Initialize the instruments table in session state if not already present
if "instr_table" not in st.session_state:
    verify_instruments()

# Application title
st.subheader("📋 Connected Instruments")

# Display the instruments table
st.table(st.session_state["instr_table"])

# Create columns for button alignment
button_cols = st.columns([1, 1, 1, 1])

# Button to refresh the data
with button_cols[0]:
    if st.button("🔄 Refresh"):
        verify_instruments()
        st.success("Instruments refreshed successfully!")

# Button to full refresh the data
with button_cols[1]:
    if st.button("🔃 Full Refresh"):
        verify_instruments(mode=1)
        st.success("All instruments fetched successfully!")

# Button to save the configuration
with button_cols[2]:
    if st.button("💾 Save Configuration"):
        save_config()

# Button to load the configuration
with button_cols[3]:
    if st.button("📂 Load Configuration"):
        load_config()

# Separator
st.markdown("---")

# Terminal box section
st.subheader("🖥️ Terminal Box")

# List of instruments for the selectbox
instrument_formatted: List[str] = [
    f"{instr.data.alias}, IDN:{instr.data.idn}".strip()
    .replace(",", "_")
    .replace(":", "_")
    .replace(" ", "_")
    for instr in Connections.InstrumentsList
]

# Selectbox to choose an instrument
curInstrSelected: str = st.selectbox("🔍 Select Instrument", instrument_formatted)

if curInstrSelected is not None:
    # Initialize buffer output in session state if not already present
    if f"{curInstrSelected}_buffer_output" not in st.session_state:
        st.session_state[f"{curInstrSelected}_buffer_output"] = ""

    # Get the selected instrument object
    curinstrumentIndex: int = instrument_formatted.index(curInstrSelected)
    curinstrumentObject: Instrument_Entry = Connections.InstrumentsList[
        curinstrumentIndex
    ]

    # Input for user command
    user_input: str = st.text_input(
        "✏️ Input to Device:", value="", placeholder="Type a command"
    )

    # Button to send the command to the device
    if st.button("➡️ Send Command"):
        send_command(curinstrumentObject, user_input, curInstrSelected)

    # Text area to display the output from the device
    st.text_area(
        "📥 Output from Device:",
        value=st.session_state[f"{curInstrSelected}_buffer_output"],
        height=200,
        max_chars=None,
        key=f"{curInstrSelected}_output",
        disabled=True,
    )
