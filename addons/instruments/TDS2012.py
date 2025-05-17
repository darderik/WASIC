from easy_scpi import Instrument
from instruments import SCPI_Info
from pyvisa import constants
import threading
import numpy as np
from typing import Union, Sequence
import time
from typing import List, Tuple, Any
from config import Config

delay: float = 0.1  # seconds


class TDS2012(Instrument):
    def __init__(self, scpi_info: SCPI_Info, backend: str = "@py"):
        if scpi_info.baud_rate != 0:
            super().__init__(
                backend=backend,
                port=scpi_info.port,
                baud_rate=scpi_info.baud_rate,
                read_termination="\n",
                write_termination="\n",
                timeout=50000,
                stop_bits=constants.StopBits.one,
                parity=constants.Parity.none,
                encoding="latin-1",
            )
        else:
            # UsbMTC instrument
            super().__init__(
                port=scpi_info.port,
                backend=backend,
                read_termination="\n",
                write_termination="\n",
                timeout=50000,
                encoding="latin-1",
            )
        self.connect()
        self._childlock = threading.RLock()
        self.reset()
        self.write("HEADer OFF")
        self.write("ACQuire:STATE OFF")
        self.write("*CLS")

    def initialize_waveform_settings(
        self,
        points: int = 2500,
        source: int = 1,
        encoding: str = "RPBinary",
        width: int = 1,
    ):
        self.write(f"DATa:SOUrce CH{source}")
        self.write(f"DATa:ENCdg {encoding}")
        self.write(f"DATa:WIDth {width}")
        self.write("DATa:STARt 1")
        self.write(f"DATa:STOP {points}")
        self.write(f"SELect:CH{source} ON")

    def reset(self):
        self.write("*RST")
        self.write("HEADer OFF")

    @property
    def time_scale(self) -> float:
        return float(self.query("HORizontal:MAIn:SCAle?"))

    @time_scale.setter
    def time_scale(self, value: float):
        self.write(f"HORizontal:MAIn:SCAle {value}")

    def trigger_config(
        self,
        source: int = 1,
        slope: str = "FALL",
        level: float = 0.5,
        mode: str = "NORMal",
    ):
        self.write(f"TRIGger:MAIn:EDGE:SOUrce CH{source}")
        self.write(f"TRIGger:MAIn:EDGE:SLOpe {slope}")
        self.write(f"TRIGger:MAIn:LEVel {level}")
        self.write(f"TRIGger:MAIn:MODe {mode}")

    def acquire_toggle(self, state: bool = True):
        self.write("ACQuire:STATE ON" if state else "ACQuire:STATE OFF")
        self.query("acquire:state?")

    def single(self):
        self.write("ACQuire:STOPAfter SEQuence")
        self.write("ACQuire:STATE ON")
        self.query("ACQUIRE:STATE?")

    def _parse_wfmoutpre(self, response: str) -> dict[str, Any]:
        fields = response.strip().split(";")
        return {
            "BYT_NR": int(fields[0]),
            "BIT_NR": int(fields[1]),
            "ENCODING": fields[2],
            "BN_FMT": fields[3],
            "BYT_OR": fields[4],
            "NR_PT": int(fields[5]),
            "WFID": fields[6],
            "PT_FMT": fields[7],
            "XINCR": float(fields[8]),
            "PT_OFF": int(fields[9]),
            "XZERO": float(fields[10]),
            "XUNIT": fields[11].strip('"'),
            "YMULT": float(fields[12]),
            "YZERO": float(fields[13]),
            "YOFF": float(fields[14]),
            "YUNIT": fields[15].strip('"'),
        }

    def get_waveform(
        self,
        channel: int = 1,
        points: int = 2500,
        encoding: str = "binary",
    ) -> Tuple[np.ndarray, np.ndarray]:
        preamble_raw = self.query("WFMPre?")
        preamble = self._parse_wfmoutpre(preamble_raw)
        ymult, yoff, yzero = map(
            float, (preamble["YMULT"], preamble["YOFF"], preamble["YZERO"])
        )
        xinc, xzero = map(float, (preamble["XINCR"], preamble["XZERO"]))
        if encoding.lower() == "binary":
            data = self.query_binary_values(
                "CURVe?", datatype="B", data_points=points, is_big_endian=True
            )
        else:
            data = self.query_ascii_values("CURVe?", separator=",", container=list)
        self.acquire_toggle(False)
        unscaled = np.array(data, dtype="double")
        scaled = (unscaled - yoff) * ymult + yzero
        timebase = np.arange(len(data)) * xinc + xzero
        return timebase, scaled

    def vertical_scale(self, channel: int, scale: float):
        self.write(f"CH{channel}:SCALE {scale}")

    def vertical_position(self, channel: int, position: float):
        self.write(f"CH{channel}:POSITION {position}")

    def horizontal_position(self, position: float):
        self.write(f"HORizontal:MAIn:POSition {position}")

    def opc(self):
        resp = self.query("*OPC?")
        return resp

    def wait(self):
        self.write("*WAI")


class TDS2012C(TDS2012):
    def __init__(
        self, scpi_info: SCPI_Info, backend: str = Config().get("custom_backend", "")
    ):
        super().__init__(scpi_info, backend)

    def reset(self):
        self.write("*RST")
        self.write("HEADer OFF")
        self.write("ACQuire:STATE OFF")
        self.write("*CLS")


# Append to register the instrument class with its alias
Config().add_instrument_extension(("TDS 2012,", TDS2012))
Config().add_instrument_extension(("TDS 2012C,", TDS2012C))
