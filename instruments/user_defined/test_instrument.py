from dataclasses import dataclass
from typing import List
from easy_scpi import Instrument
from ..instrument_entry import SCPI_Info
from ..properties import property_info

# Replace "RaspberrySIM" with the name of the instrument class


class RaspberrySIM(Instrument):
    def __init__(self, scpi_info: SCPI_Info):
        curPort: str = scpi_info.port
        curBaudRate: int = scpi_info.baud_rate
        super().__init__(
            port=curPort,
            timeout=5000,
            baud_rate=curBaudRate,
        )

        # other initialization code...

    # Begin custom code, specific to instrument
    # Include this even if no init_properties() method is defined
    properties_list: List[property_info] = []

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = [
            property_info(
                "Voltage",
                float,
                lambda: self.voltp,
                lambda val: setattr(self, "voltp", val),
            ),
        ]

    def read(self) -> str:
        """
        Read data from the instrument.
        """
        curStr: str = super().read()
        return curStr

    ## End custom code, specific to instrument
    @property
    def voltp(self):
        """
        Returns the voltage reading.
        """
        return self.voltage()

    @voltp.setter
    def voltp(self, volts):
        """
        Sets the voltage of the instrument.
        """
        self.voltage(volts)
