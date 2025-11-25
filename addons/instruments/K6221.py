import time
from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from config import Config
from .SCPIInstrumentTemplate import SCPIInstrumentTemplate


class K6221(SCPIInstrumentTemplate):
    """
    K6221 Class
    ============
    Minimal SCPI wrapper for Keithley 6221 (622x) current source.

    Focus:
      - Set / query DC source current.
      - Set / query voltage compliance.
      - Control source range (fixed / auto).
      - Control output state and triax connections (OLOW, inner shield).
      - Basic waveform configuration helper (for 6221 wave functions).
    """

    def __init__(self, scpi_info: SCPI_Info, **kwargs) -> None:
        super().__init__(
            scpi_info=scpi_info,
            port=scpi_info.port,
            baud_rate=scpi_info.baud_rate,
            read_termination="\n",
            write_termination="\n",
            timeout=5000,
            backend="@py",
            encoding="latin-1",
        )
        self.connect()

        # Reset to known state (*RST or SYST:PRES are both valid; base class
        # usually maps reset() to *RST).
        self.reset()

        # Disable beeper: SYSTem:BEEPer:STATe <b> (ON/OFF) :contentReference[oaicite:5]{index=5}
        self.disable_beep()

        self.init_properties()

    # -------------------------------------------------------------------------
    # Basic helpers
    # -------------------------------------------------------------------------

    def disable_beep(self) -> None:
        """Disable the front-panel beeper (SCPI: SYSTem:BEEPer:STATe OFF)."""
        self.write("SYST:BEEPer:STATe OFF")

    def init_properties(self) -> None:
        """
        Register properties for any GUI / higher-level abstraction using
        property_info (same pattern as your SM2401 class).
        """
        self.properties_list: List[property_info] = [
            property_info(
                "Current (A)",
                float,
                lambda: self.current,
                lambda x: setattr(self, "current", x),
            ),
            property_info(
                "Compliance (V)",
                float,
                lambda: self.compliance,
                lambda x: setattr(self, "compliance", x),
            ),
            property_info(
                "Source Range (A)",
                float,
                lambda: self.source_range,
                lambda x: setattr(self, "source_range", x),
            ),
            property_info(
                "Source Autorange",
                bool,
                lambda: self.source_autorange,
                lambda x: setattr(self, "source_autorange", x),
            ),
            property_info(
                "Output Enabled",
                bool,
                lambda: self.output_enabled,
                lambda x: setattr(self, "output_enabled", x),
            ),
            property_info(
                "Output Low to Earth",
                bool,
                lambda: self.output_low_to_earth,
                lambda x: setattr(self, "output_low_to_earth", x),
            ),
            property_info(
                "Triax Inner Shield",
                str,
                lambda: self.triax_inner_shield,
                lambda x: setattr(self, "triax_inner_shield", x),
            ),
        ]

    # -------------------------------------------------------------------------
    # Source current and compliance (SOURce:CURRent...) :contentReference[oaicite:6]{index=6}
    # -------------------------------------------------------------------------

    @property
    def current(self) -> float:
        """
        Programmed output current in amperes.

        SCPI:
          - Set:  SOURce:CURRent <n>
          - Get:  SOURce:CURRent?
        Valid range: -105e-3 to +105e-3 A.
        """
        return float(self.query("SOUR:CURR?"))

    @current.setter
    def current(self, value: float) -> None:
        self.write(f"SOUR:CURR {value}")

    @property
    def compliance(self) -> float:
        """
        Voltage compliance in volts.

        SCPI:
          - Set:  SOURce:CURRent:COMPliance <NRf>
          - Get:  SOURce:CURRent:COMPliance? :contentReference[oaicite:7]{index=7}
        Valid range: 0.1 to 105 V.
        """
        return float(self.query("SOUR:CURR:COMP?"))

    @compliance.setter
    def compliance(self, value: float) -> None:
        self.write(f"SOUR:CURR:COMP {value}")

    # -------------------------------------------------------------------------
    # Range control (SOURce:CURRent:RANGe / :AUTO) :contentReference[oaicite:8]{index=8}
    # -------------------------------------------------------------------------

    @property
    def source_range(self) -> float:
        """
        Fixed source range in amperes.

        SCPI:
          - Set:  SOURce:CURRent:RANGe <n>
          - Get:  SOURce:CURRent:RANGe?
        """
        return float(self.query("SOUR:CURR:RANG?"))

    @source_range.setter
    def source_range(self, value: float) -> None:
        # Using explicit fixed range also implies autorange OFF.
        self.write(f"SOUR:CURR:RANG {value}")
        self.write("SOUR:CURR:RANG:AUTO OFF")

    @property
    def source_autorange(self) -> bool:
        """
        Source autorange state.

        SCPI:
          - Set:  SOURce:CURRent:RANGe:AUTO <b>
          - Get:  SOURce:CURRent:RANGe:AUTO? :contentReference[oaicite:9]{index=9}
        """
        resp = self.query("SOUR:CURR:RANG:AUTO?")
        # Instrument returns 1/0 or ON/OFF; normalize to bool.
        return resp.strip().upper() in ("1", "ON")

    @source_autorange.setter
    def source_autorange(self, enable: bool) -> None:
        state = "ON" if enable else "OFF"
        self.write(f"SOUR:CURR:RANG:AUTO {state}")

    # -------------------------------------------------------------------------
    # Output control (OUTPut...) :contentReference[oaicite:10]{index=10}
    # -------------------------------------------------------------------------

    @property
    def output_enabled(self) -> bool:
        """
        Output ON/OFF state.

        SCPI:
          - Set:  OUTPut[:STATe] <b>
          - Get:  OUTPut[:STATe]?  (returns 0/1)
        """
        resp = self.query("OUTP:STAT?")
        return resp.strip().upper() in ("1", "ON")

    @output_enabled.setter
    def output_enabled(self, enable: bool) -> None:
        state = "ON" if enable else "OFF"
        # Both "OUTP ON/OFF" and "OUTP:STATe <b>" are legal; use explicit form.
        self.write(f"OUTP:STAT {state}")
        self.opc()

    def output_on(self, wait_rise: bool = True) -> None:
        """Turn output ON and optionally wait a small rise time."""
        self.output_enabled = True
        if wait_rise:
            time.sleep(5e-3)

    def output_off(self) -> None:
        """Turn output OFF."""
        self.output_enabled = False

    # -------------------------------------------------------------------------
    # Triax / output-low configuration (OUTPUT:LTEarth, OUTPUT:ISHield) :contentReference[oaicite:11]{index=11}
    # -------------------------------------------------------------------------

    @property
    def output_low_to_earth(self) -> bool:
        """
        Whether output low (OLOW) is tied to earth ground.

        SCPI:
          - Set:  OUTPut:LTEarth <b>   (ON = OLOW to earth, OFF = OLOW floating)
          - Get:  OUTPut:LTEarth?
        """
        resp = self.query("OUTP:LTEAR?")
        return resp.strip().upper() in ("1", "ON")

    @output_low_to_earth.setter
    def output_low_to_earth(self, connect: bool) -> None:
        state = "ON" if connect else "OFF"
        self.write(f"OUTP:LTEAR {state}")

    @property
    def triax_inner_shield(self) -> str:
        """
        Triax inner shield connection.

        SCPI:
          - Set:  OUTPut:ISHield <name>
                   <name> = OLOW (inner shield to output low)
                            GUARd (inner shield to guarded cable) :contentReference[oaicite:12]{index=12}
          - Get:  OUTPut:ISHield?
        Returns 'OLOW' or 'GUARD'.
        """
        return self.query("OUTP:ISH?").strip().upper()

    @triax_inner_shield.setter
    def triax_inner_shield(self, value: str) -> None:
        value = value.upper()
        if value not in ("OLOW", "GUARD"):
            raise ValueError("triax_inner_shield must be 'OLOW' or 'GUARD'.")
        self.write(f"OUTP:ISH {value}")

    # -------------------------------------------------------------------------
    # Convenience: configure DC current source
    # -------------------------------------------------------------------------

    def configure_current_source(
        self,
        current: float,
        compliance: float | None = None,
        autorange: bool | None = None,
    ) -> None:
        """
        Convenience helper to set DC current, compliance, and range behavior.

        Parameters
        ----------
        current : float
            Output current in amperes.
        compliance : float, optional
            Voltage compliance in volts. If None, leaves existing setting.
        autorange : bool, optional
            If True, enable autorange; if False, leave on present range with
            autorange OFF; if None, leave unchanged.
        """
        if compliance is not None:
            self.compliance = compliance
        if autorange is not None:
            self.source_autorange = autorange
        self.current = current

    # -------------------------------------------------------------------------
    # Waveform helpers (6221 only) – basic sine setup/start/stop
    # SOUR:WAVE:FUNC, :AMPL, :FREQ, :OFFS, :ARM, etc. 
    # -------------------------------------------------------------------------

    def configure_sine_wave(
        self,
        amplitude: float,
        frequency: float,
        offset: float = 0.0,
        range_mode: str = "BEST",
    ) -> None:
        """
        Configure a basic sine wave on the 6221 (waveform only, does not start it).

        SCPI (6221 only):
          - SOUR:WAVE:FUNC SIN
          - SOUR:WAVE:AMPL <NRf>
          - SOUR:WAVE:FREQ <NRf>
          - SOUR:WAVE:OFFS <NRf>
          - SOUR:WAVE:RANG <name>   (BEST or FIXed) :contentReference[oaicite:14]{index=14}
        """
        range_mode = range_mode.upper()
        if range_mode not in ("BEST", "FIXED"):
            raise ValueError("range_mode must be 'BEST' or 'FIXED'.")

        self.write("SOUR:WAVE:FUNC SIN")
        self.write(f"SOUR:WAVE:AMPL {amplitude}")
        self.write(f"SOUR:WAVE:FREQ {frequency}")
        self.write(f"SOUR:WAVE:OFFS {offset}")
        self.write(f"SOUR:WAVE:RANG {range_mode}")

    def arm_waveform(self) -> None:
        """
        Arm the currently configured waveform.

        SCPI:
          - SOUR:WAVE:ARM
        """
        self.write("SOUR:WAVE:ARM")

    def start_waveform(self) -> None:
        """
        Start the currently armed waveform.

        Depending on setup, this may involve INIT/trigger, but at minimum we
        must ensure output is ON and waveform is armed.
        """
        self.output_on()
        self.arm_waveform()
        # In many use cases, the waveform starts on trigger; here we just arm.

    def abort_waveform(self) -> None:
        """
        Abort any running sweep/Delta/waveform and stop sourcing.

        SCPI:
          - SOUR:SWEep:ABORt   (also exits Delta / Differential Conductance) :contentReference[oaicite:15]{index=15}
        """
        self.write("SOUR:SWE:ABOR")
        self.output_off()


# Register instrument with your Config system
Config().add_instrument_extension(("Model 6221", K6221))
Config().add_instrument_extension(("Model 6220", K6221))
