# TBS1052C.py
from typing import List, Tuple, Optional, Any
from pyvisa.constants import StopBits
from instruments import SCPI_Info, property_info
from config import Config
from .SCPIInstrumentTemplate import SCPIInstrumentTemplate
import time  # added for inter-command delays
from threading import RLock
import re  # added for WFMOutpre parsing

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
        "ACQuire": 0.2,
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
            timeout=kwargs.get("timeout", 10000),
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
        self._local_lock = RLock()

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
    def wait_acquire_complete(self, timeout: float = 10.0) -> bool:
        # Wait for acquisition to complete (ACQuire:STATE STOP)
        start_time = time.time()
        while True:
            state = str(self.query("ACQuire:STATE?")).strip().upper()
            if state == "0":
                return True
            if (time.time() - start_time) > timeout:
                return False
            time.sleep(0.1)
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
    def set_probe_attenuation(self, ch: int, attenuation: float) -> None:
        # e.g., 10 for a "10x" probe (attenuation = input/output)
        if attenuation == 0:
            raise ValueError("Attenuation must be non-zero.")
        self.write(f"{self._ch(ch)}:PRObe:GAIN {1/attenuation}")
    # ---------------- Horizontal / timebase ----------------
    def set_time_scale(self, sec_per_div: float) -> None:
        self.write(f"HORizontal:MAIn:SCAle {sec_per_div}")

    def get_time_scale(self) -> float:
        return float(self.query("HORizontal:MAIn:SCAle?"))

    def set_trigger_position_divs(self, divs: float) -> None:
        # Sets position of trigger within record in divisions
        self.write(f"HORizontal:TRIGger:POSition {divs}")


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
    def set_waveform_xzero(self, xzero) -> None:
        self.write(f"WFMInpre:XZEro {xzero}")
        
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
    def set_record_length(self, points: int = 0, auto:bool = False) -> None:
        if auto:
            self.write("HORizontal:RECOrdlength:AUTO 1")
            return
        else:
            self.write("HORizontal:RECOrdlength:AUTO 0")
        if points < 1000 or points > 20000:
            raise ValueError("Record length must be between 1000 and 1,000,000 points.")
        self.write(f"HORizontal:RECOrdlength {points}")
    
    def _read_preamble(self) -> dict:
        """
        Parser compatto per WFMOutPre? del TBS1000C (formato a lista con ordine fisso).
        Restituisce le chiavi legacy: NR_Pt, XINcr, XZEro, YMUlt, YOFf, YZEro,
        PT_Off, XUNit, YUNit + extra (BYT_NR, BIT_NR, ENCDG, BN_FMT, BYT_OR, WFID, PT_Fmt, NR_FRM, TCLK).
        """
        raw = self.query("WFMOutPre?") or ""
        # normalizza e splitta sui ';'
        parts = [p.strip() for p in re.sub(r'[\r\n]+', ' ', raw).lstrip(':').split(';')]

        def dequote(s: str) -> str:
            s = s.strip()
            return s[1:-1] if len(s) >= 2 and s[0] == s[-1] == '"' else s

        def num_or_str(s: str):
            s = dequote(s)
            s = re.sub(r'(?<=-)\s+(?=\d)', '', s)  # "- 1.0E-3" -> "-1.0E-3"
            try:
                return float(s)
            except ValueError:
                return s

        # ordine Tek TBS1000C (lista senza nomi):
        # 0:BYT_NR 1:BIT_NR 2:ENCDG 3:BN_FMT 4:BYT_OR 5:WFID 6:NR_PT 7:PT_FMT
        # 8:XUNIT 9:XINCR 10:XZERO 11:PT_OFF 12:YUNIT 13:YMULT 14:YOFF 15:YZERO 16:NR_FRM 17:TCLK
        m = {}
        try:
            m["BYT_NR"] = num_or_str(parts[0])
            m["BIT_NR"] = num_or_str(parts[1])
            m["ENCDG"]  = dequote(parts[2])
            m["BN_FMT"] = dequote(parts[3])
            m["BYT_OR"] = dequote(parts[4])
            m["WFID"]   = dequote(parts[5])
            m["NR_Pt"]  = int(num_or_str(parts[6]))
            m["PT_Fmt"] = dequote(parts[7])
            m["XUNit"]  = dequote(parts[8])
            m["XINcr"]  = float(num_or_str(parts[9]))
            m["XZEro"]  = float(num_or_str(parts[10]))
            m["PT_Off"] = int(num_or_str(parts[11]))  # sul TBS spesso resta 0
            m["YUNit"]  = dequote(parts[12])
            m["YMUlt"]  = float(num_or_str(parts[13]))
            m["YOFf"]   = float(num_or_str(parts[14]))
            m["YZEro"]  = float(num_or_str(parts[15]))
            m["NR_FRM"] = int(num_or_str(parts[16])) if len(parts) > 16 else None
            m["TCLK"]   = num_or_str(parts[17])       if len(parts) > 17 else None
        except Exception:
            pass  # cadrà nei fallback sotto se qualcosa manca

        # Fallback essenziali (solo se non presenti o parse fallito)
        q = lambda s: (self.query(s) or "").strip()
        if "NR_Pt" not in m or not isinstance(m.get("NR_Pt"), (int, float)):
            try: m["NR_Pt"] = int(float(q("WFMOutpre:NR_Pt?")))
            except: pass
        for k, scpi in [("XINcr","WFMOutpre:XINcr?"),
                        ("XZEro","WFMOutpre:XZEro?"),
                        ("YMUlt","WFMOutpre:YMUlt?"),
                        ("YOFf" ,"WFMOutpre:YOFf?"),
                        ("YZEro","WFMOutpre:YZEro?"),
                        ("PT_Off","WFMOutpre:PT_Off?"),
                        ("XUNit","WFMOutpre:XUNit?"),
                        ("YUNit","WFMOutpre:YUNit?")]:
            if k not in m or m[k] in ("", None):
                try:
                    v = q(scpi)
                    m[k] = float(v) if re.search(r'[0-9]', v) and k not in ("XUNit","YUNit") else dequote(v)
                except:
                    pass
        return m

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
                     start: int = 1,
                     stop: int = 1000,
                     source: str = "CH1",
                     width_bytes: int = 1,
                     binary: bool = True,
                     center_wavfrm = False,) -> Tuple[List[float], List[float], dict]:
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
        # Parsing from preamble dict
        xzero = pre["XZEro"]
        xincr = pre["XINcr"]
        n_expected = int(pre["NR_Pt"])
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
        t_first = xzero + (start - 1) * xincr
        time_s  = [t_first + i*xincr for i in range(len(codes))]


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
        with self._local_lock:
            super().write(msg)
            self._apply_delay(msg)


# Optional registration (match your framework's discovery)
Config().add_instrument_extension(("TBS1052C", TBS1052C))
