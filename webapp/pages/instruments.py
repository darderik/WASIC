import streamlit as st
from typing import List, Optional
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument  # Adjust the import path as necessary
from easy_scpi import Property as Scpi_Property


def send_parameters(instr_properties: List[property_info]) -> None:
    for prop in instr_properties:
        # Retrieve the value from the input box, using session state
        unparsed_value: str = st.session_state[prop.alias + "_input"]
        supposed_type = prop.typecheck
        try:
            parsed_value = supposed_type(unparsed_value)
            if unparsed_value != prop.associated_getter():
                prop.associated_setter(parsed_value)
        except Exception:
            st.error(f"Error parsing value for {prop.alias}")


def instruments_page(alias: str) -> None:
    # Retrieve the instrument based on the alias
    instr = Connections.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.idn  # IDN or ALIAS?
        # Display Instrument Name
        st.subheader(f"🔌 {instr_name}")

        # Display Properties if available
        if (
            cur_scpi_instrument.properties_list is not None
            and len(cur_scpi_instrument.properties_list) > 0
        ):
            instr_properties: List[property_info] = cur_scpi_instrument.properties_list

            # Table Headers
            header_col1, header_col2, header_col3 = st.columns([2, 1, 3])
            with header_col1:
                st.markdown("**Property**")
            with header_col2:
                st.markdown("**Type**")
            with header_col3:
                st.markdown("**Value**")
            st.divider()
            # Display Each Property
            for prop in instr_properties:
                row_col1, row_col2, row_col3 = st.columns([2, 1, 3])
                with row_col1:
                    st.write(f"{prop.alias}:")
                with row_col2:
                    st.write(f"{prop.typecheck.__name__}")
                with row_col3:
                    if prop.typecheck == bool:
                        st.radio(
                            "Select",
                            ["ON", "OFF"],
                            key=f"{prop.alias}_input",
                            index=(
                                0
                                if Scpi_Property.val2bool(prop.associated_getter())
                                else 1
                            ),
                            horizontal=True,
                        )
                    else:
                        st.text_input(
                            "Enter Value",
                            value=prop.associated_getter(),
                            key=f"{prop.alias}_input",
                        )
                st.divider()
            # Send Parameters Button
            st.button(
                "📤 Send Parameters",
                on_click=send_parameters,
                args=(instr_properties,),
                key="send_parameters_button",
                disabled=False,
                help="Click to send the updated parameters to the instrument.",
            )


with st.container():
    # Main Instruments Configurator Page
    st.title("🛠️ Instruments Configurator")

    # Instrument Selection Dropdown
    instr_selectbox: str = st.selectbox(
        "🔍 Select Instrument",
        Connections.get_instruments_aliases(idn=True),
        help="Choose an instrument to configure.",
        key="instr_selectbox",
    )

# Display the selected instrument's configuration page
with st.container():
    if instr_selectbox:
        instruments_page(instr_selectbox)
