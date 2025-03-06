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
from user_defined.tasks import *


def main():
    # Init tasks
    script_path = os.path.abspath("streamlit_app.py")

    # Avvio di Streamlit
    streamlit.web.bootstrap.run(script_path, False, [], {})

    print("Streamlit has terminated.")


if __name__ == "__main__":
    main()
