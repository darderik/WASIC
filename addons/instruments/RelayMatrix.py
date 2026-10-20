from typing import List
from threading import RLock
from instruments import SCPI_Info, property_info
import pymeasure.adapters as pma
from pymeasure.instruments import Instrument,SCPIMixin


class RelayMatrix(SCPIMixin, Instrument):
    """
    RelayMatrix Class
    =================
    Class to control a relay matrix using SCPI commands.

    Methods
    -------
    switch_commute(*relays: str) -> None:
        Activates or deactivates one or more relays in the matrix.
    switch_commute_reset(*relays: str) -> None:
        Resets one or more relays in the matrix.
    switch_commute_reset_all() -> None:
        Resets all relays in the matrix.
    switch_commute_exclusive(*relays: str) -> None:
        Activates one relay and resets all others in its group.
    get_system_log() -> str:
        Retrieves the current system log via UART.
    get_system_state() -> str:
        Returns the current system state.
    halt_system() -> None:
        Stops the system by turning off power.
    identify() -> str:
        Retrieves the device identification and firmware version.
    """

    def __init__(self, adapter,name,**kwargs) -> None:
        """
        Initializes the RelayMatrix object with the specified SCPI parameters.

        Parameters
        ----------
        port : str
            The serial port for the connection.
        baud_rate : int, optional
            Baud rate for the serial communication (default is 9600).
        """

        self._io_lock = RLock()
        self._handshake_failed = False
        super().__init__(
            adapter,
            name=name,
        )

        self.init_properties()

    def write(self, command: str, **kwargs) -> None:
        """Send one command and consume its OK before allowing another send."""
        with self._io_lock:
            if self._handshake_failed:
                raise RuntimeError("Relay matrix handshake lost; reconnect before sending commands")
            try:
                super().write(command, **kwargs)
                self._read_acknowledgement(command)
            except Exception:
                self._handshake_failed = True
                raise

    def read(self, **kwargs) -> str:
        with self._io_lock:
            return super().read(**kwargs)

    def _read_acknowledgement(self, command: str) -> None:
        acknowledgement = str(super().read()).strip()
        if acknowledgement.upper() != "OK":
            raise RuntimeError(
                f"Relay matrix expected final OK for {command!r}, received {acknowledgement!r}"
            )

    def ask(self, command: str, query_delay=None) -> str:
        """Consume the query output and its final OK before allowing another send."""
        with self._io_lock:
            if self._handshake_failed:
                raise RuntimeError("Relay matrix handshake lost; reconnect before sending commands")
            try:
                super().write(command)
                self.wait_for(query_delay)
                response = str(super().read())
                self._read_acknowledgement(command)
                return response
            except Exception:
                self._handshake_failed = True
                raise

    def opc(self) -> bool:
        response = self.ask("*OPC?").strip()
        if response != "1":
            raise RuntimeError(f"Relay matrix operation not complete: {response!r}")
        return True

    def idn(self) -> str:
        return str(self.ask("*IDN?"))

    def init_properties(self) -> None:
        self.properties_list: List[property_info] = []  # No properties for now

    def switch_commute(self, *relays: str) -> None:
        """
        Activates or deactivates one or more relays in the matrix.

        Parameters
        ----------
        relays : str
            One or more relay identifiers in the format <group><number>, e.g., "a1", "b2", "c3".
        """
        command = f"switch:commute {' '.join(relays)}"
        self.write(command)
        self.opc()

    def switch_commute_reset(self, *relays: str) -> None:
        """
        Resets one or more relays in the matrix.

        Parameters
        ----------
        relays : str
            One or more relay identifiers in the format <group><number>, e.g., "a1", "d4".
        """
        command = f"switch:commute:reset {' '.join(relays)}"
        self.write(command)
        self.opc()

    def switch_commute_reset_all(self) -> None:
        """
        Resets all relays in the matrix, regardless of group or number.
        """
        self.write("switch:commute:reset:all")
        self.opc()

    def switch_commute_exclusive(self, *relays: str) -> None:
        """
        Activates a single relay and resets all others in its group.

        Parameters
        ----------
        relays : str
            The relay identifier in the format <group><number>, e.g., "b3", "c4".
        """
        command = f"switch:commute:exclusive {' '.join(relays)}"
        self.write(command)
        self.opc()

    def get_system_log(self) -> str:
        """
        Retrieves the current system log via UART.
        Use \\| as newline character.
        Returns
        -------
        str
            The system log.
        """
        raw_msg: str = self.ask("sys:log?")
        return raw_msg.replace("\\|", "\n")

    def get_system_state(self) -> str:
        """
        Returns the current system state.

        Returns
        -------
        str
            The system state.
        """
        return self.ask("sys:getstate?")

    def halt_system(self) -> None:
        """
        Stops the system by turning off power.
        """
        self.write("sys:halt")

    def identify(self) -> str:
        """
        Retrieves the device identification and firmware version.
        """
        return self.idn()



from wasic_api import InstrumentSpec

PLUGIN = InstrumentSpec(
    id='relay_matrix', name='Relay Matrix', idn_keywords=('Relay Matrix',),
    factory=lambda adapter, info: RelayMatrix(adapter=adapter, name=info.name),
)

