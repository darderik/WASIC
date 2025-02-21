from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from easy_scpi import Property as Scpi_Property
from config import Config


class K2000(Instrument):
    """
    K2000 Class
    ===========
    Class to configure and use the Keithley 2000 multimeter via SCPI,
    using properties to configure the instrument (range and resolution).

    Properties
    ----------
    range_dc : float
        Range for DC voltage measurement (getter and setter).
    resolution_dc : int
        Resolution for DC voltage measurement (getter and setter).
    range_ac : float
        Range for AC voltage measurement (getter and setter).
    resolution_ac : int
        Resolution for AC voltage measurement (getter and setter).

    Methods
    -------
    measure_voltage_dc() -> float:
        Performs a DC voltage measurement.
    measure_voltage_ac() -> float:
        Performs an AC voltage measurement.
    """

    def __init__(self, scpi_info: SCPI_Info):
        """
        Initializes the K2000 object with the specified SCPI parameters.

        Parameters
        ----------
        scpi_info : SCPI_Info
            Object containing port and baud rate for the connection.
        """
        curPort: str = scpi_info.port
        curBaudRate: int = scpi_info.baud_rate
        super().__init__(port=curPort, timeout=5000, baud_rate=curBaudRate)

    def disable_beep(self) -> None:
        """
        Disables the beep sound.
        """
        self.write(":SYST:BEEP:STAT OFF")

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = [
            property_info(
                "Range DC",
                float,
                lambda: self.range_dc,
                lambda x: setattr(self, "range_dc", x),
            ),
            property_info(
                "Resolution DC",
                int,
                lambda: self.resolution_dc,
                lambda x: setattr(self, "resolution_dc", x),
            ),
            property_info(
                "Range AC",
                float,
                lambda: self.range_ac,
                lambda x: setattr(self, "range_ac", x),
            ),
            property_info(
                "Resolution AC",
                int,
                lambda: self.resolution_ac,
                lambda x: setattr(self, "resolution_ac", x),
            ),
            property_info(
                "Auto Range",
                bool,
                lambda: self.autorange,
                lambda x: setattr(self, "autorange", x),
            ),
        ]

    @property
    def autorange(self):
        """
        Returns the auto range setting for DC voltage measurement.
        """
        return Scpi_Property.val2bool(int(self.query(":SENS:VOLT:DC:RANGE:AUTO?")))

    @autorange.setter
    def autorange(self, value: str):  # Accepts ON OFF
        """
        Sets the auto range for DC voltage measurement.
        """
        self.write(f":SENS:VOLT:DC:RANGE:AUTO {Scpi_Property.val2state(value)}")

    @property
    def range_dc(self):
        """
        Returns the configured range for DC measurement.
        """
        return float(self.query(":SENS:VOLT:DC:RANG?"))

    @range_dc.setter
    def range_dc(self, value: float):
        """
        Configures the range for DC measurement.
        """
        # self.write(f":SENS:VOLT:DC:RANG {value}")
        self.sens.volt.dc.range(value)

    @property
    def resolution_dc(self):
        """
        Returns the configured resolution for DC measurement.
        """
        return int(self.query(":SENS:VOLT:DC:DIG?"))

    @resolution_dc.setter
    def resolution_dc(self, value: int):
        """
        Configures the resolution for DC measurement.
        """
        self.write(f":SENS:VOLT:DC:DIG {value}")

    @property
    def range_ac(self):
        """
        Returns the configured range for AC measurement.
        """
        return float(self.query(":SENS:VOLT:AC:RANG?"))

    @range_ac.setter
    def range_ac(self, value: float):
        """
        Configures the range for AC measurement.
        """
        self.write(f":SENS:VOLT:AC:RANG {value}")

    @property
    def resolution_ac(self):
        """
        Returns the configured resolution for AC measurement.
        """
        return int(self.query(":SENS:VOLT:AC:DIG?"))

    @resolution_ac.setter
    def resolution_ac(self, value: int):
        """
        Configures the resolution for AC measurement.
        """
        self.write(f":SENS:VOLT:AC:DIG {value}")

    def read_measurement(self) -> float:
        """
        Reads a measurement value.
        """
        return float(self.query(":READ?"))

    def measure_voltage_dc(self) -> float:
        """
        Performs a DC voltage measurement.

        Returns
        -------
        float
            Measured DC voltage value.
        """
        self.write(":CONF:VOLT:DC")
        # Read the DC voltage measurement
        response = self.query(":READ?")
        return float(response)

    def measure_voltage_ac(self) -> float:
        """
        Performs an AC voltage measurement.

        Returns
        -------
        float
            Measured AC voltage value.
        """
        self.write(":CONF:VOLT:AC")
        response = self.query(":READ?")
        return float(response)

    def configure_4w_resistance(self, range: float = -1) -> None:
        """
        Configures the instrument for 4-wire resistance measurement.

        Parameters
        ----------
        range : float, optional
            If left default, set to -1 and interpreted as auto range on.
        """
        if range < 0:
            # Auto range
            self.write(":SENS:FRES:RANG:AUTO ON")
        else:
            self.write(f":SENS:FRES:RANG {range}")
        self.write(":CONF:FRES")


# Mandatory append to register instrument class with its alias
Config.instruments_extensions.append(("MODEL 2000", K2000))
