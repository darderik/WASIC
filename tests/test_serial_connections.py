"""Exercise the real VISA/driver stack with an in-memory serial instrument."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from connections import Connections
from connections.baud_detector import BaudTrialResult, BaudTrialDetector, SerialParamCache
from instruments import Instrument_Entry, SCPI_Info
from pyvisa.constants import StopBits


class MemorySerial:
    def __init__(self, idn, terminator="\n", flow=False, write_termination="\n"):
        self.idn = idn
        self.terminator = terminator
        self.flow = flow
        self.write_termination = write_termination
        self.pending = bytearray()
        self.writes = []
        self.baudrate = 9600
        self.bytesize = 8
        self.parity = "N"
        self.stopbits = 1
        self.xonxoff = self.rtscts = self.dsrdtr = False

    def write(self, data):
        self.writes.append(data)
        if data == ("*IDN?" + self.write_termination).encode() and self.baudrate == 19200:
            tokens = self.flow and not self.xonxoff
            self.pending.extend((b"\x13" if tokens else b"") + self.idn.encode()
                                + (b"\x11" if tokens else b"") + self.terminator.encode())
        return len(data)

    def read(self, count):
        data = bytes(self.pending[:count])
        del self.pending[:count]
        return data

    @property
    def in_waiting(self):
        return len(self.pending)

    def close(self):
        pass


class SerialConnectionTests(unittest.TestCase):
    def test_relay_acknowledgements_do_not_replace_query_responses(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        adapter = Mock()
        idn = "DIIEM,Relay Matrix,123,V1.0"
        adapter.read.side_effect = [idn, "OK", idn, "OK", "1", "OK"]
        instrument = RelayMatrix(adapter, "Relay Matrix")
        self.assertEqual(instrument.ask("*IDN?"), idn)
        self.assertEqual(instrument.ask("*IDN?"), idn)
        self.assertTrue(instrument.opc())
        self.assertEqual(adapter.write.call_count, 3)

    def test_relay_waits_for_each_ok_before_sending_opc(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        adapter = Mock()
        exchanges = []
        pending = []
        def write(command, **kwargs):
            self.assertFalse(pending, "A command was sent before consuming the previous reply")
            exchanges.append(("write", command))
            pending.extend(["1", "OK"] if command == "*OPC?" else ["OK"])
        def read(**kwargs):
            response = pending.pop(0)
            exchanges.append(("read", response))
            return response
        adapter.write.side_effect = write
        adapter.read.side_effect = read
        instrument = RelayMatrix(adapter, "Relay Matrix")
        instrument.switch_commute_reset_all()
        self.assertEqual(exchanges, [
            ("write", "switch:commute:reset:all"), ("read", "OK"),
            ("write", "*OPC?"), ("read", "1"), ("read", "OK"),
        ])
        self.assertFalse(pending)

    def test_relay_concurrent_write_waits_until_query_response_is_consumed(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        from threading import Event, Thread
        adapter = Mock()
        response_started, allow_response = Event(), Event()
        second_attempted, second_written = Event(), Event()
        failures = []
        def read():
            if adapter.read.call_count == 1:
                response_started.set()
                if not allow_response.wait(2):
                    raise TimeoutError("Test did not release query response")
                return "1"
            return "OK"
        adapter.read.side_effect = read
        adapter.write.side_effect = lambda command, **kwargs: (
            second_written.set() if command != "*OPC?" else None
        )
        instrument = RelayMatrix(adapter, "Relay Matrix")
        def query():
            try:
                instrument.opc()
            except Exception as exc:
                failures.append(exc)
        def command():
            second_attempted.set()
            try:
                instrument.write("switch:commute:reset:all")
            except Exception as exc:
                failures.append(exc)
        first, second = Thread(target=query, daemon=True), Thread(target=command, daemon=True)
        first.start()
        try:
            self.assertTrue(response_started.wait(2))
            second.start()
            self.assertTrue(second_attempted.wait(2))
            self.assertFalse(second_written.wait(0.05))
        finally:
            allow_response.set()
            first.join(2)
            if second.ident is not None:
                second.join(2)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertFalse(failures)
        self.assertTrue(second_written.is_set())

    def test_relay_missing_ack_blocks_all_further_commands(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        from pyvisa.errors import VisaIOError
        from pyvisa.constants import StatusCode
        adapter = Mock()
        adapter.read.side_effect = VisaIOError(StatusCode.error_timeout)
        instrument = RelayMatrix(adapter, "Relay Matrix")
        with self.assertRaises(VisaIOError):
            instrument.switch_commute_reset_all()
        with self.assertRaisesRegex(RuntimeError, "reconnect"):
            instrument.switch_commute_reset_all()
        adapter.write.assert_called_once_with("switch:commute:reset:all")

    def test_relay_invalid_ack_does_not_send_opc(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        adapter = Mock()
        adapter.read.return_value = "ERROR"
        instrument = RelayMatrix(adapter, "Relay Matrix")
        with self.assertRaisesRegex(RuntimeError, "expected final OK"):
            instrument.switch_commute_reset_all()
        adapter.write.assert_called_once_with("switch:commute:reset:all")

    def test_relay_missing_query_response_requires_reconnection(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        adapter = Mock()
        adapter.read.side_effect = TimeoutError("query response missing")
        instrument = RelayMatrix(adapter, "Relay Matrix")
        with self.assertRaises(TimeoutError):
            instrument.opc()
        with self.assertRaisesRegex(RuntimeError, "reconnect"):
            instrument.write("switch:commute:reset:all")
        adapter.write.assert_called_once_with("*OPC?")

    def test_relay_query_requires_final_ok_even_after_valid_output(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        adapter = Mock()
        idn = "DIIEM,Relay Matrix,123,V1.0"
        adapter.read.side_effect = [idn, TimeoutError("final OK missing")]
        instrument = RelayMatrix(adapter, "Relay Matrix")
        with self.assertRaises(TimeoutError):
            instrument.ask("*IDN?")
        with self.assertRaisesRegex(RuntimeError, "reconnect"):
            instrument.opc()
        adapter.write.assert_called_once_with("*IDN?")

    def test_refresh_verifies_relay_with_output_then_ack(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        from collections import deque
        adapter = Mock()
        idn = "DIIEM,Relay Matrix,123,V1.0"
        pending = deque()
        def write(command, **kwargs):
            self.assertFalse(pending, "A previous command's final OK was not consumed")
            self.assertEqual(command, "*IDN?")
            pending.extend((idn, "OK"))
        adapter.write.side_effect = write
        adapter.read.side_effect = pending.popleft
        instrument = RelayMatrix(adapter, "Relay Matrix")
        entry = Instrument_Entry(SCPI_Info("COM4", 115200, idn=idn), instrument)
        for _ in range(3):
            self.assertTrue(Connections._is_instrument_alive(entry))
            self.assertFalse(pending)

    def test_probe_consumes_idn_final_ok_without_preceding_cls(self):
        idn = "DIIEM,Relay Matrix,123,V1.0"
        serial = MemorySerial(idn)
        serial.baudrate = 19200
        original_write = serial.write
        def handshake_write(data):
            self.assertFalse(serial.pending, "Previous handshake was not consumed")
            result = original_write(data)
            if data == b"*IDN?\n":
                serial.pending.extend(b"OK\n")
            return result
        serial.write = handshake_write
        with tempfile.TemporaryDirectory() as temp, \
             patch("connections.baud_detector.open_serial_adapter",
                   return_value=self.probe_adapter(serial)):
            detector = BaudTrialDetector("COM98", clear_on_connect=False,
                                         cache=SerialParamCache(str(Path(temp) / "cache")))
            result = detector._try_candidate_worker(19200, StopBits.one)
        self.assertEqual(result.idn, idn)
        self.assertEqual(serial.writes, [b"*IDN?\n"])
        self.assertFalse(serial.pending)

    def test_connection_discovery_uses_idn_without_cls(self):
        with patch("connections.connections.BaudTrialDetector") as detector:
            detector.return_value.detect.return_value = None
            self.assertIsNone(Connections._detect_serial_port("COM98"))
        detector.assert_called_once_with(port="COM98", clear_on_connect=False)

    def test_adjacent_handshake_and_idn_are_preserved(self):
        from connections.baud_detector import read_probe_line
        serial = MemorySerial("vendor,model,123")
        serial.pending.extend(b"OK\nDIIEM,Relay Matrix,123,V1.0\n")
        adapter = self.probe_adapter(serial)
        self.assertEqual(read_probe_line(adapter, 0.15), b"OK\n")
        self.assertEqual(read_probe_line(adapter, 0.15), b"DIIEM,Relay Matrix,123,V1.0\n")

    def probe_adapter(self, serial):
        adapter = SimpleNamespace(connection=serial, write_termination="\n", close=serial.close)
        adapter.write = lambda command: serial.write((command + adapter.write_termination).encode())
        return adapter

    def test_automatic_framing_flow_and_cache_through_real_driver(self):
        idn = "KEITHLEY INSTRUMENTS INC.,MODEL 6221,123,C01"
        for term in ("\r", "\n", "\r\n", "\n\r"):
            for flow in (False, True):
                with self.subTest(terminator=repr(term), flow=flow), tempfile.TemporaryDirectory() as temp:
                    cache = SerialParamCache(str(Path(temp) / "cache.json"))
                    cache.save_success("COM98", 19200, StopBits.one)  # Legacy defaults.
                    serial = MemorySerial(idn, term, flow)
                    serial.baudrate = 19200
                    with patch("connections.baud_detector.open_serial_adapter",
                               return_value=self.probe_adapter(serial)):
                        result = BaudTrialDetector("COM98", cache=cache).detect()
                    self.assertIsNotNone(result)
                    self.assertEqual(result.idn, idn)
                    self.assertEqual(result.read_termination, term)
                    self.assertEqual(result.flow_control, "xon_xoff" if flow else "none")
                    self.assertEqual(cache.get("COM98")["read_termination"], term)
                    self.assertEqual(serial.writes.count(b"*IDN?\n"), 1)
                    info = Connections()._build_serial_info(
                        "COM98", idn, 19200, "one", result.read_termination,
                        result.write_termination, result.flow_control)
                    with patch("pyvisa_py.serial.serial.serial_for_url", return_value=serial):
                        entry = Connections()._create_instrument_entry(info)
                        try:
                            entry.scpi_instrument.adapter.connection.timeout = 50
                            # Repeated reads must consume paired terminators fully.
                            for _ in range(2):
                                self.assertEqual(entry.ask_wrapper("*IDN?"), idn)
                        finally:
                            entry.scpi_instrument.adapter.close()

    def test_cr_only_commands_are_detected_and_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = SerialParamCache(str(Path(temp) / "cache.json"))
            serial = MemorySerial("vendor,model,123", "\r", True, "\r")
            serial.baudrate = 19200
            cache.save_success("COM98", 19200, StopBits.one)
            with patch("connections.baud_detector.open_serial_adapter",
                       return_value=self.probe_adapter(serial)):
                result = BaudTrialDetector("COM98", cache=cache).detect()
                self.assertEqual(result.write_termination, "\r")
                serial.writes.clear()
                self.assertEqual(BaudTrialDetector("COM98", cache=cache).detect(), result)
                self.assertEqual(serial.writes, [b"*CLS\r", b"*IDN?\r"])

    def test_stale_cached_baud_recovers_and_refreshes_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = SerialParamCache(str(Path(temp) / "cache.json"))
            cache.save_success("COM98", 115200, StopBits.one)
            def open_candidate(port, baud, stop_bits, timeout):
                serial = MemorySerial("vendor,model,123", "\r", True)
                serial.baudrate = baud
                return self.probe_adapter(serial)
            with patch("connections.baud_detector.open_serial_adapter", side_effect=open_candidate):
                result = BaudTrialDetector("COM98", cache=cache).detect()
            self.assertEqual(result.baud_rate, 19200)
            self.assertEqual(cache.get("COM98")["flow_control"], "xon_xoff")

    def test_unterminated_partial_reply_is_rejected(self):
        serial = MemorySerial("vendor,model,123", "")
        serial.baudrate = 19200
        with patch("connections.baud_detector.open_serial_adapter",
                   return_value=self.probe_adapter(serial)), tempfile.TemporaryDirectory() as temp:
            detector = BaudTrialDetector("COM98", cache=SerialParamCache(str(Path(temp) / "cache")))
            self.assertIsNone(detector._try_candidate_worker(19200, StopBits.one))

    def test_failed_definitive_connection_is_closed_and_not_listed(self):
        connections = Connections()
        previous = connections.instruments_list
        connections.instruments_list = []
        instrument = Mock()
        instrument.ask.return_value = "different instrument"
        info = SCPI_Info("COM98", 19200, idn="vendor,model,123", resource_str="ASRL98::INSTR")
        try:
            with patch.object(connections, "_create_instrument_entry",
                              return_value=Instrument_Entry(info, instrument)), \
                 patch("connections.connections.SerialParamCache") as cache:
                self.assertFalse(connections._add_instrument(info))
                self.assertEqual(connections.instruments_list, [])
                instrument.adapter.connection.close.assert_called_once()
                cache.return_value.forget.assert_called_once_with("COM98")
        finally:
            connections.instruments_list = previous

    def test_detected_settings_work_through_both_keithley_drivers(self):
        connections = Connections()
        for model in ("2182A", "6221"):
            with self.subTest(model=model):
                idn = f"KEITHLEY INSTRUMENTS INC.,MODEL {model},123,C01"
                serial = MemorySerial(idn)
                detected = BaudTrialResult(19200, StopBits.two, idn)
                with patch("connections.connections.BaudTrialDetector") as detector:
                    detector.return_value.detect.return_value = detected
                    row = connections._detect_serial_port("COM98")
                info = connections._build_serial_info(*row)
                with patch("pyvisa_py.serial.serial.serial_for_url", return_value=serial):
                    entry = connections._create_instrument_entry(info)
                    self.assertIsNotNone(entry)
                    try:
                        entry.scpi_instrument.adapter.connection.timeout = 50
                        self.assertEqual(entry.ask_wrapper("*IDN?"), idn)
                        self.assertEqual(serial.writes, [b"*IDN?\n"])
                        self.assertEqual(serial.stopbits, 2)
                        self.assertFalse(serial.xonxoff or serial.rtscts or serial.dsrdtr)
                    finally:
                        entry.scpi_instrument.adapter.close()

    def test_discovery_only_lists_resources_and_keeps_manager_open(self):
        connections = Connections()
        manager = Mock()
        manager.list_resources.return_value = ("ASRL5::INSTR", "USB::TEST")
        with patch("connections.connections.pyvisa.ResourceManager", return_value=manager), \
             patch.object(connections, "_process_visa_resource") as process:
            connections._discover_visa_instruments([])
        manager.open_resource.assert_not_called()
        manager.close.assert_not_called()
        process.assert_called_once_with("USB::TEST")

    def test_visa_probe_is_closed_before_opening_driver_connection(self):
        from pymeasure.instruments import Instrument

        connections = Connections()
        resource = "USB0::2733::617::101612::0::INSTR"
        idn = "Rohde-Schwarz,ZNB43-4Port,1334333095101612,3.72"
        info = SCPI_Info(resource, 0, idn=idn, resource_str=resource)
        adapter = Mock()
        adapter.read.return_value = idn
        probe = Instrument(adapter, resource, includeSCPI=False)

        def open_driver(info):
            adapter.close.assert_called_once_with()
            return True

        with patch("connections.connections.Instrument", return_value=probe) as factory, \
             patch.object(connections, "_build_visa_info", return_value=info), \
             patch.object(connections, "_add_instrument", side_effect=open_driver) as add:
            connections._process_visa_resource(resource)

        factory.assert_called_once_with(
            adapter=resource, visa_library=connections.backend, name=resource)
        adapter.write.assert_called_once_with("*IDN?")
        add.assert_called_once_with(info)
        adapter.close.assert_called_once_with()

    def test_failed_visa_probe_closes_adapter(self):
        from pymeasure.instruments import Instrument

        adapter = Mock()
        adapter.read.side_effect = RuntimeError("IDN failed")
        probe = Instrument(adapter, "USB probe", includeSCPI=False)
        connections = Connections()
        with patch("connections.connections.Instrument", return_value=probe), \
             patch.object(connections, "_add_instrument") as add, \
             self.assertLogs("connections.connections", level="ERROR"):
            connections._process_visa_resource("USB::TEST")
        adapter.close.assert_called_once_with()
        add.assert_not_called()

    def test_open_serial_ports_are_excluded_from_next_scan(self):
        connections = Connections()
        previous = connections.instruments_list
        try:
            connections.instruments_list = [Instrument_Entry(
                SCPI_Info("COM5", 19200, resource_str="ASRL5::INSTR"),
                SimpleNamespace(adapter=object()),
            )]
            with patch("connections.connections.comports", return_value=[
                SimpleNamespace(name="COM5"), SimpleNamespace(name="COM6")
            ]):
                self.assertEqual(connections._get_available_serial_ports(
                    connections._get_locked_ports()), ["COM6"])
        finally:
            connections.instruments_list = previous

    def test_old_saved_connections_default_to_one_stop_bit(self):
        self.assertEqual(SCPI_Info(**{"port": "COM5", "baud_rate": 19200}).stop_bits, "one")


if __name__ == "__main__":
    unittest.main()
