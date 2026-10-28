"""Concurrent query/refresh and task lifetime regressions, without hardware."""
import tempfile
import unittest
from collections import deque
from threading import Event, Thread
from unittest.mock import patch

from pymeasure.adapters import Adapter
from pymeasure.instruments import Channel, Instrument

from connections import Connections
from config import Config
from instruments import Instrument_Entry, SCPI_Info
from tasks import Task
from wasic_api import TaskSpec


class MemoryAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.idn = "KEITHLEY,MODEL 2000,123"
        self.pending = deque()
        self.writes = []
        self.block = None
        self.read_started, self.allow_read = Event(), Event()
        self.idn_written, self.value_written = Event(), Event()
        self.closes = 0

    def _write(self, command, **kwargs):
        if self.pending:
            raise AssertionError("Another command interrupted an outstanding response")
        self.writes.append(command)
        if command == "*IDN?":
            self.idn_written.set()
        if command.startswith("VALUE "):
            self.value_written.set()
        if "?" in command:
            self.pending.append((command, self.idn if command == "*IDN?" else "1.25"))

    def _read(self, **kwargs):
        command, response = self.pending[0]
        if command == self.block:
            self.read_started.set()
            if not self.allow_read.wait(3):
                raise TimeoutError("Test did not release the simulated response")
        self.pending.popleft()
        return response

    def close(self):
        self.closes += 1


class TestInstrument(Instrument):
    value = Instrument.control("VALUE?", "VALUE %g", "Example measurement.")

    def __init__(self, adapter):
        super().__init__(adapter, "Test instrument", includeSCPI=False)


class TestChannel(Channel):
    value = Channel.control("CHAN{ch}:VALUE?", "CHAN{ch}:VALUE %g", "Channel measurement.")


class InstrumentIOFixture(unittest.TestCase):
    def setUp(self):
        self.connections = Connections()
        self.previous_entries = self.connections.instruments_list
        self.adapter = MemoryAdapter()
        self.driver = TestInstrument(self.adapter)
        self.entry = Instrument_Entry(SCPI_Info("COM98", 9600, idn=self.adapter.idn,
                                               resource_str="ASRL98::INSTR"), self.driver)
        self.connections.instruments_list = [self.entry]
        self.failures = []
        self.workers = []

    def tearDown(self):
        self.adapter.allow_read.set()
        for worker in self.workers:
            worker.join(4)
            self.assertFalse(worker.is_alive(), "Concurrent instrument access deadlocked")
        self.connections.instruments_list = self.previous_entries
        self.assertEqual(self.failures, [])

    def launch(self, function):
        def run():
            try:
                function()
            except BaseException as exc:
                self.failures.append(exc)
        worker = Thread(target=run, daemon=True)
        self.workers.append(worker)
        worker.start()
        return worker

    def start_blocked_query(self):
        self.adapter.block = "VALUE?"
        self.launch(lambda: self.assertEqual(self.driver.value, 1.25))
        self.assertTrue(self.adapter.read_started.wait(2))


class InstrumentIOTests(InstrumentIOFixture):
    def test_refresh_waits_for_the_whole_query_and_keeps_the_connection(self):
        self.start_blocked_query()
        attempted = Event()
        def verify():
            attempted.set()
            self.connections.verify_instruments()
        verifier = self.launch(verify)
        self.assertTrue(attempted.wait(2))
        self.assertFalse(self.adapter.idn_written.wait(0.05))
        self.adapter.allow_read.set()
        verifier.join(2)
        self.assertFalse(verifier.is_alive())
        self.assertEqual(self.adapter.writes, ["VALUE?", "*IDN?"])
        self.assertEqual(self.connections.instruments_list, [self.entry])
        self.assertEqual(self.adapter.closes, 0)

    def test_property_setter_cannot_interrupt_a_property_query(self):
        self.start_blocked_query()
        attempted = Event()
        def write():
            attempted.set()
            self.driver.value = 2
        self.launch(write)
        self.assertTrue(attempted.wait(2))
        self.assertFalse(self.adapter.value_written.wait(0.05))
        self.adapter.allow_read.set()
        self.assertTrue(self.adapter.value_written.wait(2))

    def test_existing_and_new_channel_queries_share_the_parent_lock(self):
        for existing in (True, False):
            with self.subTest(existing_channel=existing):
                self.adapter = MemoryAdapter()
                driver = TestInstrument(self.adapter)
                if existing:
                    driver.add_child(TestChannel, 1)
                entry = Instrument_Entry(SCPI_Info("COM99", 9600), driver)
                if not existing:
                    driver.add_child(TestChannel, 1)
                self.assertIs(driver.ch_1._io_lock, entry.io.lock)
                self.adapter.block = "CHAN1:VALUE?"
                query = self.launch(lambda: self.assertEqual(driver.ch_1.value, 1.25))
                self.assertTrue(self.adapter.read_started.wait(2))
                attempted = Event()
                def verify():
                    attempted.set()
                    self.assertEqual(driver.ask("*IDN?"), self.adapter.idn)
                verifier = self.launch(verify)
                self.assertTrue(attempted.wait(2))
                self.assertFalse(self.adapter.idn_written.wait(0.05))
                self.adapter.allow_read.set()
                query.join(2)
                verifier.join(2)
                self.assertFalse(query.is_alive() or verifier.is_alive())
                self.assertEqual(self.adapter.writes, ["CHAN1:VALUE?", "*IDN?"])

    def test_other_instruments_remain_available(self):
        self.start_blocked_query()
        other = TestInstrument(MemoryAdapter())
        entry = Instrument_Entry(SCPI_Info("COM99", 9600), other)
        self.assertIsNot(self.entry.io.lock, entry.io.lock)
        worker = self.launch(lambda: self.assertEqual(other.value, 1.25))
        worker.join(1)
        self.assertFalse(worker.is_alive(), "An unrelated instrument must not wait")

    def test_existing_driver_lock_and_identity_are_preserved(self):
        from addons.instruments.RelayMatrix import RelayMatrix
        from addons.instruments.ZNB43 import ZNB43
        for driver_type in (RelayMatrix, ZNB43):
            with self.subTest(driver=driver_type.__name__):
                driver = driver_type(MemoryAdapter(), "Existing driver")
                lock = driver._io_lock
                entry = Instrument_Entry(SCPI_Info("COM99", 9600), driver)
                duplicate = Instrument_Entry(entry.data, driver)
                self.assertIs(entry.scpi_instrument, driver)
                self.assertIs(entry.io.lock, lock)
                self.assertIs(duplicate.io, entry.io)
        # Real PyMeasure channel access also reaches the managed parent query.
        self.assertEqual(driver.ch_1.start_frequency, 1.25)

    def test_transport_exception_releases_the_lock_without_retry(self):
        with patch.object(self.adapter, "_read", side_effect=TimeoutError("no response")):
            with self.assertRaises(TimeoutError):
                self.driver.ask("VALUE?")
        self.assertEqual(self.adapter.writes, ["VALUE?"])
        self.adapter.pending.clear()  # Simulate transport recovery, not an automatic retry.
        worker = self.launch(lambda: self.assertEqual(self.entry.ask_wrapper("VALUE?"), "1.25"))
        worker.join(1)
        self.assertFalse(worker.is_alive())

    def test_close_waits_for_query_and_closed_driver_rejects_later_commands(self):
        self.start_blocked_query()
        closer = self.launch(lambda: self.assertTrue(self.connections._disconnect_entry(self.entry)))
        self.assertEqual(self.adapter.closes, 0)
        self.adapter.allow_read.set()
        closer.join(2)
        self.assertFalse(closer.is_alive())
        self.assertEqual(self.adapter.closes, 1)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.driver.write("OUTPUT OFF")
        self.assertEqual(self.adapter.writes, ["VALUE?"])

    def test_reference_count_allows_queries_but_prevents_premature_close(self):
        self.entry.io.retain()
        self.entry.io.retain()
        try:
            self.entry.io.release()
            self.assertEqual(self.entry.ask_wrapper("*IDN?"), self.adapter.idn)
            self.assertFalse(self.connections._disconnect_entry(self.entry))
            self.assertEqual(self.adapter.closes, 0)
        finally:
            self.entry.io.release()
        self.assertTrue(self.connections._disconnect_entry(self.entry))


