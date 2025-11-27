from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List, Optional
from config import Config
from pyvisa.constants import StopBits
from .SCPIInstrumentTemplate import SCPIInstrumentTemplate

class NV34420(SCPIInstrumentTemplate):
    """
    Keysight 34420A NanoVolt/Micro-Ohm (NV34420)
    ============================================
    SCPI wrapper for DC voltage (Ch1/Ch2, ratio, difference), 2W/4W resistance,
    NPLC, null, trigger, and filter controls.

    Manual highlights reflected here:
      - Channels via SENS1:/SENS2: for volts config
      - NPLC choices: 0.02|0.2|1|2|10|20|100|200
      - Ratio/Diff queries: MEAS:VOLT:DC:RATIO? / :DIFF?
      - Avoid digital filter in remote; analog filter limited to 1/10/100 mV & T/C
    """

    def __init__(self, scpi_info: SCPI_Info, **kwargs) -> None:
        super().__init__(
            scpi_info,
            timeout=kwargs.get("timeout", 1000),
            handshake=kwargs.get("handshake", True),
            write_termination="\n",
            read_termination="\n",
            backend="@py",
            encoding="latin-1",
            stop_bits=StopBits.two,  # 34420A ships RS-232 default 2 stop bits
        )
        self.connect(explicit_remote=1)

        # Quality-of-life defaults
        self.disable_beep()
        self.init_properties()

    # ---------------- Properties panel (for your UI) ----------------
    def init_properties(self) -> None:
        self.properties_list: List['property_info'] = [
            property_info("Voltage Range (Ch1)", float,
                          lambda: self.get_voltage_range(1),
                          lambda x: self.set_voltage_range(x, 1)),
            property_info("Voltage Range (Ch2)", float,
                          lambda: self.get_voltage_range(2),
                          lambda x: self.set_voltage_range(x, 2)),
            property_info("Integration Time (NPLC)", float,
                          self.get_nplc,
                          self.set_nplc),
            property_info("Resistance Range (4W)", float,
                          self.get_resistance_range,
                          self.set_resistance_range),
        ]

    # ---------------- Helpers ----------------
    def _sensesel(self, channel: int) -> str:
        if channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        return f"SENS{channel}:"

    def _validate_nplc(self, nplc: float) -> None:
        allowed = {0.02, 0.2, 1, 2, 10, 20, 100, 200}
        if nplc not in allowed:
            raise ValueError(f"nplc must be one of {sorted(allowed)}")

    # ---------------- Core/basic ----------------
    def disable_beep(self) -> None:
        # Manual lists SYS menu options; beeper cmd naming varies by family.
        # Keep your working form:
        self.write("SYSTem:BEEPer:STATe 0")

    # ---------------- Voltage config (per channel) ----------------
    def get_voltage_range(self, channel: int = 1) -> float:
        return float(self.query(f"{self._sensesel(channel)}VOLT:DC:RANG?"))

    def set_voltage_range(self, value: float, channel: int = 1) -> None:
        self.write(f"{self._sensesel(channel)}VOLT:DC:RANG {value}")

    def set_voltage_autorange(self, on: bool = True, channel: int = 1) -> None:
        self.write(f"{self._sensesel(channel)}VOLT:DC:RANG:AUTO {'ON' if on else 'OFF'}")

    def get_nplc(self) -> float:
        # NPLC is shared across functions; use VOLT as canonical
        return float(self.query("SENS:VOLT:DC:NPLC?"))

    def set_nplc(self, nplc: float) -> None:
        self._validate_nplc(nplc)
        # Set for relevant funcs
        self.write(f"SENS:VOLT:DC:NPLC {nplc}")
        self.write(f"SENS:FRES:NPLC {nplc}")
        self.write(f"SENS:TEMP:NPLC {nplc}")

    # ---------------- Resistance (4W primary) ----------------
    def get_resistance_range(self) -> float:
        return float(self.query("SENS:FRES:RANG?"))

    def set_resistance_range(self, value: float) -> None:
        self.write(f"SENS:FRES:RANG {value}")

    def set_resistance_autorange(self, on: bool = True) -> None:
        self.write(f"SENS:FRES:RANG:AUTO {'ON' if on else 'OFF'}")

    def set_offset_comp(self, on: bool = True) -> None:
        self.write(f"SENS:FRES:OCOMp {'ON' if on else 'OFF'}")

    def set_low_power_ohms(self, on: bool = False) -> None:
        # 4W only
        self.write(f"SENS:FRES:POW:LIM {'ON' if on else 'OFF'}")

    def set_voltage_limited_ohms(self, on: bool = False, limit_mV: Optional[float] = None) -> None:
        self.write(f"SENS:FRES:VOLT:LIM {'ON' if on else 'OFF'}")
        if on and limit_mV is not None:
            # allowed: 20 mV, 100 mV, 500 mV
            if limit_mV not in (20, 100, 500):
                raise ValueError("limit_mV must be 20, 100, or 500")
            self.write(f"SENS:FRES:VOLT:LIM:VAL {limit_mV/1000.0}")

    # ---------------- Filters (use cautiously in remote) ----------------
    def filters_off(self) -> None:
        self.write("INP:FILT:STAT OFF")  # digital & analog off (instrument interprets)
    def set_analog_filter(self, on: bool = False) -> None:
        # Analog filter (only 1/10/100 mV ranges & TC). Use sparingly for line noise.
        self.write(f"INP:FILT:STAT {'ON' if on else 'OFF'}")
        if on:
            self.write("INP:FILT:TYPE ANAlog")
    def set_digital_filter(self, mode: str = "OFF") -> None:
        # {OFF|FAST|MED|SLOW}; discouraged for remote per manual
        m = mode.upper()
        if m == "OFF":
            self.write("INP:FILT:STAT OFF")
        else:
            self.write("INP:FILT:STAT ON")
            self.write("INP:FILT:TYPE DIGital")
            self.write(f"INP:FILT:DIG:RESP { {'FAST':'FAST','MED':'MED','SLOW':'SLOW'}[m] }")

    # ---------------- Null (per channel/function) ----------------
    def set_voltage_null(self, channel: int, on: bool, value: Optional[float] = None) -> None:
        base = f"{self._sensesel(channel)}VOLT:DC:NULL"
        self.write(f"{base} {'ON' if on else 'OFF'}")
        if on and value is not None:
            self.write(f"{base} {value}")

    def set_resistance_null(self, on: bool, value: Optional[float] = None) -> None:
        base = "SENS:FRES:NULL"
        self.write(f"{base} {'ON' if on else 'OFF'}")
        if on and value is not None:
            self.write(f"{base} {value}")

    # ---------------- Triggering ----------------
    def trigger_configure(self, source: str = "IMM", delay: float = 0.0, count: int = 1) -> None:
        """
        source: 'IMM' | 'BUS' | 'EXT'
        delay: seconds
        count: triggers per reading sequence
        """
        src = source.upper()
        self.write(f"TRIG:SOUR {src}")
        self.write(f"TRIG:DEL {delay}")
        self.write(f"TRIG:COUN {count}")

    def set_sample_count(self, count: int = 1) -> None:
        # number of samples per trigger
        self.write(f"SAMP:COUN {count}")

    # ---------------- Measurements ----------------
    def read_measurement(self) -> List[float]:
        """
        Reads a measurement value.
        """
        curRead: str = self.query(":READ?")
        return [float(x) for x in curRead.split(",")]

    def measure_voltage(self, channel: int = 1, configure: bool = False, sample_count: int = 1) -> List[float]:
        if configure:
            # Use SENS commands instead of CONF to avoid resetting sample count
            self.write(f"{self._sensesel(channel)}FUNC 'VOLT:DC'")
        if sample_count > 1:
            self.set_sample_count(sample_count)
        return self.read_measurement()

    def measure_resistance_4w(self, configure: bool = True, sample_count: int = 1) -> List[float]:
        if configure:
            # Use SENS commands instead of CONF to avoid resetting sample count
            self.write("SENS:FUNC 'FRES'")
        if sample_count > 1:
            self.set_sample_count(sample_count)
        return self.read_measurement()

    def measure_ratio(self, sample_count: int = 1) -> List[float]:
        """Voltage ratio Ch1/Ch2."""
        # Use SENS commands instead of CONF to avoid resetting sample count
        self.write("SENS:FUNC 'VOLT:DC:RATIO'")
        if sample_count > 1:
            self.set_sample_count(sample_count)
        return self.read_measurement()

    def measure_difference(self, sample_count: int = 1) -> List[float]:
        """Voltage difference Ch1-Ch2 (uses channel nulls)."""
        # Use SENS commands instead of CONF to avoid resetting sample count
        self.write("SENS:FUNC 'VOLT:DC:DIFF'")
        if sample_count > 1:
            self.set_sample_count(sample_count)
        return self.read_measurement()

    def measure_voltage_with_params(self, channel: int = 1, range_val: Optional[float] = None, 
                                   nplc: Optional[float] = None, sample_count: int = 1) -> List[float]:
        """Measure voltage with optional range and NPLC settings."""
        # Set function
        self.write(f"{self._sensesel(channel)}FUNC 'VOLT:DC'")
        
        # Set range if provided
        if range_val is not None:
            if range_val < 0:
                self.write(f"{self._sensesel(channel)}VOLT:DC:RANG:AUTO ON")
            else:
                self.write(f"{self._sensesel(channel)}VOLT:DC:RANG {range_val}")
        
        # Set NPLC if provided
        if nplc is not None:
            self._validate_nplc(nplc)
            self.write(f"{self._sensesel(channel)}VOLT:DC:NPLC {nplc}")
        
        # Set sample count if > 1
        if sample_count > 1:
            self.set_sample_count(sample_count)
        
        return self.read_measurement()

    def measure_resistance_with_params(self, range_val: Optional[float] = None, 
                                      nplc: Optional[float] = None, sample_count: int = 1) -> List[float]:
        """Measure 4W resistance with optional range and NPLC settings."""
        # Set function
        self.write("SENS:FUNC 'FRES'")
        
        # Set range if provided
        if range_val is not None:
            if range_val < 0:
                self.write("SENS:FRES:RANG:AUTO ON")
            else:
                self.write(f"SENS:FRES:RANG {range_val}")
        
        # Set NPLC if provided
        if nplc is not None:
            self._validate_nplc(nplc)
            self.write(f"SENS:FRES:NPLC {nplc}")
        
        # Set sample count if > 1
        if sample_count > 1:
            self.set_sample_count(sample_count)
        
        return self.read_measurement()

    # ---------------- System / status ----------------
    def preset(self) -> None:
        self.write("SYST:PRESET")

# Register the instrument class with its alias
Config().add_instrument_extension(("34420A", NV34420))
