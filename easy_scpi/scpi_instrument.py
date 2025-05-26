# Portions of this file are adapted from easy-scpi, licensed under MIT and Apache 2.0.
# See LICENSE-MIT and LICENSE-APACHE for details.
import re
import platform
import threading
import time
import pyvisa as visa
from typing import List, Union, Optional, Tuple
from functools import wraps
from pyvisa.resources import Resource, MessageBasedResource


class helper_methods:
    @staticmethod
    def get_resource_list(backend: str = ""):
        """
        Returns a list of all available resources.

        :param backend: The pyvisa backend to use for communication. [Default: '']
        :returns: A list of all available resources.
        """
        rm = visa.ResourceManager(backend)
        return rm.list_resources()

    @staticmethod
    def val_to_bool(val) -> bool:
        """
        Converts a string to a boolean.

        :param val: The string to convert.
        :returns: True if the string is '1', 'true', or 'True', False otherwise.
        """
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            val = val.lower()
        if val in ["1", "true", "on", 1]:
            return True
        elif val in ["0", "false", "off", 0]:
            return False
        raise ValueError(f"Invalid value for boolean conversion: {val}")


class SCPI_Instrument:
    """
    Represents an instrument

    Arbitrary SCPI commands can be performed
    treating the hieracrchy of the command as attributes.

    To read an property:  inst.p1.p2.p3()
    To call a function:   inst.p1.p2( 'value' )
    To execute a command: inst.p1.p2.p3( '' )
    """

    def __init__(
        self,
        port: Optional[str] = None,
        port_match: bool = True,
        backend: str = "",
        handshake: str | bool = False,
        arg_separator: str = ",",
        prefix_cmds: bool = False,
        **resource_params,
    ):
        """
        Creates an instance of an Instrument, to communicate with VISA instruments.

        :param port: The name of the port to connect to. [Default: None]
        :param port_match: Verify the port is associated to a resource when connecting.
        :param backend: The pyvisa backend to use for communication. [Default: '']
        :param handshake: Handshake mode. [Default: False]
        :param arg_separator: Separator to use between arguments. [Default: ',']
        :param prefix_cmds: Option to prefix all commands with a colon. [Default: False]
        :param resource_params: Arguments sent to the resource upon connection.
            https://pyvisa.readthedocs.io/en/latest/api/resources.html
        :returns: An Instrument communicator.
        """
        self.__backend: str = backend
        self.__rm = visa.ResourceManager(backend)
        self.__inst = None
        self.__port: Optional[str] = None
        self.__port_match: bool = port_match
        self.__rid: Optional[str] = None  # the resource id of the instrument
        self.__resource_params = resource_params  # options for connection

        self.port: Optional[str] = port
        self.arg_separator: str = arg_separator
        self.prefix_cmds: bool = prefix_cmds

        if handshake is True:
            handshake = "OK"

        self.handshake = handshake
        self.__lock = threading.RLock()

    def __del__(self):
        """
        Disconnects and deletes the Instrument
        """
        if self.connected:
            self.disconnect()

        del self.__inst
        del self.__rm

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def is_message_based(self):
        """
        Check if the instrument is message based.

        :returns: True if the instrument is message based, False otherwise.
        """
        return isinstance(self.__inst, MessageBasedResource)

    @property
    def backend(self):
        return self.__backend

    @property
    def instrument(self):
        return self.__inst

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, port):
        """
        Connects to the given port based on the OS.
        [See #_set_port_windows and #_set_port_linux for more.]

        :param port: The port to connect to.
        """
        if port is None:
            self.__port = None
            self.__rid = None
            return

        system = platform.system()
        if system == "Windows":
            self._set_port_windows(port, match=self.port_match)

        else:
            self._set_port_linux(port, match=self.port_match)

    @property
    def port_match(self):
        """
        Verify the port is associated to a resource when connecting.
        """
        return self.__port_match

    @port_match.setter
    def port_match(self, port_match):
        """
        :param port_match: Whether to require the port to be found before connecting.
        """
        self.__port_match = port_match

    @property
    def rid(self):
        """
        Return the resource id of the instrument.
        """
        return self.__rid

    @rid.setter
    def rid(self, rid):
        """
        :param rid: Resource id.
        """
        self.__rid = rid

    @property
    def resource_params(self):
        return self.__resource_params

    @property
    def id(self):
        """
        Returns the id of the instrument.
        """
        return self._query("*IDN?")

    @property
    def value(self):
        """
        Get current value.
        """
        return self._query("READ?")

    @property
    def connected(self):
        """
        Returns if the instrument is connected.
        """
        if self.__inst is None:
            return False

        try:
            # session throws excpetion if not connected
            self.__inst.session
            return True
        except visa.InvalidSession:
            return False

    @property
    def is_connected(self):
        """
        Alias for connected.
        """
        return self.connected

    def connect(self, explicit_remote=False):
        """
        Connects to the instrument on the given port.
        """
        if not self.rid:
            raise RuntimeError("Can not connect. No resource id provided.")

        if self.__inst is None:
            self.__inst = self.__rm.open_resource(self.rid)

            # set resource parameters
            for param, val in self.__resource_params.items():
                setattr(self.__inst, param, val)

        else:
            self.__inst.open()
        if explicit_remote is False:
            self.id  # place instrument in remote control
        else:
            self._write(explicit_remote)

    def disconnect(self):
        """
        Disconnects from the instrument, and returns local control.
        """
        if self.__inst is not None:
            self.__inst.close()

    def write(self, msg):
        return self._write(msg)

    def _write(self, msg):
        """
        Delegates write to resource.

        :param msg: Message to send.
        :returns: Response from the message.
        :raises RuntimeError: If an instrument is not connected.
        """
        if self.__inst is None:
            raise RuntimeError("Can not write, instrument not connected.")
        with self.__lock:
            resp = self.__inst.write(msg)
            self._handle_handshake()

        return resp

    def _read(self):
        """
        Delegates read to resource.

        :returns: Response from the read.
        :raises RuntimeError: If an instrument is not connected.
        """
        if self.__inst is None:
            raise RuntimeError("Can not read, instrument not connected")
        with self.__lock:
            resp = self.__inst.read()
        return resp

    def read(self):
        return self._read()

    def _query(self, msg):
        """
        Delegates query to resource.

        :param msg: Message to send.
        :returns: Response from the message.
        :raises RuntimeError: If an instrument is not connected.
        """
        if self.__inst is None:
            raise RuntimeError("Can not query, instrument not connected")
        with self.__lock:
            resp = self.__inst.query(msg)
            self._handle_handshake()
        return resp

    def query(self, msg):
        resp = self._query(msg)
        return resp

    def reset(self):
        """
        Resets the meter to inital state.
        Sends `*RST` command.

        :returns: Response from the command.
        """
        return self._write("*RST")

    def init(self):
        """
        Initialize the instrument.
        Sends the `INIT` command.

        :returns: Response from the command.
        """
        return self._write("INIT")

    def _handle_handshake(self):
        """
        Handles handshaking if enabled.

        :raises RuntimeError: If the response message does not match the handshake message.
        """
        if self.handshake:
            hs = self._read()
            if hs != self.handshake:
                raise RuntimeError(hs)

    def _set_port_windows(self, port, match=True):
        """
        Disconnects from current connection and updates port and id.
        Does not reconnect.

        :param port: Name of port to connect to.
        :param match: Whether to verify the port matches a resource. [Default: True]
        :raises ValueError: If connection type is not specified.
        """
        prefixes = ["COM", "USB", "GPIB", "TCPIP"]
        port_name = port.upper()

        if not any(port_name.startswith(p) for p in prefixes):
            raise ValueError(f"Port must start with one of the following: {prefixes}.")

        if self.__inst is not None:
            self.disconnect()

        self.__port = port

        # search for resource
        if any(port_name.startswith(p) for p in prefixes[1:]):
            # connections except com
            resource_pattern = (
                port
                if port_name.endswith("INSTR") or port_name.endswith("SOCKET")
                else f"{ port }::.*::INSTR"
            )

        elif port_name.startswith("COM"):
            r_port = port.replace("COM", "")
            resource_pattern = f"ASRL((?:COM)?{r_port})::INSTR"

        else:
            # redundant error check for future compatibility
            raise ValueError(f"Port must start with one of the following: {prefixes}.")

        # single matching resource
        resource = self._match_resource(resource_pattern) if match else resource_pattern
        self.__rid = resource

    def _set_port_linux(self, port: str, match: bool = True):
        """
        Disconnects from current connection and updates port and id.
        Does not reconnect.

        :param port: Name of port to connect to.
        :param match: Whether to verify the port matches a resource. [Default: True]
        """
        prefixes = ["USB", "GPIB", "TCPIP"]
        port_name = port.upper()

        if self.__inst is not None:
            self.disconnect()

        self.__port = port

        # search for resource
        if any(port_name.startswith(p) for p in prefixes):
            resource_pattern = (
                port
                if port_name.endswith("INSTR") or port_name.endswith("SOCKET")
                else f"{port}::.*::INSTR"
            )
        else:
            # build resource pattern
            resource_pattern = port
            if not resource_pattern.startswith("ASRL"):
                asrl = "ASRL"
                if not resource_pattern.startswith("/"):
                    asrl += "/"

                resource_pattern = f"{asrl}{resource_pattern}"

            if not resource_pattern.endswith("::INSTR"):
                resource_pattern = f"{resource_pattern}::INSTR"

        resource = self._match_resource(resource_pattern) if match else resource_pattern
        self.__rid = resource

    def _match_resource(self, resource):
        """
        Matches port name with a resource.

        :param resource: Resource name.
        :returns: Resource name.
        :raises RuntimeError: If 0 or more than 1 matching resource is found.
        """
        rm = visa.ResourceManager(self.backend)
        matches = [
            re.match(resource, res, re.IGNORECASE) for res in rm.list_resources()
        ]

        matches = [match for match in matches if match is not None]
        if matches == []:
            raise RuntimeError(f"Could not find resource {resource}")
        elif len(matches) > 1:
            raise RuntimeError(f"Found multiple resources matching {resource}")

        if matches[0] is None:
            raise RuntimeError(
                f"Unexpected error: match for resource {resource} is None"
            )
        r_name = matches[0].group(0)
        return r_name

    def read_raw(self, *args, **kwargs):
        if not self.is_message_based():
            raise RuntimeError("read_raw is not supported for this resource type")
        if self.__inst is None:
            raise RuntimeError("Can not read, instrument not connected")
        with self.__lock:
            resp = self.__inst.read_raw(*args, **kwargs)
        return resp

    def query_ascii_values(self, *args, **kwargs):
        """
        Delegates query to resource.

        :param msg: Message to send.
        :returns: Response from the message.
        :raises RuntimeError: If an instrument is not connected.
        """
        if not self.is_message_based():
            raise RuntimeError(
                "query_ascii_values is not supported for this resource type"
            )
        if self.__inst is None:
            raise RuntimeError("Can not query, instrument not connected")
        with self.__lock:
            resp = self.__inst.query_ascii_values(*args, **kwargs)
            self._handle_handshake()
        return resp

    def query_binary_values(self, *args, **kwargs):
        """
        Delegates query to resource.

        :param msg: Message to send.
        :returns: Response from the message.
        :raises RuntimeError: If an instrument is not connected.
        """
        if not self.is_message_based():
            raise RuntimeError(
                "query_binary_values is not supported for this resource type"
            )
        if self.__inst is None:
            raise RuntimeError("Can not query, instrument not connected")
        with self.__lock:
            resp = self.__inst.query_binary_values(*args, **kwargs)
            self._handle_handshake()
        return resp
