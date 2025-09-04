import test
from connections import Connections
from addons.instruments import TDS2012C, RelayMatrix, TBS1052C
from addons.tasks import Tasks
import logging
from config import Config
import os
import serial

from connections.utilities import detect_baud_rate


def test_function():
    # Open serial port com4
    logging.basicConfig(level=logging.DEBUG)

    detect_baud_rate("COM6")

test_function()
