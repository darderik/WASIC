from typing import List, Optional, Tuple, Union
from easy_scpi import Instrument
from instruments import SCPI_Info
# Assuming these exist in your codebase
# from your_lib import Instrument, SCPI_Info, property_info

class SCPIInstrumentTemplate(Instrument):
    """
    Generic SCPI Instrument Template
    ================================
    Replace placeholders and add device-specific methods from the manual.

    Common Methods
    --------------
    opc() -> bool:
        Waits for operation complete (*OPC?) and returns True when ready.
    idn() -> str:
        Returns the device identification string.
    rst() -> None:
        Issues a device reset (*RST).
    cls() -> None:
        Clears status (*CLS).
    check_error() -> Optional[str]:
        Queries the error queue (SYST:ERR?) and returns the top error or None.
    """

    def __init__(self, scpi_info: SCPI_Info, **kwargs) -> None:
        super().__init__(
            port=scpi_info.port,
            timeout=kwargs.get("timeout", 5000),
            baud_rate=scpi_info.baud_rate,
            handshake=kwargs.get("handshake", True),
            write_termination=kwargs.get("write_termination", "\n"),
            read_termination=kwargs.get("read_termination", "\n"),
            backend=kwargs.get("backend", "@py"),
            encoding=kwargs.get("encoding", "ascii"),
        )
        self.properties_list = []  # fill if needed

    # -------- Core SCPI helpers --------
    def opc(self) -> bool:
        """Wait for operation complete and return True when ready."""
        resp = self.query("*OPC?")
        # Some instruments return "1"; be tolerant to whitespace.
        return str(resp).strip() == "1"

    def idn(self) -> str:
        """Standard identification query."""
        return self.query("*IDN?")

    def rst(self) -> None:
        """Standard reset."""
        self.write("*RST")

    def cls(self) -> None:
        """Clear status."""
        self.write("*CLS")

    def check_error(self) -> Optional[str]:
        """
        Check the system error queue.
        Returns None if '0' or 'No error', otherwise the error string.
        """
        try:
            msg = self.query("SYST:ERR?")
        except Exception:
            # Some instruments don't implement SYST:ERR?
            return None
        if msg is None:
            return None
        s = str(msg).strip()
        # Typical formats: '0,"No error"' or '-113,"Undefined header"'
        if s.startswith("0") or "No error" in s:
            return None
        return s

