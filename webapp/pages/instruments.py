import streamlit as st
from typing import List, Optional
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument  # Adjust the import path as necessary
from easy_scpi import Property as Scpi_Property


@dataclass
class prop_wrapper:
    property: property_info
    value: Optional[str]


def send_parameters(prop_list: List[prop_wrapper]) -> None:
    for prop_wrap in prop_list:
        if prop_wrap.value is not None:
            # Parse correctly the value based on typecheck
            unparsed_value: str = prop_wrap.value
            supposed_type: type = prop_wrap.property.typecheck
            try:
                parsed_value = supposed_type(unparsed_value)
                if unparsed_value != prop_wrap.property.associated_getter():
                    prop_wrap.property.associated_setter(parsed_value)
            except Exception:
                st.error(f"Error parsing value for {prop_wrap.property.alias}")


def instruments_page(alias: str) -> None:
    # Retrieve the instrument based on the alias
    instr = Connections.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.alias
        instr_port: str = instr.scpi_instrument.port
        instr_baud: int = instr.scpi_instrument.resource_params["baud_rate"]

        # Display Instrument Information
        st.subheader(f"🔌 {instr_name}")
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.write(f"**COM PORT:** {instr_port}")
        with info_col2:
            st.write(f"**BAUD RATE:** {instr_baud}")

        # Display Properties if available
        if (
            hasattr(cur_scpi_instrument, "init_properties")
            and callable(getattr(cur_scpi_instrument, "init_properties"))
            and cur_scpi_instrument.properties_list
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

            prop_wrapper_list: List[prop_wrapper] = []

            # Display Each Property
            for prop in instr_properties:
                row_col1, row_col2, row_col3 = st.columns([2, 1, 3])
                with row_col1:
                    st.write(f"{prop.alias}:")
                with row_col2:
                    st.write(f"{prop.typecheck.__name__}")
                with row_col3:
                    if prop.typecheck == bool:
                        curBox = st.radio(
                            "Select",
                            ["ON", "OFF"],
                            key=f"{prop.alias}_radio",
                            index=(
                                0
                                if Scpi_Property.val2bool(prop.associated_getter())
                                else 1
                            ),
                            horizontal=True,
                        )
                        prop_wrapper_list.append(prop_wrapper(prop, curBox))
                    else:
                        curBox = st.text_input(
                            "Enter Value",
                            value=prop.associated_getter(),
                            key=f"{prop.alias}_input",
                        )
                        prop_wrapper_list.append(prop_wrapper(prop, curBox))
                st.divider()
            # Send Parameters Button
            st.button(
                "📤 Send Parameters",
                on_click=send_parameters,
                args=(prop_wrapper_list,),
                key="send_parameters_button",
                disabled=False,
                help="Click to send the updated parameters to the instrument.",
            )


# Main Instruments Configurator Page
st.title("🛠️ Instruments Configurator")

# Instrument Selection Dropdown
instr_selectbox: str = st.selectbox(
    "🔍 Select Instrument",
    Connections.get_instruments_aliases(),
    help="Choose an instrument to configure.",
)

# Display the selected instrument's configuration page
if instr_selectbox:
    instruments_page(instr_selectbox)
