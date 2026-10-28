from dataclasses import dataclass, field
from serial import Serial
from config import Config
import time
from typing import Optional
import pyvisa as visa
import logging
from pymeasure.instruments import Instrument
from .io import InstrumentIO

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
    resource_str: str = ""
    backend: str = "@py"
    stop_bits: str = "one"
    read_termination: str = "\n"
    write_termination: str = "\n"
    flow_control: str = "none"


@dataclass
class Instrument_Entry:
    data: SCPI_Info
    scpi_instrument: Instrument
    _config: Config = Config()
    io: InstrumentIO = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self.io = InstrumentIO.for_instrument(self.scpi_instrument)

    def write_wrapper(self, command: str) -> None:
        with self.io.transaction():
            self.scpi_instrument.write(command)

    def read_wrapper(self) -> str:
        # The CLS handling should be implemented in the children classes
        # Refer to test_instrument example
        try:
            with self.io.transaction():
                toReturn = self.scpi_instrument.read()
        except visa.errors.VisaIOError as e:
            logger.error(f"VisaIOError occurred: {e}")
            raise
        return toReturn

    def ask_wrapper(self, command) -> str:
        # The CLS handling should be implemented in the children classes
        # Refer to test_instrument example
        toReturn: str = ""
        with self.io.transaction():
            toReturn = self.scpi_instrument.ask(command)
        return toReturn
