"""PyMeasure-style driver for the Rohde & Schwarz ZNB43 VNA.

SCPI reference: R&S ZNB User Manual 1173.9163.02, version 74:
https://www.rohde-schwarz.com/webhelp/ZNB_HTML_UserManual_en/Content/welcome.htm

Construction and addon discovery send no commands. Measurement channels are
independent of physical RF ports; use ``ch_1`` or ``channel(number)`` to access
their settings. Additional channels must exist on the analyzer or be created
with ``define_trace`` before configuring them.
"""

from math import isfinite
from numbers import Integral
from threading import RLock

from pymeasure.instruments import Channel, Instrument, SCPIMixin
from pymeasure.instruments.validators import strict_discrete_set, strict_range

from instruments.properties import property_info
from wasic_api import InstrumentSpec


def _integer_range(value, bounds):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("Expected an integer")
    return strict_range(value, bounds)


def _finite_value(value, _):
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def _scpi_string(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError("Trace name must be a nonempty string without control characters")
    # Channel.insert_id uses format_map; preserve literal braces in trace names.
    escaped = value.replace("'", "''").replace("{", "{{").replace("}", "}}")
    return "'" + escaped + "'"


class ZNB43Channel(Channel):
    """One logical measurement channel of a ZNB43 (not an RF port)."""

    start_frequency = Channel.control(
        "SENS{ch}:FREQ:STAR?", "SENS{ch}:FREQ:STAR %.12g",
        """Start frequency in Hz (100 kHz to 43.5 GHz).""",
        validator=strict_range, values=(100e3, 43.5e9),
    )
    stop_frequency = Channel.control(
        "SENS{ch}:FREQ:STOP?", "SENS{ch}:FREQ:STOP %.12g",
        """Stop frequency in Hz (100 kHz to 43.5 GHz).""",
        validator=strict_range, values=(100e3, 43.5e9),
    )
    center_frequency = Channel.control(
        "SENS{ch}:FREQ:CENT?", "SENS{ch}:FREQ:CENT %.12g",
        """Center frequency in Hz (100 kHz to 43.5 GHz).""",
        validator=strict_range, values=(100e3, 43.5e9),
    )
    frequency_span = Channel.control(
        "SENS{ch}:FREQ:SPAN?", "SENS{ch}:FREQ:SPAN %.12g",
        """Frequency span in Hz; the instrument validates the resulting edges.""",
        validator=strict_range, values=(0, 43.5e9 - 100e3),
    )
    sweep_points = Channel.control(
        "SENS{ch}:SWE:POIN?", "SENS{ch}:SWE:POIN %d",
        """Number of points per sweep, from 1 to 100001.""",
        validator=_integer_range, values=(1, 100001), cast=int,
    )
    sweep_type = Channel.control(
        "SENS{ch}:SWE:TYPE?", "SENS{ch}:SWE:TYPE %s",
        """Sweep type: LIN, LOG, SEGM, POW, CW or POIN.""",
        validator=strict_discrete_set,
        values=("LIN", "LOG", "SEGM", "POW", "CW", "POIN"), cast=str,
    )
    if_bandwidth = Channel.control(
        "SENS{ch}:BAND?", "SENS{ch}:BAND %.12g",
        """IF bandwidth in Hz (1 Hz to 10 MHz; above 1 MHz requires K17).

        The analyzer rounds to supported bandwidths. Read back the applied value.
        """,
        validator=strict_range, values=(1, 10e6),
    )
    source_power = Channel.control(
        "SOUR{ch}:POW?", "SOUR{ch}:POW %.12g",
        """Channel base power in dBm. Limits depend on frequency and options;
        the analyzer validates the supported range.
        """,
        validator=_finite_value,
    )
    averaging_enabled = Channel.control(
        "SENS{ch}:AVER:STAT?", "SENS{ch}:AVER:STAT %d",
        """Whether sweep averaging is enabled.""",
        validator=strict_discrete_set, values={False: 0, True: 1}, map_values=True,
    )
    average_count = Channel.control(
        "SENS{ch}:AVER:COUN?", "SENS{ch}:AVER:COUN %d",
        """Averaging factor (1 to 1000), independent of sweep_count.""",
        validator=_integer_range, values=(1, 1000), cast=int,
    )
    sweep_count = Channel.control(
        "SENS{ch}:SWE:COUN?", "SENS{ch}:SWE:COUN %d",
        """Sweeps per single acquisition cycle (1 to 100000).""",
        validator=_integer_range, values=(1, 100000), cast=int,
    )
    continuous_enabled = Channel.control(
        "INIT{ch}:CONT?", "INIT{ch}:CONT %d",
        """Whether this channel sweeps continuously.""",
        validator=strict_discrete_set, values={False: 0, True: 1}, map_values=True,
    )
    trigger_source = Channel.control(
        "TRIG{ch}:SOUR?", "TRIG{ch}:SOUR %s",
        """Trigger source: IMM, EXT, MAN or MULT.""",
        validator=strict_discrete_set, values=("IMM", "EXT", "MAN", "MULT"), cast=str,
    )
    trace_format = Channel.control(
        "CALC{ch}:FORM?", "CALC{ch}:FORM %s",
        """Display format of the active trace; complex readout ignores it.""",
        validator=strict_discrete_set,
        values=("MLIN", "MLOG", "PHAS", "UPH", "POL", "SMIT", "ISM",
                "GDEL", "REAL", "IMAG", "SWR", "COMP", "MAGN", "LOG", "GDD"),
        cast=str,
    )
    sweep_time = Channel.measurement(
        "SENS{ch}:SWE:TIME?", """Duration of one sweep in seconds.""",
    )

    def define_trace(self, name: str, parameter: str = "S11") -> None:
        """Create/select a single-ended S-parameter trace for ports 1 to 4.

        Ports must exist in the analyzer's logical port configuration. Trace
        names are global; reusing a name on this channel replaces that trace.
        The new trace is not automatically displayed on the instrument screen.
        """
        quoted = _scpi_string(name)
        if not isinstance(parameter, str):
            raise ValueError("Expected an S-parameter such as S11 or S21")
        parameter = parameter.upper()
        if len(parameter) != 3 or parameter[0] != "S" or any(
            p not in "1234" for p in parameter[1:]
        ):
            raise ValueError("Expected an S-parameter between S11 and S44")
        with self.parent._io_lock:
            self.write(f"CALC{{ch}}:PAR:SDEF {quoted},'{parameter}'")
            self.select_trace(name)

    def select_trace(self, name: str) -> None:
        """Select an existing trace on this channel."""
        self.write(f"CALC{{ch}}:PAR:SEL {_scpi_string(name)}")

    def clear_averages(self) -> None:
        """Clear accumulated averaging data and start a fresh average cycle."""
        self.write("SENS{ch}:AVER:CLE")

    def sweep(self, wait: bool = True) -> None:
        """Acquire sweep_count sweeps, leaving this channel in single mode.

        Honors trigger_source and averaging settings. For a fresh N-sweep
        average, enable averaging, set both counts to N and clear_averages().
        With wait=True, *OPC? blocks until completion; configure the adapter's
        timeout for the entire cycle, including any external/manual trigger.
        """
        with self.parent._io_lock:
            self.continuous_enabled = False
            self.write("INIT{ch}:IMM")
            if wait:
                self.parent.wait_for_complete()

    def _read_ascii(self, command: str) -> list[float]:
        response = self.ask(command).strip()
        if not response:
            raise ValueError("The analyzer returned empty trace data")
        return [float(value) for value in response.split(",")]

    def read_trace(self, name: str | None = None) -> tuple[list[float], list[complex]]:
        """Read the active/named trace as (stimulus, complex values).

        Does not trigger a sweep. Call sweep() first for a completed acquisition.
        Stimulus units are Hz for frequency sweeps, dBm for power sweeps and
        seconds for time sweeps. Uses the instrument's actual stimulus values,
        including logarithmic and segmented sweeps. SDAT includes applied
        calibration but ignores display format and trace mathematics.

        Sets the instrument-wide transfer format to ASCII and leaves it there.
        For a consistent snapshot, the channel must be in single sweep mode
        with a completed acquisition and no other controller changing settings.
        """
        with self.parent._io_lock:
            if name is not None:
                self.select_trace(name)
            self.parent.write("FORM ASC")
            stimulus = self._read_ascii("CALC{ch}:DATA:STIM?")
            data = self._read_ascii("CALC{ch}:DATA? SDAT")
            if len(data) != 2 * len(stimulus):
                raise ValueError("Expected one real/imaginary pair per stimulus point")
            return stimulus, [complex(real, imag) for real, imag in zip(data[::2], data[1::2])]

    def read_formatted_data(self, name: str | None = None) -> list[float]:
        """Read FDAT in the active display format, without triggering a sweep.

        Returns one value per point for Cartesian formats, two for polar/Smith
        formats. Sets the global transfer format to ASCII and leaves it there.
        """
        with self.parent._io_lock:
            if name is not None:
                self.select_trace(name)
            self.parent.write("FORM ASC")
            return self._read_ascii("CALC{ch}:DATA? FDAT")


class ZNB43(SCPIMixin, Instrument):
    """Rohde & Schwarz ZNB43, 100 kHz to 43.5 GHz, with 2 or 4 RF ports.

    Accepts a PyMeasure Adapter or a VISA resource string. Adapter options such
    as visa_library, timeout and terminations are forwarded to PyMeasure.
    Construction preserves instrument state; reset() is explicit.
    """

    ch_1 = Instrument.ChannelCreator(ZNB43Channel, 1)

    rf_enabled = Instrument.control(
        "OUTP?", "OUTP %d",
        """Global RF output state for all channels and ports.""",
        validator=strict_discrete_set, values={False: 0, True: 1}, map_values=True,
    )

    def __init__(self, adapter, name: str = "Rohde & Schwarz ZNB43", **kwargs):
        self._io_lock = RLock()
        super().__init__(adapter, name=name, **kwargs)
        fields = (
            ("Start frequency (Hz)", "start_frequency", float),
            ("Stop frequency (Hz)", "stop_frequency", float),
            ("Sweep points", "sweep_points", int),
            ("Sweep type", "sweep_type", str),
            ("IF bandwidth (Hz)", "if_bandwidth", float),
            ("Source power (dBm)", "source_power", float),
            ("Averaging enabled", "averaging_enabled", bool),
            ("Average count", "average_count", int),
            ("Sweep count", "sweep_count", int),
            ("Continuous sweep", "continuous_enabled", bool),
            ("Trigger source", "trigger_source", str),
            ("Trace format", "trace_format", str),
        )
        self.properties_list = [
            property_info(f"CH1 {label}", kind,
                          lambda attr=attr: getattr(self.ch_1, attr),
                          lambda value, attr=attr: setattr(self.ch_1, attr, value))
            for label, attr, kind in fields
        ]
        self.properties_list.append(property_info(
            "RF enabled (all channels)", bool,
            lambda: self.rf_enabled, lambda value: setattr(self, "rf_enabled", value),
        ))

    def channel(self, number: int = 1) -> ZNB43Channel:
        """Get a cached measurement channel without communicating with hardware."""
        if isinstance(number, bool) or not isinstance(number, Integral) or number < 1:
            raise ValueError("Channel number must be a positive integer")
        with self._io_lock:
            if number not in self.channels:
                self.add_child(ZNB43Channel, number)
            return self.channels[number]

    def write(self, command: str, **kwargs) -> None:
        with self._io_lock:
            super().write(command, **kwargs)

    def ask(self, command: str, query_delay: float | None = None) -> str:
        with self._io_lock:
            return super().ask(command, query_delay=query_delay)

    def wait_for_complete(self) -> None:
        """Wait for pending operations using *OPC? and the adapter timeout."""
        if self.ask("*OPC?").strip() != "1":
            raise RuntimeError("Unexpected response to *OPC?")


PLUGIN = InstrumentSpec(
    id="znb43", name="Rohde & Schwarz ZNB43", idn_keywords=("ZNB43",),
    factory=lambda adapter, info: ZNB43(adapter=adapter, name=info.name),
)
