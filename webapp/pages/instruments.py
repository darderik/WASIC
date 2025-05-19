import streamlit as st
from typing import List, Optional
from dataclasses import dataclass
from connections import Connections
from config import Config
from instruments.properties import property_info
from easy_scpi import Instrument  # Adjust the import path as necessary
from easy_scpi import helper_methods

connections_obj = Connections()
conf_obj = Config()


def send_parameters(instr_properties: List[property_info]) -> None:
    for prop in instr_properties:
        # Retrieve the value from the input box, using session state
        unparsed_value: str = st.session_state[prop.alias + "_input"]
        supposed_type = prop.typecheck
        try:
            if prop.typecheck != bool:
                parsed_value = supposed_type(unparsed_value)
            else:
                parsed_value = helper_methods.val_to_bool(unparsed_value)
            if (
                parsed_value != prop.associated_getter()
                and unparsed_value != prop.associated_getter()
            ):
                prop.associated_setter(parsed_value)
        except Exception:
            st.error(f"Error parsing value for {prop.alias}")


def instruments_page(alias: str) -> None:
    # Retrieve the instrument based on the alias
    instr = connections_obj.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.idn  # IDN or ALIAS?
        # Display Instrument Name
        st.subheader(f"🔌 {instr_name}")

        # Display Properties if available
        str_properties_types: List[str] = conf_obj.get("init_properties_types", [])
        # Hacky way for converting the class name to string
        has_properties: bool = (
            len(
                [
                    is_prop
                    for is_prop in str_properties_types
                    if is_prop in str(type(cur_scpi_instrument))
                ]
            )
            > 0
        )
        if has_properties:
            instr_properties: List[property_info] = cur_scpi_instrument.properties_list
            with st.form(key="properties_form"):
                # Table headers for a clean look
                col_prop, col_type, col_value = st.columns([2, 1, 3])
                with col_prop:
                    st.markdown("**Property**")
                with col_type:
                    st.markdown("**Type**")
                with col_value:
                    st.markdown("**Value**")
                st.markdown("---")
                # Iterate over each property to create input widgets
                for prop in instr_properties:
                    row_col1, row_col2, row_col3 = st.columns([2, 1, 3])
                    with row_col1:
                        st.write(prop.alias)
                    with row_col2:
                        st.write(prop.typecheck.__name__)
                    with row_col3:
                        if prop.typecheck == bool:
                            # Use radio with no label to save space
                            default_idx = (
                                0
                                if helper_methods.val_to_bool(prop.associated_getter())
                                else 1
                            )
                            st.radio(
                                "",
                                ["ON", "OFF"],
                                key=f"{prop.alias}_input",
                                index=default_idx,
                                horizontal=True,
                            )
                        else:
                            st.text_input(
                                "",
                                value=prop.associated_getter(),
                                key=f"{prop.alias}_input",
                            )
                # Submit button to apply changes
                st.form_submit_button(
                    "📤 Send Parameters",
                    on_click=send_parameters,
                    args=(instr_properties,),
                )


with st.container():
    # Main Instruments Configurator Page
    st.title("🛠️ Instruments Configurator")

    # Instrument Selection Dropdown
    instr_selectbox: str = st.selectbox(
        "🔍 Select Instrument",
        connections_obj.get_instruments_aliases(idn=True),
        help="Choose an instrument to configure.",
        key="instr_selectbox",
    )

# Display the selected instrument's configuration page
with st.container():
    if instr_selectbox:
        instruments_page(instr_selectbox)
