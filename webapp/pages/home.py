import streamlit as st
from connections import Connections
import pandas as pd
from config import Config
from easy_scpi import Instrument
from typing import List
from instruments import Instrument_Entry

conn_obj = Connections()
conf_obj = Config()


def baud_or_usb(instr: Instrument_Entry) -> str:
    """Return the baud rate or USBMTC resource string."""
    if instr.data.baud_rate != 0:
        return f"{instr.data.baud_rate}"
    else:
        return f"USBMTC Resource: {instr.data.port}"


def verify_instruments(mode: int = 0, clear_list: bool = True):
    """Verify or fetch all instruments based on the mode."""
    aliases = conf_obj.get("instr_aliases")
    try:
        if mode == 0:
            conn_obj.verify_instruments()
        elif clear_list:
            conn_obj.fetch_all_instruments(curAliasesList=aliases)
        else:
            conn_obj.fetch_all_instruments(curAliasesList=aliases, clear_list=False)
    except:
        st.error("Error while fetching instruments")
    # Update session state with the instruments data
    instr_list: List[Instrument_Entry] = conn_obj.instruments_list
    st.session_state["instr_table"] = pd.DataFrame(
        {
            "Instrument Name": [instr.data.name for instr in instr_list],
            "COM PORT": [instr.scpi_instrument.port for instr in instr_list],
            "BAUD RATE": [baud_or_usb(instr) for instr in instr_list],
            "IDN": [instr.data.idn for instr in instr_list],
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
            ] += f"{instr_selected.data.name}: {command}\n"
            st.success("Command executed successfully")
    except RuntimeError as exception:
        st.error(f"An error occurred: {exception}")


def save_config():
    conn_obj.save_config()
    st.success("Configuration saved successfully!")


def load_config():
    conn_obj.load_config()
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
button_cols = st.columns([1, 1, 1, 1, 1])

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

# Button to fetch only newly connected instruments
with button_cols[2]:
    if st.button("🔃 Partial Refresh"):
        verify_instruments(mode=1, clear_list=False)
        st.success("New instruments fetched successfully!")

# Button to save the configuration
with button_cols[3]:
    if st.button("💾 Save Configuration"):
        save_config()

# Button to load the configuration
with button_cols[4]:
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
    for instr in conn_obj.instruments_list
]

# Selectbox to choose an instrument
# curInstrSelected will be basically the full idn string
curInstrSelected: str = st.selectbox("🔍 Select Instrument", instrument_formatted)

if curInstrSelected is not None:
    # Initialize buffer output in session state if not already present
    if f"{curInstrSelected}_buffer_output" not in st.session_state:
        st.session_state[f"{curInstrSelected}_buffer_output"] = ""

    # Get the selected instrument object
    curinstrumentIndex: int = instrument_formatted.index(curInstrSelected)
    curinstrumentObject: Instrument_Entry = conn_obj.instruments_list[
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
