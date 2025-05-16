from smtplib import bCRLF
from easy_scpi import Instrument
from instruments import SCPI_Info, property_info
from typing import List
from config import Config
import threading
import time

class RelayMatrix(Instrument):
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
    switch_commute_exclusive(relay: str) -> None:
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

    def __init__(self, scpi_info: SCPI_Info,backend="@py", **kwargs) -> None:
        """
        Initializes the RelayMatrix object with the specified SCPI parameters.

        Parameters
        ----------
        port : str
            The serial port for the connection.
        baud_rate : int, optional
            Baud rate for the serial communication (default is 9600).
        """
        super().__init__(
            port=scpi_info.port,
            timeout=5000,
            baud_rate=scpi_info.baud_rate,
            handshake=False,
            write_termination="\n",
            read_termination="\n",
            encoding="utf-8",
            backend=backend,
        )
        self.__child_lock = threading.RLock()
        self.properties_list: List[property_info] = []  # No properties
    def opc(self) -> None:
        """
        Waits for the operation to complete.
        """
        resp=self.query("*OPC?")
        return resp
    def query(self, msg):
        with self.__child_lock:
            time.sleep(0.1) 
            return super().query(msg)
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

    def switch_commute_exclusive(self, *relays: str) -> None:
        """
        Activates a single relay and resets all others in its group.

        Parameters
        ----------
        relay : str
            The relay identifier in the format <group><number>, e.g., "b3", "c4".
        """
        command = f"switch:commute:exclusive {' '.join(relays)}"
        self.write(command)

    def get_system_log(self) -> str:
        """
        Retrieves the current system log via UART.
        Use \\| as newline character.
        Returns
        -------
        str
            The system log.
        """
        raw_msg: str = self.query("sys:log?")
        return raw_msg.replace("\\|", "\n")

    def get_system_state(self) -> str:
        """
        Returns the current system state.

        Returns
        -------
        str
            The system state.
        """
        return self.query("sys:getstate?")

    def halt_system(self) -> None:
        """
        Stops the system by turning off power.
        """
        self.write("sys:halt")


# Mandatory append to register instrument class with its alias
Config().add_instrument_extension(("Relay Matrix", RelayMatrix))
