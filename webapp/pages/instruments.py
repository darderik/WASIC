import streamlit as st
from connections import Connections
from config import Config
from webapp.web_utilities import (
    craft_property_info_list,
    send_parameters,
    create_properties_dataframe,
)
from pymeasure.instruments import Instrument
connections_obj = Connections()
conf_obj = Config()


def instruments_page(alias: str) -> None:
    # Retrieve the instrument based on the alias
    instr = connections_obj.get_instrument(alias)
    if instr is not None:
        cur_scpi_instrument: Instrument = instr.scpi_instrument
        instr_name: str = instr.data.idn  # IDN or ALIAS?
        # Display Instrument Name
        st.subheader(f"🔌 {instr_name}")

        # Tries with getting properties without an allow list
        instr_properties = getattr(cur_scpi_instrument, "properties_list", None)
        if not instr_properties:
            instr_properties = craft_property_info_list(cur_scpi_instrument)
        has_properties = bool(instr_properties)

        if has_properties:
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
                    messages = send_parameters(instr_properties, edited_df)
                    for message in messages:
                        if message.startswith("Error"):
                            st.error(message)
                        else:
                            st.success(message)

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
