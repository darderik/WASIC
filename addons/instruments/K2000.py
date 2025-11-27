from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List, Optional, Literal
from config import Config
from easy_scpi import helper_methods
from .SCPIInstrumentTemplate import SCPIInstrumentTemplate

class K2000(SCPIInstrumentTemplate):
    """Keithley 2000 multimeter helper.

    Note: measurement is now a two-step model: configure_* then measure_*.
    The measure_* methods no longer send :CONF commands on every call; they
    just trigger/read based on the existing configuration.
    Global settings:
      - nplc: applies integration time to all relevant functions.
      - autozero: controls automatic zero.
      - filter_enabled / filter_type / filter_count: digital averaging filter
        applied to all supported functions.
    """

    def __init__(self, scpi_info: SCPI_Info, **kwargs) -> None:
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
            scpi_info=scpi_info,
            baud_rate=curBaudRate,
            read_termination="\n",
            write_termination="\n",
            timeout=5000,
            backend="@py",
        )
        self.connect()
        self.rst()  # Reset to known state
        self.cls()  # Clear any error conditions
        self.init_properties()
        self.disable_beep()

    def disable_beep(self) -> None:
        """
        Disables the beep sound.
        """
        self.write(":SYST:BEEP:STAT OFF")

    def enable_beep(self) -> None:
        """
        Enables the beep sound.
        """
        self.write(":SYST:BEEP:STAT ON")

    def beep(self) -> None:
        """
        Trigger a single beep.
        """
        self.write(":SYST:BEEP")

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
            property_info(
                "NPLC",
                float,
                lambda: self.nplc,
                lambda x: setattr(self, "nplc", x),
            ),
            property_info(
                "Autozero",
                bool,
                lambda: self.autozero,
                lambda x: setattr(self, "autozero", x),
            ),
        ]

    @property
    def autorange(self):
        """
        Returns the auto range setting for DC voltage measurement.
        """
        resp = self.query(":SENS:VOLT:DC:RANGE:AUTO?")
        return helper_methods.val_to_bool(resp)

    @autorange.setter
    def autorange(self, value):  # Accepts ON OFF or boolean
        """
        Sets the auto range for DC voltage measurement.
        Accepts boolean or string equivalents ('ON'/'OFF','1'/'0','true'/'false').
        """
        state = "ON" if helper_methods.val_to_bool(value) else "OFF"
        self.write(f":SENS:VOLT:DC:RANGE:AUTO {state}")

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
        If value < 0 the instrument is set to auto range.
        """
        if value is None:
            raise ValueError("range_dc requires a numeric value or negative for auto range")
        try:
            v = float(value)
        except Exception:
            raise ValueError("range_dc requires a numeric value")

        if v < 0:
            # Auto range
            self.write(":SENS:VOLT:DC:RANG:AUTO ON")
        else:
            self.write(f":SENS:VOLT:DC:RANG {v}")

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

    # --- Global integration time (NPLC) ---
    @property
    def nplc(self) -> float:
        """Get the integration time (NPLC) for the primary DC voltage function.

        This is used as a reference; setter applies the same NPLC to
        VOLT:DC/AC, CURR:DC/AC, RES, and FRES where supported.
        """
        try:
            return float(self.query(":SENS:VOLT:DC:NPLC?"))
        except Exception:
            return 1.0

    @nplc.setter
    def nplc(self, value: float) -> None:
        """Set NPLC for all relevant sensing functions.

        Applies to VOLT:DC, VOLT:AC, CURR:DC, CURR:AC, RES, FRES.
        """
        if value <= 0:
            raise ValueError("NPLC must be positive")
        functions = [
            "VOLT:DC",
            "VOLT:AC",
            "CURR:DC",
            "CURR:AC",
            "RES",
            "FRES",
        ]
        for func in functions:
            try:
                self.write(f":SENS:{func}:NPLC {value}")
            except Exception:
                # Some functions may not be available depending on mode/options
                continue

    # --- Global digital filter configuration ---
    @property
    def filter_enabled(self) -> bool:
        """Return True if the averaging filter is enabled for DC voltage.

        Used as a representative; setter applies to all functions.
        """
        try:
            resp = self.query(":SENS:VOLT:DC:AVER:STAT?")
        except Exception:
            return False
        return helper_methods.val_to_bool(resp)

    @filter_enabled.setter
    def filter_enabled(self, value: bool) -> None:
        state = "ON" if helper_methods.val_to_bool(value) else "OFF"
        functions = ["VOLT:DC", "VOLT:AC", "CURR:DC", "CURR:AC", "RES", "FRES", "TEMP"]
        for func in functions:
            try:
                self.write(f":SENS:{func}:AVER:STAT {state}")
            except Exception:
                continue

    @property
    def filter_type(self) -> str:
        """Get digital filter type ("REP" or "MOV") for DC voltage.

        Setter applies chosen type across all functions.
        """
        try:
            resp = self.query(":SENS:VOLT:DC:AVER:TCON?")
            return resp.strip().upper()
        except Exception:
            return "MOV"

    @filter_type.setter
    def filter_type(self, mode: str) -> None:
        mode = mode.upper()
        if mode not in ("REP", "MOV"):
            raise ValueError("filter_type must be 'REP' or 'MOV'")
        functions = ["VOLT:DC", "VOLT:AC", "CURR:DC", "CURR:AC", "RES", "FRES", "TEMP"]
        for func in functions:
            try:
                self.write(f":SENS:{func}:AVER:TCON {mode}")
            except Exception:
                continue

    @property
    def filter_count(self) -> int:
        """Get averaging filter count for DC voltage."""
        try:
            return int(float(self.query(":SENS:VOLT:DC:AVER:COUN?") or 0))
        except Exception:
            return 10

    @filter_count.setter
    def filter_count(self, count: int) -> None:
        if not 1 <= int(count) <= 100:
            raise ValueError("filter_count must be between 1 and 100")
        functions = ["VOLT:DC", "VOLT:AC", "CURR:DC", "CURR:AC", "RES", "FRES", "TEMP"]
        for func in functions:
            try:
                self.write(f":SENS:{func}:AVER:COUN {int(count)}")
            except Exception:
                continue

    # --- Autozero ---
    @property
    def autozero(self) -> bool:
        """Return True if autozero is enabled.

        Maps to :SYST:AZER:STAT? (ON/OFF or 1/0 depending on firmware).
        """
        try:
            resp = self.query(":SYST:AZER:STAT?")
        except Exception:
            return False
        return helper_methods.val_to_bool(resp)

    @autozero.setter
    def autozero(self, value: bool) -> None:
        """Enable or disable autozero.

        True -> ON, False -> OFF.
        """
        state = "ON" if helper_methods.val_to_bool(value) else "OFF"
        self.write(f":SYST:AZER:STAT {state}")

    def read_measurement(self) -> List[float]:
        """Trigger a reading using current configuration and return parsed values."""
        curRead: str = self.query(":READ?")
        return [float(x) for x in curRead.split(",") if x.strip()]

    # --- Configuration helpers (no per-call NPLC) ---
    def configure_voltage_dc(self, range: Optional[float] = None) -> None:
        """Configure DC voltage function.

        range < 0 -> autorange; nplc sets integration time if provided.
        """
        self.write(":CONF:VOLT:DC")
        if range is not None:
            if range < 0:
                self.write(":SENS:VOLT:DC:RANG:AUTO ON")
            else:
                self.write(f":SENS:VOLT:DC:RANG {range}")

    def configure_voltage_ac(self, range: Optional[float] = None) -> None:
        self.write(":CONF:VOLT:AC")
        if range is not None:
            if range < 0:
                self.write(":SENS:VOLT:AC:RANG:AUTO ON")
            else:
                self.write(f":SENS:VOLT:AC:RANG {range}")

    def configure_current_dc(self, range: Optional[float] = None) -> None:
        self.write(":CONF:CURR:DC")
        if range is not None:
            if range < 0:
                self.write(":SENS:CURR:DC:RANG:AUTO ON")
            else:
                self.write(f":SENS:CURR:DC:RANG {range}")

    def configure_current_ac(self, range: Optional[float] = None) -> None:
        self.write(":CONF:CURR:AC")
        if range is not None:
            if range < 0:
                self.write(":SENS:CURR:AC:RANG:AUTO ON")
            else:
                self.write(f":SENS:CURR:AC:RANG {range}")

    def configure_resistance_2w(self, range: Optional[float] = None) -> None:
        self.write(":CONF:RES")
        if range is not None:
            if range < 0:
                self.write(":SENS:RES:RANG:AUTO ON")
            else:
                self.write(f":SENS:RES:RANG {range}")

    def configure_resistance_4w(self, range: Optional[float] = None) -> None:
        self.write(":CONF:FRES")
        if range is not None:
            if range < 0:
                self.write(":SENS:FRES:RANG:AUTO ON")
            else:
                self.write(f":SENS:FRES:RANG {range}")
    # --- Measurement helpers (assume already configured) ---
    def measure_voltage_dc(self) -> List[float]:
        """Read DC voltage using current configuration.

        Call configure_voltage_dc once before a loop of measurements.
        """
        return self.read_measurement()

    def measure_voltage_ac(self) -> List[float]:
        return self.read_measurement()

    def measure_current_dc(self) -> List[float]:
        return self.read_measurement()

    def measure_current_ac(self) -> List[float]:
        return self.read_measurement()

    def measure_resistance_2w(self) -> List[float]:
        return self.read_measurement()

    def measure_resistance_4w(self) -> List[float]:
        return self.read_measurement()

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

    # Advanced configuration and control methods
    
    def set_display_text(self, text: str) -> None:
        """
        Set custom text on the instrument display.
        
        Parameters
        ----------
        text : str
            Text to display (max 12 characters for top line, 20 for bottom).
        """
        if len(text) > 12:
            raise ValueError("Display text must be 12 characters or less")
        self.write(f':DISP:TEXT:DATA "{text}"')
        self.write(":DISP:TEXT:STAT ON")

    def clear_display_text(self) -> None:
        """Clear custom text from display and return to normal operation."""
        self.write(":DISP:TEXT:STAT OFF")

    def set_filter(self, function: str, enable: bool = True, filter_type: str = "MOV", count: int = 10) -> None:
        """
        Configure digital filter for specified measurement function.
        
        Parameters
        ----------
        function : str
            Measurement function ("VOLT:DC", "CURR:DC", "RES", "FRES", etc.)
        enable : bool
            Enable or disable filter
        filter_type : str
            Filter type ("MOV" for moving average, "REP" for repeating)
        count : int
            Number of readings to filter (1-100)
        """
        if not 1 <= count <= 100:
            raise ValueError("Filter count must be between 1 and 100")
        
        if enable:
            self.write(f":SENS:{function}:AVER:TCON {filter_type}")
            self.write(f":SENS:{function}:AVER:COUN {count}")
            self.write(f":SENS:{function}:AVER:STAT ON")
        else:
            self.write(f":SENS:{function}:AVER:STAT OFF")

    def configure_trigger_delay(self, delay: float) -> None:
        """
        Set trigger delay.
        
        Parameters
        ----------
        delay : float
            Delay in seconds (0 to 999.999)
        """
        if not 0 <= delay <= 999.999:
            raise ValueError("Trigger delay must be between 0 and 999.999 seconds")
        self.write(f":TRIG:DEL {delay}")

    def configure_sample_count(self, count: int) -> None:
        """
        Set number of samples per trigger.
        
        Parameters
        ----------
        count : int
            Number of samples (1 to 50000)
        """
        if not 1 <= count <= 50000:
            raise ValueError("Sample count must be between 1 and 50000")
        self.write(f":SAMP:COUN {count}")

    def initiate_measurement(self) -> None:
        """Initiate a measurement sequence."""
        self.write(":INIT")

    def abort_measurement(self) -> None:
        """Abort the current measurement sequence."""
        self.write(":ABOR")

    def fetch_data(self) -> List[float]:
        """
        Fetch measurement data from instrument memory.
        
        Returns
        -------
        List[float]
            List of measurement values
        """
        response = self.query(":FETC?")
        # Parse comma-separated values
        values = [float(x.strip()) for x in response.split(',')]
        return values

    def get_error(self) -> tuple[int, str]:
        """
        Get the next error from the error queue.
        
        Returns
        -------
        tuple[int, str]
            Error code and error message
        """
        response = self.query(":SYST:ERR?")
        parts = response.strip().split(',', 1)
        error_code = int(parts[0])
        error_message = parts[1].strip('"') if len(parts) > 1 else ""
        return error_code, error_message

    def clear_error_queue(self) -> None:
        """Clear all errors from the error queue."""
        while True:
            error_code, _ = self.get_error()
            if error_code == 0:  # No error
                break

    def save_setup(self, location: int) -> None:
        """
        Save current instrument setup to specified memory location.
        
        Parameters
        ----------
        location : int
            Memory location (0-9)
        """
        if not 0 <= location <= 9:
            raise ValueError("Setup location must be between 0 and 9")
        self.write(f":*SAV {location}")

    def recall_setup(self, location: int) -> None:
        """
        Recall instrument setup from specified memory location.
        
        Parameters
        ----------
        location : int
            Memory location (0-9)
        """
        if not 0 <= location <= 9:
            raise ValueError("Setup location must be between 0 and 9")
        self.write(f":*RCL {location}")

    def set_reference_value(self, value: float) -> None:
        """
        Set reference value for null function.
        
        Parameters
        ----------
        value : float
            Reference value
        """
        self.write(f":CALC:NULL:OFFS {value}")

    def enable_null_function(self, enable: bool = True) -> None:
        """
        Enable or disable null function (relative measurement).
        
        Parameters
        ----------
        enable : bool
            Enable or disable null function
        """
        if enable:
            self.write(":CALC:FUNC NULL")
            self.write(":CALC:STAT ON")
        else:
            self.write(":CALC:STAT OFF")

    def set_limit_testing(self, lower_limit: float, upper_limit: float, enable: bool = True) -> None:
        """
        Configure limit testing.
        
        Parameters
        ----------
        lower_limit : float
            Lower limit value
        upper_limit : float
            Upper limit value
        enable : bool
            Enable limit testing
        """
        self.write(f":CALC:LIM:LOW {lower_limit}")
        self.write(f":CALC:LIM:UPP {upper_limit}")
        if enable:
            self.write(":CALC:FUNC LIM")
            self.write(":CALC:STAT ON")
        else:
            self.write(":CALC:STAT OFF")

    def get_limit_test_result(self) -> str:
        """
        Get limit test result.
        
        Returns
        -------
        str
            "PASS", "FAIL", or "NONE"
        """
        return self.query(":CALC:LIM:FAIL?").strip()

    # Data logging and statistics methods
    
    def get_statistics(self) -> dict:
        """
        Get measurement statistics.
        
        Returns
        -------
        dict
            Dictionary containing count, mean, stddev, min, max, pk-pk
        """
        stats = {}
        try:
            stats['count'] = int(self.query(":CALC:AVER:COUN?"))
            stats['mean'] = float(self.query(":CALC:AVER?"))
            stats['stddev'] = float(self.query(":CALC:AVER:SDEV?"))
            stats['min'] = float(self.query(":CALC:AVER:MIN?"))
            stats['max'] = float(self.query(":CALC:AVER:MAX?"))
            stats['pk_pk'] = stats['max'] - stats['min']
        except:
            # If statistics not available, return empty dict
            pass
        return stats

    def clear_statistics(self) -> None:
        """Clear measurement statistics."""
        self.write(":CALC:AVER:CLE")


# Mandatory append to register instrument class with its alias
Config().add_instrument_extension(("Model 2000", K2000))
