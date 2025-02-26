import os
from connections import Connections
import streamlit.web.bootstrap
from instruments import Instrument_Entry
from easy_scpi.scpi_instrument import SCPI_Instrument
from instruments import SCPI_Info
from serial import Serial
from tasks import Task, Tasks, ChartData
from config import Config
from user_defined import custom_instr_handler

# Global variables
#        # Craft SCPI Info
#        scpi_info: SCPI_Info = SCPI_Info(
#            port="COM5", baud_rate=115200, idn="Raspberry Pi SPI 1.0", alias="Raspberry"
#        )
#        curInWrapper: Instrument_Entry = Instrument_Entry(
#            scpi_info,
#            Serial(scpi_info.port, scpi_info.baud_rate),
#            scpi_instrument=RaspberrySIM(scpi_info),
#        )
#        curInWrapper.com_obj.close()
#        curInWrapper.scpi_instrument.connect()
#        curInWrapper.scpi_instrument.init_properties()
#
#        Connections.InstrumentsList.append(curInWrapper)


def main():
    # Init instruments
    # Connections.load_config()
    # Manual instruments

    # Init tasks
    Tasks.init_tasks()
    # Connections.fetch_all_instruments(Config.instrAliasesList)
    # Connections.fetch_all_instruments(Config.instrAliasesList)
    # Path del file Streamlit
    script_path = os.path.abspath("streamlit_app.py")

    # Avvio di Streamlit
    streamlit.web.bootstrap.run(script_path, False, [], {})

    print("Streamlit has terminated.")


if __name__ == "__main__":
    main()
