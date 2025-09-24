# TBS1052C.py
from typing import List, Tuple, Optional
from pyvisa.constants import StopBits
from instruments import SCPI_Info, property_info
from config import Config
from .SCPIInstrumentTemplate import SCPIInstrumentTemplate
import time  # added for inter-command delays


class TBS1052C(SCPIInstrumentTemplate):
    """
    Tektronix TBS1052C (TBS1000C series) Oscilloscope
    ==================================================
    Lightweight SCPI wrapper for common control and waveform I/O.

    Notes (command groups from the Programmer Manual):
      - Acquisition: ACQuire:STATE, :STOPAfter, :MODe, :NUMAVg  (Avg requires :MODe AVERage)
      - Channels: CH<x>:SCAle|VOLts, :COUPling, :BANdwidth, :POSition, :OFFSet, :INVert, :LABel, :PRObe:GAIN
      - Horizontal/timebase: HORizontal[:MAIn]:SCAle|SECdiv, :RECOrdlength, :TRIGger:POSition
      - Trigger (A): TRIGger:A:TYPe EDGE, :EDGE:SOUrce, :EDGE:SLOPe, :EDGE:COUPling, :LEVel[:CH<x>]
      - Measurement: MEASUrement:IMMed:TYPe/SOUrce1/VALue?
      - Waveform readback: DATa:SOUrce, DATa:STARt/STOP, DATa:WIDth, WFMOutpre?, CURVe?
      - All measurement methods return List[float] for consistency
    """

    # ---------------- Static (edit-in-code) timing configuration ----------------
    ENABLE_DELAYS: bool = True  # Toggle all extra delays globally
    DEFAULT_COMMAND_DELAY: float = 0.0  # Fallback delay if no command key matches
    COMMAND_DELAYS: dict[str, float] = {
        "ACQuire": 0.5,
        "HORizontal:MAIn:SCAle": 0.05,
        "HORizontal:RECOrdlength": 0.10,
        "HORizontal:TRIGger:POSition": 0.01,
        "HORizontal:POSition": 0.01,
        "HORIZONTAL:MAIN:DELAY:TIME": 0.01,
        "HORIZONTAL:MAIN:DELAY:STATE": 0.01,
        "DATa:SOUrce": 0.01,
        "DATa:STARt": 0.01,
        "DATa:STOP": 0.01,
        "WFMOutpre:BYT_Nr": 0.01,
        "WFMOutpre:ENCdg": 0.01,
        "TRIGger:A:TYPe": 0.05,
        "TRIGger:A:EDGE:SOUrce": 0.01,
        "TRIGger:A:EDGE:SLOPe": 0.01,
        "TRIGger:A:EDGE:COUPling": 0.01,
        "MEASUrement:IMMed:TYPe": 0.01,
        "AUTOSet": 0.20,
        "FACtory": 0.50,
    }

    def __init__(self, scpi_info: SCPI_Info, **kwargs) -> None:
        super().__init__(
            scpi_info,
            timeout=kwargs.get("timeout", 5000),
            backend=kwargs.get("backend", "@py"),
            encoding=kwargs.get("encoding", "latin-1"),
            handshake=False,
            write_termination="\n",
            read_termination="\n",)
        # (Delays are static; no runtime kwargs customization to keep caller generic.)
        try:
            self.connect()
            self.reset()
            time.sleep(0.5)
        except Exception:
            pass
        self.init_properties()

    # ---------------- Properties panel (optional for your UI) ----------------
    def init_properties(self) -> None:
        self.properties_list: List['property_info'] = [
            property_info("CH1 Scale (V/div)", float,
                          lambda: self.get_channel_scale(1),
                          lambda v: self.set_channel_scale(1, v)),
            property_info("CH2 Scale (V/div)", float,
                          lambda: self.get_channel_scale(2),
                          lambda v: self.set_channel_scale(2, v)),
            property_info("Timebase (s/div)", float,
                          self.get_time_scale,
                          self.set_time_scale),
            property_info("Acquire Mode", str,
                          self.get_acquire_mode,
                          self.set_acquire_mode),
        ]

    # ---------------- Helpers ----------------
    def _ch(self, ch: int) -> str:
        if ch not in (1, 2):
            raise ValueError("Channel must be 1 or 2 for TBS1052C.")
        return f"CH{ch}"

    def read_measurement(self) -> List[float]:
        """
        Reads a measurement value.
        """
        curRead: str = self.query(":READ?")
        return [float(x) for x in curRead.split(",")]

    # ---------------- Core / basics ----------------
    def autoset(self) -> None:
        # AUTOset EXECute
        self.write("AUTOSet EXECute")

    def run(self) -> None:
        # ACQuire:STATE RUN
        self.write("ACQuire:STATE RUN")

    def stop(self) -> None:
        # ACQuire:STATE STOP
        self.write("ACQuire:STATE STOP")

    def single(self) -> None:
        # CRITICAL unknown behaviour without delay
        # ACQuire:STOPAfter SEQuence;:ACQuire:STATE RUN
        self.write("ACQuire:STOPAfter SEQuence")
        self.run()
    def set_stop_after(self, mode: str = "RUNSTop") -> None:
        m = mode.upper()
        if m not in ("RUNSTOP", "SEQUENCE", "SEQuence", "RUNSTop"):
            raise ValueError("mode must be RUNSTop or SEQuence")
        self.write(f"ACQuire:STOPAfter {m}")

    def opc_wait(self) -> None:
        # Convenience wrapper for *OPC? via parent opc()
        self.opc()

    # ---------------- Acquisition ----------------
    def set_acquire_mode(self, mode: str) -> None:
        m = mode.upper()
        # {SAMple|PEAKdetect|HIRes|AVErage}
        valid = {"SAMPLE", "PEAKDETECT", "HIRES", "AVERAGE"}
        if m not in valid:
            raise ValueError("mode must be one of SAMPLE|PEAKDETECT|HIRES|AVERAGE")
        self.write(f"ACQuire:MODe { {'SAMPLE':'SAMple','PEAKDETECT':'PEAKdetect','HIRES':'HIRes','AVERAGE':'AVErage'}[m] }")

    def get_acquire_mode(self) -> str:
        return str(self.query("ACQuire:MODe?")).strip()

    def set_averages(self, n: int) -> None:
        # Range 2..512 in powers of two
        if n not in (2, 4, 8, 16, 32, 64, 128, 256, 512):
            raise ValueError("Averages must be a power-of-two between 2 and 512.")
        self.write(f"ACQuire:NUMAVg {n}")

    def get_averages(self) -> int:
        return int(float(self.query("ACQuire:NUMAVg?")))

    # ---------------- Channels ----------------
    def set_channel_enable(self, ch: int, on: bool = True) -> None:
        # SELECT:CH<x> {ON|OFF}
        self.write(f"SELect:{self._ch(ch)} {'ON' if on else 'OFF'}")

    def set_channel_scale(self, ch: int, vdiv: float) -> None:
        self.write(f"{self._ch(ch)}:SCAle {vdiv}")

    def get_channel_scale(self, ch: int) -> float:
        return float(self.query(f"{self._ch(ch)}:SCAle?"))

    def set_channel_position(self, ch: int, divisions: float) -> None:
        self.write(f"{self._ch(ch)}:POSition {divisions}")

    def set_channel_offset(self, ch: int, volts: float) -> None:
        self.write(f"{self._ch(ch)}:OFFSet {volts}")

    def set_channel_coupling(self, ch: int, mode: str) -> None:
        m = mode.upper()
        if m not in ("AC", "DC"):
            raise ValueError("Coupling must be 'AC' or 'DC'.")
        self.write(f"{self._ch(ch)}:COUPling {m}")

    def set_channel_bandwidth(self, ch: int, value: str = "FULL") -> None:
        """
        value: 'FULL' (no limit), 'TWENTY' (20 MHz), or a numeric string/or float -> instrument rounds to available.
        """
        if isinstance(value, (int, float)):
            self.write(f"{self._ch(ch)}:BANdwidth {float(value)}")
        else:
            v = value.upper()
            if v not in ("FULL", "TWENTY"):
                raise ValueError("Bandwidth must be FULL, TWENTY, or numeric Hz.")
            self.write(f"{self._ch(ch)}:BANdwidth {'FULl' if v=='FULL' else 'TWEnty'}")

    def set_channel_invert(self, ch: int, on: bool) -> None:
        self.write(f"{self._ch(ch)}:INVert {'ON' if on else 'OFF'}")

    def set_channel_label(self, ch: int, text: str) -> None:
        # Limited to 30 chars per manual
        self.write(f'{self._ch(ch)}:LABel "{text[:30]}"')

    def set_probe_gain(self, ch: int, gain: float) -> None:
        # e.g., 0.1 for a "10x" probe (gain = output/input)
        self.write(f"{self._ch(ch)}:PRObe:GAIN {gain}")

    # ---------------- Horizontal / timebase ----------------
    def set_time_scale(self, sec_per_div: float) -> None:
        self.write(f"HORizontal:MAIn:SCAle {sec_per_div}")

    def get_time_scale(self) -> float:
        return float(self.query("HORizontal:MAIn:SCAle?"))

    def set_trigger_position_divs(self, divs: float) -> None:
        # Sets position of trigger within record in divisions
        self.write(f"HORizontal:TRIGger:POSition {divs}")

    def set_record_length(self, points: int) -> None:
        self.write(f"HORizontal:RECOrdlength {int(points)}")

    def get_record_length(self) -> int:
        return int(float(self.query("HORizontal:RECOrdlength?")))
    
    def enable_horizontal_delay(self, on:bool) -> None:
        self.write(f"HORIZONTAL:MAIN:DELAY:STATE {'ON' if on else 'OFF'}")    
    def set_horizontal_delay(self, position:float) -> None:
        self.write(f"HORIZONTAL:MAIN:DELAY:TIME {position}")
    def get_horizontal_delay(self) -> float:
        return float(self.query("HORIZONTAL:MAIN:DELAY:TIME?"))
    


    def set_horizontal_position(self, position: float) -> None:
        self.write(f"HORizontal:POSition {position}")
    def get_horizontal_position(self) -> float:
        return float(self.query("HORizontal:POSition?"))
    # ---------------- Trigger (Edge, A) ----------------
    def trig_edge(self, source: str = "CH1", slope: str = "RIS", coupling: str = "DC") -> None:
        # Type EDGE
        self.write("TRIGger:A:TYPe EDGE")
        self.write(f"TRIGger:A:EDGE:SOUrce {source.upper()}")
        self.write(f"TRIGger:A:EDGE:SLOPe { {'RIS':'RISe','RISE':'RISe','FALL':'FALL','FAL':'FALL'}[slope.upper()] }")
        self.write(f"TRIGger:A:EDGE:COUPling {coupling.upper()}")

    def trig_level(self, level_volts: float, ch: Optional[int] = None) -> None:
        # Either generic A:LEVel (applies to source) or per-channel
        if ch is None:
            self.write(f"TRIGger:A:LEVel {level_volts}")
        else:
            self.write(f"TRIGger:A:LEVel:{self._ch(ch)} {level_volts}")

    # ---------------- Measurements ----------------
    def measure_immediate(self, mtype: str, source1: str = "CH1", source2: Optional[str] = None) -> List[float]:
        """
        Quick single-shot measurement using IMMed slot.
        mtype examples: FREQuency, PERiod, MEAN, PK2Pk, MAXimum, MINImum, RMS, etc.
        """
        self.write(f"MEASUrement:IMMed:TYPe {mtype}")
        self.write(f"MEASUrement:IMMed:SOUrce1 {source1}")
        if source2:
            self.write(f"MEASUrement:IMMed:SOUrce2 {source2}")
        val = float(self.query("MEASUrement:IMMed:VALue?"))
        return [val]

    # ---------------- Waveform I/O ----------------
    def _prepare_waveform_read(self, source: str, start: int, stop: int, width_bytes: int = 1, binary: bool = True) -> None:
        # Select source (CH1|CH2|MATH|REF1|REF2)
        self.write(f"DATa:SOUrce {source.upper()}")
        # Start/Stop indices (1-based, inclusive)
        self.write(f"DATa:STARt {int(start)}")
        self.write(f"DATa:STOP {int(stop)}")
        # Width 1 or 2 (2 yields 16-bit with low byte zero on this series)
        self.write(f"DATa:WIDth {1 if width_bytes != 2 else 2}")
        # Encoding via WFMOutpre (instrument also supports HEADer ON/OFF globally)
        self.write(f"WFMOutpre:BYT_Nr {1 if width_bytes != 2 else 2}")
        self.write(f"WFMOutpre:ENCdg {'BIN' if binary else 'ASCii'}")

    def _read_preamble(self) -> dict:
        # Query needed preamble items for scaling arrays
        # We request individually to keep parsing simple and robust.
        pre = {}
        pre["NR_Pt"] = int(float(self.query("WFMOutpre:NR_Pt?")))
        pre["XINcr"] = float(self.query("WFMOutpre:XINcr?"))
        pre["XZEro"] = float(self.query("WFMOutpre:XZEro?"))
        pre["YMUlt"] = float(self.query("WFMOutpre:YMUlt?"))
        pre["YOFf"] = float(self.query("WFMOutpre:YOFf?"))
        pre["YZEro"] = float(self.query("WFMOutpre:YZEro?"))
        # Optional units (nice to return to caller)
        try:
            pre["XUNit"] = str(self.query("WFMOutpre:XUNit?")).strip()
            pre["YUNit"] = str(self.query("WFMOutpre:YUNit?")).strip()
        except Exception:
            pre["XUNit"] = "s"
            pre["YUNit"] = "V"
        return pre

    def _parse_curve_ascii(self, resp: str) -> List[int]:
        # Response like ":CURVE 61,62,..." or just "61,62,..."
        s = resp.strip()
        if s.upper().startswith(":CURVE"):
            s = s.split(" ", 1)[1] if " " in s else ""
        if not s:
            return []
        return [int(x) for x in s.split(",") if x]

    def _parse_curve_binary(self, data) -> List[int]:
        """
        Parse binary data returned by query_binary_values.
        """
        return list(data) if hasattr(data, '__iter__') else [data]

    def get_waveform(self,
                     source: str = "CH1",
                     start: Optional[int] = None,
                     stop: Optional[int] = None,
                     width_bytes: int = 1,
                     binary: bool = True) -> Tuple[List[float], List[float], dict]:
        """
        Download a waveform and return (time_s, volts, preamble_dict).
        - source: CH1|CH2|MATH|REF1|REF2
        - start/stop: 1-based inclusive indices (defaults to full record)
        - width_bytes: 1 or 2 (this series' 16-bit mode pads LSB=0 per manual)
        - binary: use definite-length block for speed
        """
        # Make sure we have a stable, recent acquisition for current setup
        # Caller can also single() + opc_wait() if desired.
        rec = self.get_record_length()
        s = 1 if start is None else int(start)
        e = rec if stop is None else int(stop)

        self._prepare_waveform_read(source, s, e, width_bytes, binary)
        if self.ENABLE_DELAYS:
            time.sleep(0.02)
        pre = self._read_preamble()
        n_expected = pre["NR_Pt"]
        if self.ENABLE_DELAYS:
            time.sleep(0.01)
        # Fetch curve
        if binary:
            codes = self.query_binary_values("CURVe?", datatype='B')
            codes = list(codes)  # Convert to list
        else:
            asc = self.query("CURVe?")
            codes = self._parse_curve_ascii(asc)

        # Guard against partial transfers
        if n_expected and len(codes) != n_expected:
            # Some firmwares may include trailing LF or short transfers; just clamp
            codes = codes[:n_expected]

        # Build time axis
        t0 = pre["XZEro"]
        dt = pre["XINcr"]
        time_s = [t0 + i * dt for i in range(len(codes))]

        # Convert sample codes to volts: V = (code - YOFf) * YMUlt + yzer
        yoff = pre["YOFf"]
        ymul = pre["YMUlt"]
        yzer = pre["YZEro"]

        volts = [(c - yoff) * ymul + yzer for c in codes]

        return time_s, volts, pre

    # ---------------- Convenience combos ----------------
    def setup_simple_edge(self, ch: int = 1, vdiv: float = 0.5, time_div: float = 1e-3,
                          trig_level: float = 0.0, slope: str = "RISE") -> None:
        """Convenience: enable CH, set scales, edge trigger, and run."""
        self.set_channel_enable(ch, True)
        self.set_channel_scale(ch, vdiv)
        self.set_time_scale(time_div)
        self.trig_edge(source=self._ch(ch), slope=slope)
        self.trig_level(trig_level, ch=ch)
        self.run()

    # ---------------- System ----------------
    def factory(self) -> None:
        """Factory defaults (does not change comms or calibration)."""
        self.write("FACtory")

    def _apply_delay(self, msg: str) -> None:
        if not self.ENABLE_DELAYS:
            return
        # Simple substring match (fast). First matching key wins.
        for key, delay in self.COMMAND_DELAYS.items():
            if key in msg:
                if delay > 0:
                    time.sleep(delay)
                return
        # Fallback default
        if self.DEFAULT_COMMAND_DELAY > 0:
            time.sleep(self.DEFAULT_COMMAND_DELAY)

    def write(self, msg: str) -> None:  # override to inject delays
        super().write(msg)
        self._apply_delay(msg)


# Optional registration (match your framework's discovery)
Config().add_instrument_extension(("TBS1052C", TBS1052C))
