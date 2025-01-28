from dataclasses import dataclass
from typing import List
from easy_scpi import Instrument
from instruments import SCPI_Info
from instruments import property_info

# Replace "RaspberrySIM" with the name of the instrument class


class RaspberrySIM(Instrument):
    """
    Class RaspberrySIM
    ==================
    A template class that provides a reference implementation for adding support for a
    specific instrument by extending the Instrument base class. Users can modify or extend
    functionality to fit their instrument needs.
    Attributes
    ----------
    properties_list : List[property_info]
        Holds the definitions for instrument-specific properties (e.g., voltage, current, etc.).
    Methods
    -------
    __init__(scpi_info: SCPI_Info):
        Initializes the instrument connection with provided SCPI parameters, such as port
        and baud rate. Inherits from the base Instrument class and sets up a default timeout.
    init_properties() -> None:
        Defines instrument-specific properties by populating the properties_list with
        property_info instances. Each entry configures a property (name, type, getter, setter)
        for interactions.
    voltp : property
        A property that reflects the instrument's voltage. Reading this property returns
        the current voltage reading, while setting this property updates the instrument's voltage.
        Internally, it calls the appropriate getter/setter methods to handle the voltage data.
    Usage Guidance
    --------------
    1. Initialize an instance of RaspberrySIM by passing the relevant SCPI_Info parameters
       (e.g., port, baud rate).
    2. After creation, call init_properties() to ensure the custom properties are available
       and configured.
    3. Use the voltp property to read or set the instrument's voltage. Additional properties
       can be added to init_properties() to extend functionality.
    4. Extend or override methods as needed to achieve custom behavior for specific hardware.
    """

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
