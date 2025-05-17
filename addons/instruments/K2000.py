from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
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
        super().__init__(
            port=curPort,
            baud_rate=curBaudRate,
            read_termination="\n",
            write_termination="\n",
            timeout=5000,
        )
        self.connect()
        self.disable_beep()
        self.init_properties()

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
        curRead: str = self.query(":READ?")
        return float(curRead)

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

    def configure_2w_resistance(
        self,
        range: float = -1,
        nplc: float = 1,
        filter_ON: bool = False,
        filter_type: str = "MOV",
        filter_count: int = 1,
    ) -> None:
        """
        Configures the instrument for 2-wire resistance measurement.

        Parameters
        ----------
        range : float, optional (default=-1)
            If left default, set to -1 and interpreted as auto range on.
        nplc : float, optional (default=1)
            Number of power line cycles.
        filter_ON : bool, optional (default=False)
            Enable filtering if True.
        filter_type : str, optional (default="MOV")
            Type of filter to use.
        filter_count : int, optional (default=1)
            Number of samples for the filter.
        """
        # Configure filter if enabled
        if filter_ON:
            self.write(f":SENS:RES:FILT:TYPE {filter_type}")
            self.write(f":SENS:RES:FILT:COUNT {filter_count}")
            self.write(":SENS:RES:FILT:STAT ON")

        # Set integration time
        self.write(f":SENS:RES:NPLC {nplc}")

        # Set range: auto range if value < 0, manual otherwise
        if range < 0:
            self.write(":SENS:RES:RANG:AUTO ON")
        else:
            self.write(f":SENS:RES:RANG {range}")

        # Configure measurement mode for 2-wire resistance
        self.write(":CONF:RES")

    def configure_4w_resistance(
        self,
        range: float = -1,
        nplc: float = 1,
        filter_ON: bool = False,
        filter_type: str = "MOV",
        filter_count: int = 1,
    ) -> None:
        """
        Configures the instrument for 4-wire resistance measurement.

        Parameters
        ----------
        range : float, optional (default=-1)
            If left default, set to -1 and interpreted as auto range on.
        nplc : float, optional (default=1)
            Number of power line cycles.
        """
        # Configure filter
        if filter_ON:
            self.write(f":SENS:FRES:FILT:TYPE {filter_type}")
            self.write(f":SENS:FRES:FILT:COUNT {filter_count}")
            self.write(":SENS:FRES:FILT:STAT ON")

        self.write(":SENS:FRES:NPLC {}".format(nplc))  # 0.01 to 10S
        if range < 0:
            # Auto range
            self.write(":SENS:FRES:RANG:AUTO ON")
        else:
            self.write(f":SENS:FRES:RANG {range}")
        self.write(":CONF:FRES")


# Mandatory append to register instrument class with its alias
Config().add_instrument_extension(("Model 2000", K2000))
