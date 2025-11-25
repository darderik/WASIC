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
def use_as_library():
    # Load TBS and relay matrix
    conn_object = Connections()
    conn_object.fetch_all_instruments()
    tasks = Tasks()
    tasks.run_task("R Cube (SM2401 source + K2000 volt)")