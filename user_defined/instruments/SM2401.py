from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from easy_scpi import Property as Scpi_Property
from config import Config


class SM2401(Instrument):
    """
    SM2401 Class
    ============
    Class to configure and use the SM2401 SourceMeter via SCPI commands.

    Typical features:
      - Configure the source mode: VOLT (voltage source) or CURR (current source).
      - Set the output level (voltage or current) and the protection limit (compliance).
      - Read measurements (voltage or current) based on the configuration.

    Properties
    ----------
    source_mode : str
        The source mode, "VOLT" for voltage or "CURR" for current (getter and setter).
    voltage : float
        The programmed voltage level (when in VOLT mode) (getter and setter).
    current : float
        The programmed current level (when in CURR mode) (getter and setter).
    compliance : float
        The protection limit: in VOLT mode, it represents the current protection limit;
        in CURR mode, the voltage protection limit (getter and setter).

    Methods
    -------
    measure_voltage() -> float:
        Performs a voltage measurement.
    measure_current() -> float:
        Performs a current measurement.
    output_on() -> None:
        Turns on the output.
    output_off() -> None:
        Turns off the output.
    """

    def __init__(self, scpi_info: SCPI_Info) -> None:
        """
        Initializes the SM2401 object with the specified SCPI parameters.

        Parameters
        ----------
        scpi_info : SCPI_Info
            Object containing port and baud rate information for the connection.
        """
        super().__init__(
            port=scpi_info.port,
            baud_rate=scpi_info.baud_rate,
            read_termination="\n",
            write_termination="\n",
            timeout=5000,
        )
        self.connect()
        # (Optional) Perform any initial configuration, e.g., disable beeps
        self.disable_beep()
        self.init_properties()

    def disable_beep(self) -> None:
        """Disables the beep (if supported by the device)."""
        self.write(":SYST:BEEP:STAT OFF")

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = [
            property_info(
                "Source Mode",
                str,
                lambda: self.source_mode,
                lambda x: setattr(self, "source_mode", x),
            ),
            property_info(
                "Voltage",
                float,
                lambda: self.voltage,
                lambda x: setattr(self, "voltage", x),
            ),
            property_info(
                "Current",
                float,
                lambda: self.current,
                lambda x: setattr(self, "current", x),
            ),
            property_info(
                "Compliance",
                float,
                lambda: self.compliance,
                lambda x: setattr(self, "compliance", x),
            ),
        ]

    @property
    def source_mode(self) -> str:
        """
        Returns the source mode: "VOLT" if the device is configured to output voltage,
        "CURR" for current.
        """
        # The command returns, for example, "VOLT" or "CURR"
        result: str = self.query(":SOUR:FUNC?")
        return result.strip().replace('"', "")

    @source_mode.setter
    def source_mode(self, mode: str) -> None:
        """
        Sets the source mode.

        Parameters
        ----------
        mode : str
            Must be "VOLT" (voltage source) or "CURR" (current source).
        """
        mode = mode.upper()
        if mode not in ["VOLT", "CURR"]:
            raise ValueError("Mode must be 'VOLT' or 'CURR'.")
        self.write(f":SOUR:FUNC {mode}")

    @property
    def voltage(self) -> float:
        """
        Returns the programmed voltage level (V).
        """
        return float(self.query(":SOUR:VOLT:LEV?"))

    @voltage.setter
    def voltage(self, value: float) -> None:
        """
        Sets the voltage level.

        Parameters
        ----------
        value : float
            Voltage value in V.
        """
        self.write(f":SOUR:VOLT:LEV {value}")

    @property
    def current(self) -> float:
        """
        Returns the programmed current level (in A).
        """
        return float(self.query(":SOUR:CURR:LEV?"))

    @current.setter
    def current(self, value: float) -> None:
        """
        Sets the current level.

        Parameters
        ----------
        value : float
            Current value in A.
        """
        self.write(f":SOUR:CURR:LEV {value}")

    @property
    def compliance(self) -> float:
        """
        Returns the protection limit (compliance value).
        In VOLT mode, it represents the current protection limit; in CURR mode, the voltage protection limit.
        """
        mode = self.source_mode
        if mode == "VOLT":
            return float(self.query(":SENS:CURR:PROT?"))
        elif mode == "CURR":
            return float(self.query(":SENS:VOLT:PROT?"))
        else:
            raise ValueError("Unknown mode.")

    @compliance.setter
    def compliance(self, value: float) -> None:
        """
        Sets the protection limit (compliance value).
        In VOLT mode, sets the current limit; in CURR mode, sets the voltage limit.

        Parameters
        ----------
        value : float
            Protection limit value.
        """
        mode = self.source_mode
        if mode == "VOLT":
            self.write(f":SENS:CURR:PROT {value}")
        elif mode == "CURR":
            self.write(f":SENS:VOLT:PROT {value}")
        else:
            raise ValueError("Unknown mode.")

    def configure_current_source(self, current: float, compliance: float) -> None:
        self.source_mode = "CURR"
        self.compliance = compliance
        self.current = current

    def configure_current_measure(self, nplc: float) -> None:
        self.write(f":SENS:CURR:NPLC {nplc}")
        self.write(":CONF:CURR")

    def configure_voltage_measure(self, nplc: float) -> None:
        self.write(f":SENS:VOLT:NPLC {nplc}")
        self.write(":CONF:VOLT")

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

    def read_meas(self) -> float:
        result: str = self.query(":READ?")
        return float(result)

    def measure_current(self) -> float:
        """
        Performs a current measurement.

        Returns
        -------
        float
            Measured current value.
        """
        self.write(":CONF:CURR")
        response = self.query(":READ?")
        return float(response)

    def output_on(self) -> None:
        """
        Turns on the device output.
        """
        self.write(":OUTP ON")

    def output_off(self) -> None:
        """
        Turns off the device output.
        """
        self.write(":OUTP OFF")


# Append to register the instrument class with its alias
Config().add_instrument_extension(("Model 2401", SM2401))
