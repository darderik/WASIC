import test
from connections import Connections
from addons.instruments import  RelayMatrix, TBS1052C
from addons.tasks import Tasks
import logging
from config import Config
import os
import serial
from instruments import SCPI_Info
from typing import cast
from connections.utilities import detect_baud_rate
import gc
import time
import random

def enable_debug_logging():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('pyvisa').setLevel(logging.DEBUG)
    logging.getLogger('pyvisa.resources').setLevel(logging.DEBUG)
    logging.getLogger('pyvisa.ctwrapper').setLevel(logging.DEBUG)
    logging.getLogger('pyvisa.vpp43').setLevel(logging.DEBUG)
    logging.getLogger('pyvisa-py').setLevel(logging.DEBUG)
    # Ensure debug output goes to the terminal (stdout)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    console.setFormatter(formatter)
    logging.getLogger().addHandler(console)

    logging.getLogger('serial').setLevel(logging.DEBUG)
    logging.getLogger('pyvisa.termios').setLevel(logging.DEBUG)
def use_as_library():
    # Load TBS and relay matrix
    conn_object = Connections()
    tbs_scpi_info = SCPI_Info("USB0::1689::964::C034147::0::INSTR", 0, "TBS1052C", "TBS1052C", "TBS1052C")
    relay_matrix_scpi_info = SCPI_Info("ASRL5::INSTR", 115200, "Relay Matrix", "Relay Matrix", "Relay Matrix")
    conn_object._add_instrument(tbs_scpi_info)
    conn_object._add_instrument(relay_matrix_scpi_info)
    #conn_object.fetch_all_instruments()
    tasks = Tasks()
    tbs: TBS1052C = cast(TBS1052C,conn_object.get_instrument("TBS1052C").scpi_instrument)
    relay_matrix = conn_object.get_instrument("Relay Matrix").scpi_instrument
    tasks.run_task("Relay Matrix Transient")

if __name__ == "__main__":
    enable_debug_logging()
    use_as_library()