from dataclasses import dataclass
from easy_scpi.scpi_instrument import SCPI_Instrument
from serial import Serial
from config import Config, comm_mode
import time


@dataclass
class Instrument_Wrapper:
    idn: str
    name: str
    scpi_instrument: SCPI_Instrument = None
    timeout: int = 2
    com_obj: Serial = None

    def write_command(self, command: str) -> None:
        if Config.communication_mode == comm_mode.pyVisa:
            self.scpi_instrument.write(command)
        else:
            if not self.com_obj.is_open:
                self.com_obj.open()
                self.com_obj.write(command.encode())
            else:
                raise Exception(RuntimeError("Serial port is already open."))

    def read(self) -> str:
        # The CLS handling should be implemented in the children classes
        # Refer to test_instrument example
        toReturn: str = ""
        if Config.communication_mode == comm_mode.pyVisa:
            toReturn = self.scpi_instrument.read()
        else:
            if not self.com_obj.is_open:
                self.com_obj.open()
                time.sleep(self.timeout)
                toReturn = self.com_obj.read_all().decode()
            else:
                raise Exception(RuntimeError("Serial port is already open."))
        return toReturn


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
    idn: str = ""
    alias: str = ""
