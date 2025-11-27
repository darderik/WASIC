from dataclasses import dataclass
from easy_scpi.scpi_instrument import SCPI_Instrument
from serial import Serial
from config import Config
import time
from typing import Optional
import pyvisa as visa
import logging

logger = logging.getLogger(__name__)


@dataclass
class SCPI_Info:
    """
    A class to represent SCPI (Standard Commands for Programmable Instruments) information.

    Attributes:
    ----------
    port : str
        The communication port used for the SCPI connection.
    baud_rate : int
        The baud rate for the SCPI connection.
    idn : str
        The identification string of the SCPI instrument.
    alias : str
        The alias name for the SCPI instrument.
    """
    port: str
    baud_rate: int
    idn: str = "default-idn"
    alias: str = "instrument"
    name: str = "instrument"
    backend: str = "@py"


@dataclass
class Instrument_Entry:
    data: SCPI_Info
    scpi_instrument: SCPI_Instrument
    _config: Config = Config()

    def write_wrapper(self, command: str) -> None:
        self.scpi_instrument.write(command)

    def read_wrapper(self) -> str:
        # The CLS handling should be implemented in the children classes
        # Refer to test_instrument example
        try:
            toReturn = self.scpi_instrument.read()
        except visa.errors.VisaIOError as e:
            logger.error(f"VisaIOError occurred: {e}")
            raise
        return toReturn

    def query_wrapper(self, command) -> str:
        # The CLS handling should be implemented in the children classes
        # Refer to test_instrument example
        toReturn: str = ""
        toReturn = self.scpi_instrument.query(command)
        return toReturn
