import streamlit as st
import pandas as pd
from typing import List
from connections import Connections
from config import Config
from instruments.properties import property_info
from easy_scpi import Instrument  # Adjust the import path as necessary
from easy_scpi import helper_methods

connections_obj = Connections()
conf_obj = Config()


def send_parameters(
    instr_properties: List[property_info], edited_data: pd.DataFrame
) -> None:
    """Send the edited parameters to the instruments"""
    for i, prop in enumerate(instr_properties):
        try:
            # Get the edited value from the dataframe
            new_value = edited_data.iloc[i]["Current Value"]
            supposed_type = prop.typecheck

            # Parse the value based on type
            if prop.typecheck == bool:
                parsed_value = helper_methods.val_to_bool(str(new_value))
            else:
                parsed_value = supposed_type(new_value)

            # Only update if the value has changed
            current_value = prop.associated_getter()
            if parsed_value != current_value:
                prop.associated_setter(parsed_value)
                st.success(f"Updated {prop.alias} to {parsed_value}")
        except Exception as e:
            st.error(f"Error updating {prop.alias}: {str(e)}")


def create_properties_dataframe(instr_properties: List[property_info]) -> pd.DataFrame:
    """Create a DataFrame from instrument properties for the data editor"""
    data = []
    for prop in instr_properties:
        current_value = prop.associated_getter()
        # Format boolean values for better display
        if prop.typecheck == bool:
            display_value = "ON" if helper_methods.val_to_bool(current_value) else "OFF"
        else:
            display_value = str(current_value)

        data.append(
            {
                "Property": prop.alias,
                "Type": prop.typecheck.__name__,
                "Current Value": display_value,
            }
        )

    return pd.DataFrame(data)


def instruments_page(alias: str) -> None:
    # Retrieve the instrument based on the alias
    instr = connections_obj.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.idn  # IDN or ALIAS?
        # Display Instrument Name
        st.subheader(f"🔌 {instr_name}")

        # Display Properties if available
        str_properties_types: List[str] = (
            conf_obj.get("init_properties_types", []) or []
        )
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

            # Create DataFrame for the data editor
            properties_df = create_properties_dataframe(instr_properties)

            st.markdown("### 📊 Instrument Properties")
            st.markdown(
                "Edit the values in the table below and click 'Send Parameters' to apply changes."
            )

            # Use st.data_editor to create an editable table
            edited_df = st.data_editor(
                properties_df,
                use_container_width=True,
                num_rows="fixed",
                disabled=["Property", "Type"],  # Make these columns read-only
                column_config={
                    "Property": st.column_config.TextColumn(
                        "Property",
                        help="The property name",
                        width="medium",
                    ),
                    "Type": st.column_config.TextColumn(
                        "Type",
                        help="The data type of the property",
                        width="small",
                    ),
                    "Current Value": st.column_config.TextColumn(
                        "Current Value",
                        help="Edit this value. Use ON/OFF for boolean properties.",
                        width="medium",
                    ),
                },
                key=f"properties_editor_{alias}",
            )

            # Add some spacing
            st.markdown("---")

            # Send Parameters button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(
                    "📤 Send Parameters",
                    use_container_width=True,
                    type="primary",
                    key=f"send_params_{alias}",
                ):
                    send_parameters(instr_properties, edited_df)

            # Display current vs edited comparison if there are changes
            if not properties_df.equals(edited_df):
                st.markdown("### 🔄 Pending Changes")
                changes_detected = False
                for i in range(len(properties_df)):
                    if (
                        properties_df.iloc[i]["Current Value"]
                        != edited_df.iloc[i]["Current Value"]
                    ):
                        changes_detected = True
                        prop_name = properties_df.iloc[i]["Property"]
                        old_val = properties_df.iloc[i]["Current Value"]
                        new_val = edited_df.iloc[i]["Current Value"]
                        st.info(f"**{prop_name}**: {old_val} → {new_val}")

                if not changes_detected:
                    st.info("No changes detected.")
        else:
            st.info("No configurable properties available for this instrument.")


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
