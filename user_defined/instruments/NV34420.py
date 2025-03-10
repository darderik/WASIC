from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from easy_scpi import Property as Scpi_Property
from config import Config


class NV34420(Instrument):
    """
    NV34420 Class
    ============
    Class to configure and use the Keysight 34420A Nano Volt/Micro Ohm Meter via SCPI.

    Features:
    ---------
    - Perform voltage and resistance measurements.
    - Configure voltage measurement parameters such as range and integration time.
    - Configure resistance measurement parameters including range, integration time,
      and optional digital filtering for 4-wire measurements.

    Properties:
    -----------
    voltage_range : float
        Configured voltage measurement range.
    integration_time : float
        Integration time (NPLC) for voltage measurements.
    resistance_range : float
        Configured resistance measurement range.

    Methods:
    --------
    measure_voltage() -> float:
        Performs a voltage measurement.
    measure_resistance() -> float:
        Performs a resistance measurement.
    configure_resistance(range: float, nplc: float, filter_ON: bool, filter_type: str, filter_count: int) -> None:
        Configures the meter for 4-wire resistance measurement.
    """

    def __init__(self, scpi_info: SCPI_Info):
        """
        Initializes the NV34420 object with the specified SCPI parameters.

        Parameters
        ----------
        scpi_info : SCPI_Info
            Object containing port and baud rate information for the connection.
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

    def init_properties(self) -> None:
        """
        Initializes the instrument properties for use in configuration.
        """
        self.properties_list: List[property_info] = [
            property_info(
                "Voltage Range",
                float,
                lambda: self.voltage_range,
                lambda x: setattr(self, "voltage_range", x),
            ),
            property_info(
                "Integration Time",
                float,
                lambda: self.integration_time,
                lambda x: setattr(self, "integration_time", x),
            ),
            property_info(
                "Resistance Range",
                float,
                lambda: self.resistance_range,
                lambda x: setattr(self, "resistance_range", x),
            ),
        ]

    @property
    def voltage_range(self) -> float:
        """
        Returns the configured voltage measurement range.
        """
        return float(self.query(":SENS:VOLT:DC:RANG?"))

    @voltage_range.setter
    def voltage_range(self, value: float) -> None:
        """
        Sets the voltage measurement range.
        """
        self.write(f":SENS:VOLT:DC:RANG {value}")

    @property
    def integration_time(self) -> float:
        """
        Returns the integration time (in NPLC) for voltage measurements.
        """
        return float(self.query(":SENS:VOLT:DC:NPLC?"))

    @integration_time.setter
    def integration_time(self, value: float) -> None:
        """
        Sets the integration time (in NPLC) for voltage measurements.
        """
        self.write(f":SENS:VOLT:DC:NPLC {value}")

    @property
    def resistance_range(self) -> float:
        """
        Returns the configured resistance measurement range.
        """
        return float(self.query(":SENS:FRES:RANG?"))

    @resistance_range.setter
    def resistance_range(self, value: float) -> None:
        """
        Sets the resistance measurement range.
        """
        self.write(f":SENS:FRES:RANG {value}")

    def measure_voltage(self) -> float:
        """
        Performs a voltage measurement.

        Returns
        -------
        float
            Measured voltage value.
        """
        self.write(":CONF:VOLT")
        response = self.query(":READ?")
        return float(response)

    def measure_resistance(self) -> float:
        """
        Performs a resistance measurement.

        Returns
        -------
        float
            Measured resistance value.
        """
        self.write(":CONF:FRES")
        response = self.query(":READ?")
        return float(response)

    def read_meas(self) -> float:
        result: str = self.query(":READ?")
        return float(result)

    def configure_resistance(
        self,
        range: float = -1,
        nplc: float = 1,
        filter_ON: bool = False,
        filter_type: str = "MOV",
        filter_count: int = 1,
    ) -> None:
        """
        Configures the meter for 4-wire resistance measurement.

        Parameters
        ----------
        range : float, optional
            Resistance range value. If negative, auto ranging is enabled.
        nplc : float, optional
            Number of power line cycles for integration (affects noise and speed).
        filter_ON : bool, optional
            Whether to enable the digital filter.
        filter_type : str, optional
            Type of filter to use (e.g., "MOV").
        filter_count : int, optional
            Number of readings for the digital filter averaging.
        """
        if filter_ON:
            self.write(f":SENS:FRES:FILT:TYPE {filter_type}")
            self.write(f":SENS:FRES:FILT:COUNT {filter_count}")
            self.write(":SENS:FRES:FILT:STAT ON")
        self.write(f":SENS:FRES:NPLC {nplc}")
        if range < 0:
            self.write(":SENS:FRES:RANG:AUTO ON")
        else:
            self.write(f":SENS:FRES:RANG {range}")
        self.write(":CONF:FRES")

    def configure_voltage(self, range: float = -1, nplc: float = 1) -> None:
        """
        Configures the meter for voltage measurement.
        Parameters
        ----------
        range : float, optional
            Voltage range value. If negative, auto ranging is enabled.
        nplc : float, optional
            Number of power line cycles for integration (affects noise and speed).
        """
        self.integration_time = nplc
        if range < 0:
            self.write(":SENS:VOLT:DC:RANG:AUTO ON")
        else:
            self.voltage_range = range
        self.write(":CONF:VOLT")


# Register the instrument class with its alias
Config().add_instrument_extension(("NV34420", NV34420))
