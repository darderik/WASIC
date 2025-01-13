import streamlit as st
from typing import List, Optional
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument  # Adjust the import path as necessary


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
            except:
                st.error(f"Error parsing value for {prop_wrap.property.alias}")


def instruments_page(alias: str) -> None:
    # Check array of instruments
    instr = Connections.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.alias
        instr_port: str = instr.scpi_instrument.port
        instr_baud: int = instr.scpi_instrument.resource_params["baud_rate"]
        info_col1, info_col2 = st.columns([1, 1])
        st.subheader(instr_name, divider=True)
        with info_col1:
            st.write(f"COM PORT: {instr_port}")
        with info_col2:
            st.write(f"BAUD RATE: {instr_baud}")
        if (
            hasattr(cur_scpi_instrument, "init_properties")
            and callable(getattr(cur_scpi_instrument, "init_properties"))
            and cur_scpi_instrument.properties_list is not None
            and cur_scpi_instrument.properties_list != []
        ):
            instr_properties: List[property_info] = cur_scpi_instrument.properties_list
            # Intestazioni delle colonne
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.subheader("Property")
            with col2:
                st.subheader("Type")
            with col3:
                st.subheader("Value")

            st.divider()  # Linea orizzontale dopo le intestazioni

            prop_wrapper_list: List[prop_wrapper] = []
            # Aggiunta delle proprietà con separazione visiva1
            for prop in instr_properties:
                col1, col_sep1, col2, col_sep2, col3 = st.columns([1, 0.1, 1, 0.1, 2])
                curBox: Optional[str] = ""
                # Title
                with col1:
                    st.write(f"{prop.alias}:")
                # Type
                with col2:
                    st.write(f"{prop.typecheck.__name__}")
                # Value box
                with col3:
                    if prop.typecheck == bool:
                        curBox = st.radio("Switch", ["ON", "OFF"])
                    else:
                        curBox = st.text_input(
                            "ValueBox", value=prop.associated_getter()
                        )

                with col_sep1:
                    st.markdown("|")  # Simula una barra verticale
                with col_sep2:
                    st.markdown("|")  # Simula una barra verticale
                prop_wrapper_list.append(prop_wrapper(prop, curBox))
                st.divider()  # Linea orizzontale tra le righe
            st.button(
                "Send parameters", on_click=send_parameters, args=(prop_wrapper_list,)
            )


st.title("Instruments configurator")
instr_selectbox: str = st.selectbox(
    "Select instrument",
    Connections.get_instruments_aliases(),
)

if instr_selectbox is not None:
    instruments_page(instr_selectbox)
