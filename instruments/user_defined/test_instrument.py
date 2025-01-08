from dataclasses import dataclass
from typing import List
from easy_scpi import Instrument
from ..instrument_wrapper import SCPI_Info

# Replace "RaspberrySIM" with the name of the instrument class


class RaspberrySIM(Instrument):
    def __init__(self, scpi_info: SCPI_Info):
        curPort: str = scpi_info.port
        curBaudRate: int = scpi_info.baud_rate
        super().__init__(
            port=curPort,
            timeout=5000,
            read_termination="\n",
            write_termination="\n",
            baud_rate=curBaudRate,
        )

        # other initialization code...

    def read(self) -> str:
        """
        Read data from the instrument.
        """
        curStr: str = super().read()
        if "CTS" in curStr:
            # We are parsing CTS. take another read
            curStr += "\n" + super().read()
        return curStr

    @property
    def voltage(self):
        """
        Returns the voltage setting.
        """
        return self.source.volt.level()

    @voltage.setter
    def voltage(self, volts):
        """
        Sets the voltage of the instrument.
        """
        self.source.volt.level(volts)
