from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from pyvisa import constants
import time
import threading
import numpy as np
from .common_utilities import strip_header
from config import Config


class TBS1052C(Instrument):
    def __init__(self, scpi_info: SCPI_Info):
        if scpi_info.baud_rate != 0:
            super().__init__(
                port=scpi_info.port,
                baud_rate=scpi_info.baud_rate,
                read_termination="\n",
                write_termination="\n",
                timeout=20000,
                stop_bits=constants.StopBits.one,
                parity=constants.Parity.none,
            )
        else:
            super().__init__(
                backend=Config().get("custom_backend", ""),
                timeout=5000,
                read_termination="\n",
                write_termination="\n",
                port=scpi_info.port,
            )

        self._super_lock = threading.RLock()
        self.connect()
        self.write("HEADER OFF")

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = [
            property_info(
                "Time Scale (s/div)",
                float,
                lambda: self.time_scale,
                lambda v: setattr(self, "time_scale", v),
            ),
            property_info(
                "Volt/Div CH1 (V/div)",
                float,
                lambda: self.volt_scale_ch1,
                lambda v: setattr(self, "volt_scale_ch1", v),
            ),
            property_info(
                "Volt/Div CH2 (V/div)",
                float,
                lambda: self.volt_scale_ch2,
                lambda v: setattr(self, "volt_scale_ch2", v),
            ),
        ]

    @property
    def time_scale(self) -> float:
        return float(self.query("HOR:MAI:SCA?"))

    @time_scale.setter
    def time_scale(self, value: float):
        self.write(f"HOR:MAI:SCA {value}")

    @property
    def volt_scale_ch1(self) -> float:
        return float(self.query("CH1:SCA?"))

    @volt_scale_ch1.setter
    def volt_scale_ch1(self, value: float):
        self.write(f"CH1:SCA {value}")

    @property
    def volt_scale_ch2(self) -> float:
        return float(self.query("CH2:SCA?"))

    @volt_scale_ch2.setter
    def volt_scale_ch2(self, value: float):
        self.write(f"CH2:SCA {value}")

    def get_id(self) -> str:
        """Instrument identification via *IDN?"""
        return self.query("*IDN?")

    def reset(self):
        """Restore factory settings with *RST"""
        self.write("*RST")

    def run(self):
        """Start continuous acquisition (ACQUIRE:STATE ON)"""
        self.write("ACQ:STATE ON")

    def horizontal_resolution(self, value: float):
        self.write(f"HORizontal:RESOlution {value}")

    def stop(self):
        """Stop acquisition (ACQUIRE:STATE OFF)"""
        self.write("ACQ:STATE OFF")

    def single(self):
        """Single-shot acquisition (ACQUIRE:STOPAfter SEQuence + STATE RUN)"""
        self.write("ACQ:STOPA SEQ")
        self.write("ACQ:STATE RUN")

    def set_channel_display(self, channel: int, on: bool):
        """Turn CHx display ON/OFF (SELECT:CHx ON/OFF)"""
        state = "ON" if on else "OFF"
        self.write(f"SEL:CH{channel} {state}")

    def set_probe_attenuation(self, channel: int, factor: float):
        """Set probe attenuation factor for CHx (CHx:PROBe:GAIN)"""
        self.write(f"CH{channel}:PRO {factor}")

    def measure_voltage(self, channel: int = 1) -> float:
        """Measure RMS voltage with MEASUrement:IMMed commands"""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYPe VRMS")
        return float(self.query("MEASU:IMM:VAL?"))

    def measure_frequency(self, channel: int = 1) -> float:
        """Measure frequency with MEASUrement:IMMed commands"""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYPe FREQuency")
        return float(self.query("MEASU:IMM:VAL?"))

    def measure_peak_to_peak(self, channel: int = 1) -> float:
        """Measure peak-to-peak voltage with MEASUrement:IMMed commands"""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYPe PK2PK")
        return float(self.query("MEASU:IMM:VAL?"))

    def configure_edge_trigger(
        self,
        source: str = "CH1",
        level: float = 3.3,
        slope: str = "RISE",
        mode: str = "AUTO",
    ):
        """Configure EDGE trigger (TRIGger:MAIN commands)"""
        self.write("TRIG:MAI:TYP EDGE")
        self.write(f"TRIG:MAI:EDGE:SOU {source}")
        self.write(f"TRIG:MAI:EDGE:SLO {slope}")
        self.write(f"TRIG:MAI:LEV {level}")
        self.write(f"TRIG:MAI:MODE {mode}")
        self.write("ACQ:STOPA SEQ")

    def wait_for_acquisition_complete(self, timeout_sec: float = 5.0) -> bool:
        """Wait for acquisition to complete by querying ACQ:STATE?"""
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.query("ACQ:STATE?") == "0":
                return True
            time.sleep(0.1)
        return False

    def get_waveform(self, channel: int = 1, points: int = 2500):
        """
        Retrieve waveform:
         1. Set DATa:ENCdg, DATa:WIDth, DATa:STARt/STOP
         2. Query WFMP:* for xinc, ymult, yoff, yzero
         3. CURV? + read_raw + strip header
        """
        with self._super_lock:
            self.write("DAT:ENC RPB")
            self.write("DAT:WID 1")
            self.write("DAT:STAR 1")
            self.write(f"DAT:STOP {points}")

            ymult = float(self.query("WFMP:YMU?"))
            yoff = float(self.query("WFMP:YOF?"))
            yzero = float(self.query("WFMP:YZE?"))
            xinc = float(self.query("WFMP:XIN?"))
            xzero = float(self.query("WFMP:XZE?"))

            self.write("CURV?")
            time.sleep(0.1)
            raw = self.read_raw()
            data = np.frombuffer(strip_header(raw), dtype=np.uint8)

        voltages = (data - yoff) * ymult + yzero
        times = np.arange(len(voltages)) * xinc + xzero
        return [times.tolist(), voltages.tolist()]

    # Override query/write to avoid threading conflicts
    def query(self, msg: str) -> str:
        with self._super_lock:
            r = super().query(msg)
            time.sleep(0.01)
        return r

    def write(self, msg: str):
        with self._super_lock:
            super().write(msg)
            time.sleep(0.01)


# Register driver
Config().add_instrument_extension(("TBS 1052C,", TBS1052C))