class TaskInstrumentLifetimeTests(InstrumentIOFixture):
    def test_task_allows_refresh_and_manual_io_including_during_cleanup(self):
        from addons.loader import registry
        registry.discover("instruments")
        started, cleanup_started, allow_cleanup = Event(), Event(), Event()
        def measure(ctx):
            try:
                started.set()
                ctx.exit_flag.wait(3)
            finally:
                cleanup_started.set()
                if not allow_cleanup.wait(3):
                    raise TimeoutError("Test did not release cleanup")
                ctx.instruments["meter"].write("OUTPUT OFF")
        task = Task.from_spec(TaskSpec("pin", "Pin", "", measure,
                                       instruments={"meter": "keithley2000"}))
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(Config()._data, data_charts_path=directory, backup_schedule=3600):
            task.start()
            try:
                self.assertTrue(started.wait(2))
                verifier = self.launch(self.connections.verify_instruments)
                verifier.join(1)
                self.assertFalse(verifier.is_alive(), "Task waits must not hold an I/O lock")
                self.assertEqual(self.entry.ask_wrapper("VALUE?"), "1.25")
                self.assertEqual(self.adapter.closes, 0)
                # Full refresh scans around the active connection instead of
                # closing it or removing it from the registry.
                with patch.object(self.connections, "_discover_visa_instruments") as visa, \
                     patch.object(self.connections, "_get_available_serial_ports", return_value=[]), \
                     patch.object(self.connections, "_discover_serial_instruments"):
                    self.connections.fetch_all_instruments()
                self.assertEqual(self.connections.instruments_list, [self.entry])
                self.assertIn("COM98", visa.call_args.args[0])
                stopper = self.launch(task.stop)
                self.assertTrue(cleanup_started.wait(2))
                # A genuine IDN mismatch must still preserve the cleanup path.
                self.adapter.idn = "wrong identification"
                self.connections.verify_instruments()
                self.assertEqual(self.connections.instruments_list, [self.entry])
                self.assertEqual(self.adapter.closes, 0)
                allow_cleanup.set()
                stopper.join(3)
                self.assertFalse(stopper.is_alive())
                self.assertIn("OUTPUT OFF", self.adapter.writes)
                self.assertTrue(self.connections._disconnect_entry(self.entry))
            finally:
                allow_cleanup.set()
                task.stop()

    def test_worker_start_failure_releases_connection_pins(self):
        from addons.loader import registry
        registry.discover("instruments")
        task = Task.from_spec(TaskSpec("start_fail", "Start fail", "", lambda ctx: None,
                                       instruments={"meter": "keithley2000"}))
        def fail_start():
            # Pins already exist before Thread.start can run any code.
            self.assertFalse(self.connections._disconnect_entry(self.entry))
            raise RuntimeError("worker did not start")
        with patch("tasks.task.Thread.start", side_effect=fail_start):
            with self.assertRaisesRegex(RuntimeError, "worker did not start"):
                task.start()
        self.assertFalse(task.running)
        self.assertIsNone(task.thread_handle)
        self.assertTrue(self.connections._disconnect_entry(self.entry))


if __name__ == "__main__":
    unittest.main()
