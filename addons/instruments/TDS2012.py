from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List, Optional
from easy_scpi import Property as Scpi_Property
from config import Config
from pyvisa import constants
from .common_utilities import strip_header
import numpy as np
import time
import threading


class TDS2012(Instrument):

    def __init__(
        self,
        scpi_info: SCPI_Info,
    ):
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
            # USBMTC Resource, tds2012C
            super().__init__(
                backend=Config().get("custom_backend", ""),
                timeout=5000,
                read_termination="\n",
                write_termination="\n",
                port=scpi_info.port,
            )

        self.__superlock = threading.RLock()
        self.connect()
        self.write("HEADER OFF")

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = [
            property_info(
                "Time Scale",
                float,
                lambda: self.time_scale,
                lambda x: setattr(self, "time_scale", x),
            ),
            property_info(
                "Volt/Div CH1",
                float,
                lambda: self.volt_scale_ch1,
                lambda x: setattr(self, "volt_scale_ch1", x),
            ),
            property_info(
                "Volt/Div CH2",
                float,
                lambda: self.volt_scale_ch2,
                lambda x: setattr(self, "volt_scale_ch2", x),
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
        """Returns the identification string of the oscilloscope."""
        return self.query("*IDN?")

    def reset(self):
        """Performs a factory reset of the oscilloscope."""
        self.write("*RST")

    def run(self):
        """Starts continuous acquisition."""
        self.write("ACQ:STATE ON")

    def stop(self):
        """Stops acquisition."""
        self.write("ACQ:STATE OFF")

    def single(self):
        """Starts single-shot acquisition."""
        self.write("ACQ:STOPA SEQ")
        self.write("ACQ:STATE RUN")

    def set_channel_display(self, channel: int, on: bool):
        """Turns channel display on or off.

        Args:
            channel (int): Channel number (1 or 2).
            on (bool): True to enable display, False to hide.
        """
        state = "ON" if on else "OFF"
        self.write(f"SEL:CH{channel} {state}")

    def set_probe_attenuation(self, channel: int, factor: float):
        """Sets the probe attenuation factor.

        Args:
            channel (int): Channel number.
            factor (float): Probe attenuation value (e.g., 1, 10).
        """
        self.write(f"CH{channel}:PRO {factor}")

    def measure_voltage(self, channel: int = 1) -> float:
        """Measures the RMS voltage on the selected channel."""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYP VRMS")
        return float(self.query("MEASU:IMM:VAL?"))

    def measure_frequency(self, channel: int = 1) -> float:
        """Measures frequency of the signal on the specified channel."""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYP FREQUENCY")
        return float(self.query("MEASU:IMM:VAL?"))

    def measure_peak_to_peak(self, channel: int = 1) -> float:
        """Measures peak-to-peak voltage."""
        self.write(f"MEASU:IMM:SOU CH{channel}")
        self.write("MEASU:IMM:TYP PK2PK")
        return float(self.query("MEASU:IMM:VAL?"))

    def configure_edge_trigger(
        self,
        source: str = "CH1",
        level: float = 1.0,
        slope: str = "RISE",
        mode: str = "AUTO",
    ):
        """Configures an edge trigger on a given channel.

        Args:
            source (str): Trigger source, e.g., "CH1".
            level (float): Trigger level in volts.
            slope (str): Trigger slope, "RISE" or "FALL".
        """
        self.write("TRIG:MAI:TYP EDGE")
        self.write(f"TRIG:MAI:EDGE:SOU {source}")
        self.write(f"TRIG:MAI:EDGE:SLO {slope}")
        self.write(f"TRIG:MAI:LEV {level}")
        self.write(f"TRIG:MAI:MODE {mode}")
        self.write("ACQ:STOPA SEQ")

    def wait_for_acquisition_complete(self, timeout_sec=5.0):
        """Waits until acquisition is complete or times out."""
        start_time = time.time()
        while True:
            if self.query("ACQ:STATE?") == "0":
                return True
            if time.time() - start_time > timeout_sec:
                return False
            time.sleep(0.1)

    def trigger_run(self):
        with self.__superlock:
            self.write("ACQ:STATE RUN")

    def horizontal_scale(self, value: float):
        """Sets the horizontal scale.

        Args:
            value (float): Horizontal scale in seconds/division.
        """
        self.write(f"HOR:MAI:SCA {value}")

    def horizontal_position(self, value: float):
        """Sets the horizontal position.

        Args:
            value (float): Horizontal position in seconds.
        """
        self.write(f"HOR:MAI:POS {value}")

    def get_waveform(self, channel: int = 1):
        """Retrieves the waveform from the specified channel.

        Returns:
            list: [time_values, voltage_values]
        """
        with self.__superlock:
            self.write("DAT:ENC RPB")  # RPBinary = unsigned, MSB first
            self.write("DAT:WID 1")  # 1 byte per point
            self.write("DAT:STAR 1")
            self.write("DAT:STOP 2500")

            ymult_str = self.query("WFMP:YMU?")
            ymult = float(ymult_str)
            yoff_str = self.query("WFMP:YOF?")
            yoff = float(yoff_str)
            yzero_str = self.query("WFMP:YZE?")
            yzero = float(yzero_str)
            xinc_str = self.query("WFMP:XIN?")
            xinc = float(xinc_str)
            xzero_str = self.query("WFMP:XZE?")
            xzero = float(xzero_str)

            self.write("CURV?")
            time.sleep(0.1)
            raw_data = self.read_raw()
            wave_bytes = strip_header(raw_data)
            digital_wave = np.frombuffer(wave_bytes, dtype=np.uint8)
            self.write("\n")
        voltages = (digital_wave - yoff) * ymult + yzero
        times = np.arange(len(voltages)) * xinc + xzero

        return [times.tolist(), voltages.tolist()]


class TDS2012C(TDS2012):
    def __init__(self, scpi_info: SCPI_Info):
        scpi_info.baud_rate = 0
        super().__init__(scpi_info)
        self.write("ACQUIRE:MODE SAMPLE")

    def set_acquisition_mode(self, mode: str):
        """Sets the acquisition mode.

        Args:
            mode (str): Acquisition mode, e.g., "SAMPLE", "PEAKDETECT", "AVERAGE".
        """
        self.write(f"ACQUIRE:MODE {mode}")

    def vertical_position(self, channel: int, value: float):
        """Sets the vertical position of the specified channel.

        Args:
            channel (int): Channel number (1 or 2).
            value (float): Vertical position in volts.
        """
        self.write(f"CH{channel}:POS {value}")

    def set_average_count(self, count: int):
        """Sets the number of averages for averaging mode.

        Args:
            count (int): Number of averages (e.g., 2, 4, 8, 16, etc.).
        """
        self.write(f"ACQUIRE:NUMAVG {count}")

    def enable_extended_acquisition(self, enable: bool):
        """Enables or disables extended acquisition.

        Args:
            enable (bool): True to enable, False to disable.
        """
        state = "ON" if enable else "OFF"
        self.write(f"ACQUIRE:EXTENDED {state}")


# Register the driver
# Comma for identifying..
Config().add_instrument_extension(("TDS 2012,", TDS2012))
Config().add_instrument_extension(("TDS 2012C,", TDS2012C))
