from easy_scpi import Instrument
from instruments import SCPI_Info
from pyvisa import constants
import threading
import numpy as np
from typing import Union, Sequence
from .common_utilities import strip_header
import time
from typing import List, Tuple, Any
from config import Config


class TBS1052C(Instrument):
    """Driver for Tektronix TBS1052C oscilloscopes, using full SCPI command names."""

    def __init__(
        self,
        scpi_info: SCPI_Info,
        backend: str = Config().get("custom_backend", ""),
        **kwargs,
    ):
        # Always use the VISA/USB backend for this model
        super().__init__(
            backend=backend,
            port=scpi_info.port,
            read_termination="\n",
            write_termination="\n",
            timeout=50000,
            encoding="latin-1",
            **kwargs,
        )
        self.connect()
        self.__childlock = threading.RLock()

        # Disable response headers
        self.write("*RST")
        self.write("HEADER OFF")
        self.write("ACQUIRE:STATE OFF")
        self.write("*cls")  # clear ESR
        self.query("*OPC?")
        # Overridden methods

    def initialize_waveform_settings(
        self,
        points: int = 2500,
        source: int = 1,
        encoding: str = "RPBinary",
        width: int = 1,
    ):
        """Set up default waveform data parameters."""
        self.write(f"DATA:SOURCE CH{source}")
        # Choose positive‐polarity binary encoding (RPBinary) :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}
        self.write(f"DATA:ENCODING {encoding}")
        self.write(f"DATA:WIDTH {width}")
        self.write("DATA:START 1")
        self.write(f"DATA:STOP {points}")
        self.write(f"SELECT:CH{source} ON")

    def reset(self):
        """Factory reset and turn headers off."""
        self.write("*RST")
        self.write("HEADER OFF")

    @property
    def time_scale(self) -> float:
        """Query horizontal time scale (seconds/div): HORIZONTAL:MAIN:SCALE? :contentReference[oaicite:2]{index=2}:contentReference[oaicite:3]{index=3}"""
        return float(self.query("HORIZONTAL:MAIN:SCALE?"))

    @time_scale.setter
    def time_scale(self, value: float):
        """Set horizontal time scale (seconds/div): HORIZONTAL:MAIN:SCALE <value>"""
        self.write(f"HORIZONTAL:MAIN:SCALE {value}")

    def trigger_config(
        self,
        source: int = 1,
        slope: str = "FALL",
        level: float = 0.5,
        mode: str = "normal",
    ):
        """Configure trigger settings."""
        self.write(f"TRIGGER:A:EDGE:SOURCE CH{source}")
        self.write(f"TRIGGER:A:EDGE:SLOPE {slope}")
        self.write(f"TRIGGER:A:EDGE:LEVEL {level}")
        self.write(f"TRIGGER:A:MODE {mode}")

    def acquire_toggle(self, state: bool = True):
        """Toggle acquisition state."""
        if state:
            self.write("ACQUIRE:STATE ON")
        else:
            self.write("ACQUIRE:STATE OFF")

    def single(self):
        """Set oscilloscope to single acquisition mode."""
        self.write("ACQUIRE:STOPAFTER SEQUENCE")
        self.write("ACQUIRE:STATE ON")

    def _parse_wfmoutpre(self, response: str) -> dict[str, Any]:
        fields = response.strip().split(";")
        preamble = {
            "BYT_NR": int(fields[0]),
            "BIT_NR": int(fields[1]),
            "ENCODING": fields[2],
            "BN_FMT": fields[3],
            "BYT_OR": fields[4],
            "WFID": fields[5],
            "NR_PT": int(fields[6]),
            "PT_FMT": fields[7],
            "XUNIT": fields[8].strip('"'),
            "XINCR": float(fields[9]),
            "XZERO": float(fields[10]),
            "PT_OFF": int(fields[11]),
            "YUNIT": fields[12].strip('"'),
            "YMULT": float(fields[13]),
            "YOFF": float(fields[14]),
            "YZERO": float(fields[15]),
        }
        return preamble

    def get_waveform(
        self,
        channel: int = 1,
        points: int = 2500,
        encoding: str = "binary",
    ) -> Tuple[np.ndarray, np.ndarray]:
        # Make sure wave is displayed
        # We assume data is setup with encoding and points, on channel
        # Get preamble and use regex
        preamble_raw = self.query("WFMOutPre?")
        preamble = self._parse_wfmoutpre(preamble_raw)
        ymult = float(preamble["YMULT"])
        yoff = float(preamble["YOFF"])
        yzero = float(preamble["YZERO"])
        xinc = float(preamble["XINCR"])
        xzero = float(preamble["XZERO"])
        # Query curv
        if encoding.lower() == "binary":
            data = self.query_binary_values(
                "CURVE?",
                datatype="B",
                data_points=points,
                is_big_endian=True,
            )
        else:  # ASCII
            data = self.query_ascii_values(
                "CURVE?",
                separator=",",
                container=list,
            )
            # Create time array
        unscaled_wave = np.array(data, dtype="double")
        scaled_wave = (unscaled_wave - yoff) * ymult + yzero
        time_array = np.arange(len(data)) * xinc + xzero
        return time_array, scaled_wave

    def _parse_waveform(self, raw: bytes, encoding: str) -> np.ndarray:
        """
        Helper to extract just the curve payload from WAVFrm?.
        """
        if encoding.lower() == "binary":
            buf = strip_header(raw)
            return np.frombuffer(buf, dtype=np.uint8)
        else:
            text = raw.decode("ascii", errors="ignore").strip()
            payload = text.splitlines()[-1]
            return np.array([int(v) for v in payload.split(",") if v], dtype=int)

    # Helper methods
    def vertical_scale(self, channel: int, scale: float):
        """Set vertical scale (V/div) for a given channel."""
        self.write(f"CH{channel}:SCALE {scale}")

    def vertical_position(self, channel: int, position: float):
        """Set vertical position (V) for a given channel."""
        self.write(f"CH{channel}:POSITION {position}")

    def horizontal_position(self, position: float):
        """Set horizontal position (s) for the main timebase."""
        self.write(f"HORIZONTAL:MAIN:DELAY:TIME {position}")

    def opc(self):
        """Wait for operation complete."""
        self.query("*OPC?")

    def wait(self):
        """WAI Command. Process next command only after all previous commands are completed."""
        self.write("*WAI")


# Append to register the instrument class with its alias
Config().add_instrument_extension(("TBS1052C", TBS1052C))
