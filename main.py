import os
from connections import Connections
import streamlit.web.bootstrap
from instruments import Instrument_Wrapper, RaspberrySIM
from easy_scpi.scpi_instrument import SCPI_Instrument
from instruments import SCPI_Info
from serial import Serial

# Global variables


def main():
    # Init connection class
    # Connections.fetch_all_instruments(["Raspberry"])

    # Manually add for debug
    try:
        # Craft SCPI Info
        scpi_info: SCPI_Info = SCPI_Info(
            port="COM6", baud_rate=115200, idn="Raspberry Pi SPI...", alias="Raspberry"
        )
        curInWrapper: Instrument_Wrapper = Instrument_Wrapper(
            idn="Raspberry Pi SPI...",
            name="Raspberry Pi",
            scpi_instrument=RaspberrySIM(scpi_info),
        )
        Connections.InstrumentsList.append(curInWrapper)
    except:
        pass
    ## end debug section

    # Path del file Streamlit
    script_path = os.path.abspath("streamlit_app.py")

    # Avvio di Streamlit
    streamlit.web.bootstrap.run(script_path, False, [], {})

    print("Streamlit has terminated.")


if __name__ == "__main__":
    main()
