"""Numerical, acquisition and failure-path tests without laboratory hardware."""
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import PropertyMock, patch

from wasic_api import TaskContext


class Source:
    def __init__(self):
        self.enabled = False
        self.source_current = 0
        self.status = 0

    def disable_source(self):
        self.enabled = False

    def enable_source(self):
        self.enabled = True

    def reset(self):
        pass

    def write(self, command):
        pass

    def ask(self, command):
        assert command == ":STAT:MEAS:COND?"
        return str(self.status)

    def check_errors(self):
        return []


class Matrix:
    def __init__(self, source):
        self.source = source
        self.routes = []
        self.route = ()
        self.switch_states = []

    def switch_commute_reset_all(self):
        self.switch_states.append((self.source.enabled, self.source.source_current))
        self.route = ()

    def switch_commute_exclusive(self, *route):
        self.switch_states.append((self.source.enabled, self.source.source_current))
        self.route = route
        self.routes.append(route)


class Meter:
    def __init__(self, source, matrix, ra=(10,), rb=(20,)):
        self.source, self.matrix = source, matrix
        self.ra, self.rb = ra, rb
        self.ch_1 = type("Channel", (), {})()
        self.read_count = 0
        self.on_read = lambda: None

    def reset(self):
        pass

    def trigger_immediately(self):
        pass

    def write(self, command):
        pass

    def ask(self, command):
        assert command == "*OPC?"
        return "1"

    def check_errors(self):
        return []

    @property
    def voltage(self):
        assert self.source.enabled
        index = (len(self.matrix.routes) - 1) // 2
        resistances = self.ra if len(self.matrix.routes) % 2 else self.rb
        self.read_count += 1
        self.on_read()
        return self.source.source_current * resistances[index % len(resistances)] + 23e-6


@unittest.skipUnless(importlib.util.find_spec("pymeasure"), "Project dependencies required")
class VanDerPauwTests(unittest.TestCase):
    def setUp(self):
        from addons.tasks.van_der_pauw import PLUGIN, sheet_resistance, relay_routes
        self.spec, self.solve, self.routes = PLUGIN, sheet_resistance, relay_routes
        self.source = Source()
        self.matrix = Matrix(self.source)
        self.meter = Meter(self.source, self.matrix)

    def context(self, **parameters):
        values = {"relay_settle_s": 0, "current_settle_s": 0,
                  "overrange_retry_delay_s": 0, **parameters}
        return TaskContext({"source": self.source, "matrix": self.matrix, "meter": self.meter},
                           self.spec.parse_parameters(values), [], Event())

    def assert_off(self):
        self.assertFalse(self.source.enabled)
        self.assertEqual(self.source.source_current, 0)
        self.assertEqual(self.matrix.route, ())

    def test_symmetric_solution_over_scales(self):
        for resistance in (1e-12, 1, 1e12):
            self.assertAlmostEqual(self.solve(resistance, resistance) / resistance,
                                   math.pi / math.log(2), places=12)

    def test_asymmetric_solution_and_interchange(self):
        for ra, rb in ((10, 20), (1e-6, 1), (1e-12, 1), (1e-20, 1)):
            rs = self.solve(ra, rb)
            self.assertAlmostEqual(math.exp(-math.pi * ra / rs) + math.exp(-math.pi * rb / rs), 1, places=14)
            self.assertEqual(rs, self.solve(rb, ra))
            residual = math.expm1(-math.pi * min(ra, rb) / rs) + math.exp(-math.pi * max(ra, rb) / rs)
            self.assertLess(abs(residual), 1e-12 * abs(math.expm1(-math.pi * min(ra, rb) / rs)))

    def test_solver_rejects_invalid_resistances(self):
        for value in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                self.solve(value, 1)

    def test_one_shot_reversal_routes_and_saved_raw(self):
        ctx = self.context(samples_per_polarity=2)
        self.spec.run(ctx)
        self.assertEqual(self.matrix.routes, [("c1", "d2", "a4", "b3"), ("c2", "d3", "a1", "b4")])
        self.assertEqual(self.meter.read_count, 8)
        self.assertAlmostEqual(ctx.data[0].y_series.processed[0], 10)
        self.assertAlmostEqual(ctx.data[1].y_series.processed[0], 20)
        self.assertAlmostEqual(ctx.data[2].y_series.processed[0], self.solve(10, 20))
        self.assertEqual(len(ctx.data), 3)
        saved = json.loads(json.dumps(ctx.data[0].to_dict()))
        record = saved["y"]["raw"][0]
        self.assertEqual(len(record["positive_V"]), 2)
        self.assertEqual(len(record["negative_V"]), 2)
        self.assertEqual(record["relays"], ["c1", "d2", "a4", "b3"])
        self.assert_off()

    def test_repeated_acquisition_produces_only_three_histograms(self):
        self.meter.ra, self.meter.rb = (10, 11, 12), (20, 22, 24)
        ctx = self.context(repetitions=3)
        self.spec.run(ctx)
        self.assertEqual(len(ctx.data), 3)
        for chart in ctx.data:
            self.assertEqual(chart.config.custom_type, "histogram")
            self.assertEqual(chart.x_series.processed, [1, 2, 3])
        for actual, expected in zip(ctx.data[0].y_series.processed, (10, 11, 12)):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(ctx.data[1].y_series.processed, (20, 22, 24)):
            self.assertAlmostEqual(actual, expected)
        for index, value in enumerate(ctx.data[2].y_series.processed):
            self.assertAlmostEqual(value, self.solve(10 + index, 20 + 2 * index))
        self.assert_off()

    def test_custom_mapping(self):
        ctx = self.context(current_hi_group="D", current_lo_group="c", voltage_hi_group="b",
                           voltage_lo_group="a", contact_1=8, contact_2=7, contact_3=6, contact_4=5)
        self.spec.run(ctx)
        self.assertEqual(self.matrix.routes, [("d8", "c7", "b5", "a6"), ("d7", "c6", "b8", "a5")])

    def test_source_stays_enabled_across_reversals_routes_and_repetitions(self):
        ctx = self.context(repetitions=3)
        with patch.object(self.source, "enable_source", wraps=self.source.enable_source) as enable, \
             patch.object(self.source, "disable_source", wraps=self.source.disable_source) as disable:
            self.spec.run(ctx)
        self.assertEqual(enable.call_count, 1)
        # Two initialization OFF commands and the final cleanup only.
        self.assertEqual(disable.call_count, 3)
        self.assertEqual(self.matrix.switch_states[:-1],
                         [(True, .0001)] * 2 + [(True, -.0001)] * 10)
        self.assertEqual(self.matrix.switch_states[-1], (False, 0))
        self.assert_off()

    def test_open_path_compliance_is_checked_only_after_reconnection_and_settling(self):
        from addons.tasks.van_der_pauw import _wait
        ctx = self.context(relay_settle_s=.001, current_settle_s=.002)
        settled = False

        def wait(context, seconds=0):
            nonlocal settled
            if seconds == .002:
                settled = True
            _wait(context)  # No real delays in this test.

        def open_path():
            nonlocal settled
            settled = False
            self.source.status = 8
            self.matrix.route = ()

        def status(command):
            self.assertTrue(self.matrix.route)
            self.assertTrue(settled)
            return "0"

        with patch.object(self.matrix, "switch_commute_reset_all", side_effect=open_path), \
             patch.object(self.source, "ask", side_effect=status), \
             patch("addons.tasks.van_der_pauw._wait", side_effect=wait):
            self.spec.run(ctx)
        self.assertEqual(len(ctx.data[2].y_series.processed), 1)
        self.assert_off()

    def test_bad_mapping_never_touches_hardware(self):
        for values in ({"contact_2": 1}, {"current_hi_group": "b"}, {"current_hi_group": "a1;*RST"}):
            ctx = self.context(**values)
            with patch.object(self.source, "disable_source") as disable, self.assertRaises(ValueError):
                self.spec.run(ctx)
            disable.assert_not_called()

    def test_bad_parameters(self):
        for values in ({"repetitions": 0}, {"current_A": 0}, {"current_A": .2},
                       {"nplc": 51}, {"samples_per_polarity": 0}, {"relay_settle_s": -1},
                       {"voltage_range_V": .05}):
            with self.assertRaises(ValueError):
                self.spec.parse_parameters(values)

    def test_persistent_compliance_discards_all_cycles_and_continues(self):
        self.source.status = 8
        ctx = self.context(repetitions=3)
        with self.assertLogs("addons.tasks.van_der_pauw", level="WARNING") as logs:
            self.spec.run(ctx)
        self.assertEqual(len(self.matrix.routes), 3)
        self.assertEqual(len(logs.output), 3)
        self.assertEqual(self.meter.read_count, 0)
        for chart in ctx.data:
            self.assertEqual(chart.y_series.processed, [])
        records = ctx.data[0].y_series.raw
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertFalse(record["accepted"])
            self.assertEqual(record["discard_reason"], "voltage_compliance")
            self.assertNotIn("resistance_ohm", record)
        self.assert_off()

    def test_compliance_message_identifies_settings_and_route(self):
        self.source.status = 8
        ctx = self.context()
        with self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        record = json.loads(json.dumps(ctx.data[0].to_dict()))["y"]["raw"][0]
        for detail in ("voltage compliance reached", "0x8", "0.0001 A", "1 V",
                       "c1 d2 a4 b3", "10000 ohm"):
            self.assertIn(detail, record["source_error"])
        self.assertEqual(self.meter.read_count, 0)
        self.assert_off()

    def test_compliance_in_rb_discards_ra_and_recovers_next_cycle(self):
        ctx = self.context(repetitions=3)
        # Compliance appears after the first RB reading, after RA completed.
        def status(command):
            return "8" if len(self.matrix.routes) == 2 and self.meter.read_count >= 3 else "0"
        with patch.object(self.source, "ask", side_effect=status), \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        self.assertEqual(len(self.matrix.routes), 6)
        for chart in ctx.data:
            self.assertEqual(chart.x_series.processed, [2, 3])
        self.assertAlmostEqual(ctx.data[2].y_series.processed[-1], self.solve(10, 20))
        for chart in ctx.data[:2]:
            record = chart.y_series.raw[0]
            self.assertFalse(record["accepted"])
            self.assertNotIn("resistance_ohm", record)
        self.assertEqual(len(ctx.data[1].y_series.raw[0]["positive_V"]), 1)
        self.assert_off()

    def test_compliance_with_other_faults_still_aborts(self):
        for status in (9, 12):
            self.source.status = status
            ctx = self.context(repetitions=3)
            with self.assertRaises(RuntimeError):
                self.spec.run(ctx)
            self.assertEqual(ctx.data[2].y_series.processed, [])
            self.assert_off()

    def test_interlock_permitted_bit_does_not_abort_measurement(self):
        self.source.status = 2
        ctx = self.context()
        self.spec.run(ctx)
        self.assertEqual(len(ctx.data[2].y_series.processed), 1)
        self.assert_off()

    def test_cancellation_keeps_raw_but_discards_incomplete_cycle(self):
        ctx = self.context(repetitions=3)
        self.meter.on_read = ctx.exit_flag.set
        self.spec.run(ctx)
        self.assertEqual(ctx.data[2].y_series.processed, [])
        self.assertEqual(len(ctx.data[0].y_series.raw[0]["positive_V"]), 1)
        self.assert_off()

    def test_cancel_during_settling(self):
        ctx = self.context(current_settle_s=10)
        with patch.object(self.source, "enable_source", side_effect=ctx.exit_flag.set):
            self.spec.run(ctx)
        self.assertEqual(self.meter.read_count, 0)
        self.assert_off()

    def test_read_failure_still_disables_source_and_opens_relays(self):
        ctx = self.context()
        self.meter.on_read = lambda: (_ for _ in ()).throw(TimeoutError("VISA timeout"))
        with self.assertRaises(TimeoutError):
            self.spec.run(ctx)
        self.assertEqual(self.meter.read_count, 1)
        self.assert_off()

    def test_invalid_voltages_are_rejected(self):
        for value in (math.nan, math.inf, 9.9e37):
            self.meter.ra = (value,)
            ctx = self.context()
            with self.assertRaises((ValueError, RuntimeError)):
                self.spec.run(ctx)
            self.assertEqual(ctx.data[2].y_series.processed, [])
            self.assert_off()

    def test_resistance_retains_existing_magnitude_convention(self):
        self.meter.ra = (-10,)
        ctx = self.context()
        self.spec.run(ctx)
        self.assertAlmostEqual(ctx.data[0].y_series.processed[0], 10)
        self.assert_off()

    def test_transient_overflows_recover_without_changing_route_or_polarity(self):
        ctx = self.context()
        readings = iter((9.9e37, 9.9e37, .001023, -.000977, .002023, -.001977))
        states = []
        def read():
            states.append((self.matrix.route, self.source.source_current, self.source.enabled))
            return next(readings)
        with patch.object(Meter, "voltage", new_callable=PropertyMock, side_effect=read), \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        self.assertEqual(states[:3], [(('c1', 'd2', 'a4', 'b3'), .0001, True)] * 3)
        record = ctx.data[0].y_series.raw[0]
        self.assertEqual(record["positive_V"], [.001023])
        self.assertEqual(len(record["invalid_readings"]), 2)
        json.dumps(record, allow_nan=False)
        self.assertAlmostEqual(ctx.data[2].y_series.processed[0], self.solve(10, 20))
        self.assert_off()

    def test_persistent_overflow_exhausts_retries_and_preserves_prior_cycles(self):
        ctx = self.context(repetitions=3, overrange_retries=2)
        values = [.001023, -.000977, .002023, -.001977, 9.9e37, 9.9e37, 9.9e37]
        with patch.object(Meter, "voltage", new_callable=PropertyMock, side_effect=values) as read, \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"), \
             self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
            self.spec.run(ctx)
        self.assertEqual(read.call_count, 7)
        self.assertEqual(ctx.data[2].x_series.processed, [1])
        self.assertEqual(len(ctx.data[0].y_series.raw[-1]["invalid_readings"]), 3)
        self.assertEqual(ctx.data[0].y_series.raw[-1]["positive_V"], [])
        self.assert_off()

    def test_overflow_on_negative_polarity_keeps_positive_samples(self):
        ctx = self.context()
        values = [.001023, 9.9e37, -.000977, .002023, -.001977]
        with patch.object(Meter, "voltage", new_callable=PropertyMock, side_effect=values), \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        record = ctx.data[0].y_series.raw[0]
        self.assertEqual(record["positive_V"], [.001023])
        self.assertEqual(record["negative_V"], [-.000977])
        self.assertEqual(record["invalid_readings"][0]["polarity"], "negative_V")
        self.assertAlmostEqual(ctx.data[0].y_series.processed[0], 10)
        self.assert_off()

    def test_overflow_retry_can_be_disabled(self):
        ctx = self.context(overrange_retries=0)
        with patch.object(Meter, "voltage", new_callable=PropertyMock, return_value=9.9e37) as read, \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"), \
             self.assertRaisesRegex(RuntimeError, "after 1 attempts"):
            self.spec.run(ctx)
        self.assertEqual(read.call_count, 1)
        self.assert_off()

    def test_stop_during_overflow_wait_does_not_retry(self):
        ctx = self.context(overrange_retry_delay_s=10)
        def read():
            ctx.exit_flag.set()
            return 9.9e37
        with patch.object(Meter, "voltage", new_callable=PropertyMock, side_effect=read) as voltage, \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        self.assertEqual(voltage.call_count, 1)
        self.assertEqual(ctx.data[2].y_series.processed, [])
        self.assert_off()

    def test_compliance_during_overflow_prevents_further_reads(self):
        ctx = self.context()
        def read():
            self.source.status = 8
            return 9.9e37
        with patch.object(Meter, "voltage", new_callable=PropertyMock, side_effect=read) as voltage, \
             self.assertLogs("addons.tasks.van_der_pauw", level="WARNING"):
            self.spec.run(ctx)
        self.assertEqual(voltage.call_count, 1)
        self.assertFalse(ctx.data[0].y_series.raw[0]["accepted"])
        self.assert_off()

    def test_configuration_waits_for_idle_opc_before_reading(self):
        ctx = self.context()
        with patch.object(self.meter, "write") as write, \
             patch.object(self.meter, "ask", return_value="1") as ask:
            self.spec.run(ctx)
        self.assertEqual([call.args[0] for call in write.call_args_list],
                         [":INIT:CONT OFF", ":ABOR", ":SAMP:COUN 1"])
        self.assertEqual(ask.call_count, 2)
        self.assertEqual(self.meter.trigger_count, 1)
        self.assert_off()

    def test_opc_failure_still_cleans_up(self):
        ctx = self.context()
        with patch.object(self.meter, "ask", return_value="0"), \
             self.assertRaisesRegex(RuntimeError, "reset did not complete"):
            self.spec.run(ctx)
        self.assertEqual(self.meter.read_count, 0)
        self.assert_off()

    def test_configuration_error_still_cleans_up(self):
        ctx = self.context()
        with patch.object(self.meter, "check_errors", return_value=[[-222, "Data out of range"]]):
            with self.assertRaisesRegex(RuntimeError, "configuration"):
                self.spec.run(ctx)
        self.assertEqual(self.meter.read_count, 0)
        self.assert_off()

    def test_cleanup_failure_does_not_commute_an_enabled_source(self):
        from addons.tasks.van_der_pauw import _cleanup
        self.source.enabled = True
        self.matrix.route = ("a1", "b2", "c4", "d3")
        with patch.object(self.source, "disable_source", side_effect=TimeoutError("Output off failed")), \
             self.assertLogs("addons.tasks.van_der_pauw", level="ERROR"), \
             self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            _cleanup(self.source, self.matrix, 0)
        self.assertEqual(self.matrix.route, ("a1", "b2", "c4", "d3"))
        self.assertEqual(self.source.source_current, 0)

    def test_all_charts_render_and_survive_json_roundtrip(self):
        from tasks import ChartData
        from webapp import make_plotly_figure
        ctx = self.context(repetitions=3)
        self.spec.run(ctx)
        for chart in ctx.data:
            restored = ChartData.from_dict(json.loads(json.dumps(chart.to_dict())))
            figure = make_plotly_figure(restored)
            self.assertEqual(figure.data[0].type, "histogram")
            self.assertEqual(list(figure.data[0].x), restored.y_series.processed)
            self.assertEqual(restored.y_series.processed, chart.y_series.processed)
            self.assertEqual(restored.y_series.raw, chart.y_series.raw)

    def test_one_shot_runtime_saves_results_and_can_restart(self):
        from config import Config
        from tasks import Task, Tasks
        config, manager = Config(), Tasks()
        old_config, old_tasks, old_running = config._data, manager._tasks_list, manager._is_running
        task = Task.from_spec(self.spec)
        task.parameters = self.context(repetitions=2).parameters
        try:
            with tempfile.TemporaryDirectory() as directory:
                config._data = dict(old_config, data_charts_path=directory, backup_schedule=3600)
                manager._tasks_list, manager._is_running = [task], None
                with patch.object(task, "resolve_instruments", return_value=self.context().instruments):
                    for _ in range(2):
                        manager.run_task(task.name)
                        worker, processor = task.thread_handle, task.data_processor
                        worker.join(5)
                        processor.join(5)
                        self.assertFalse(worker.is_alive())
                        self.assertFalse(processor.is_alive())
                        self.assertFalse(task.running)
                        self.assertIsNone(manager._is_running)
                        self.assertEqual(task.data, [])
                        self.assert_off()
                saved = list(Path(directory).glob("*.json"))
                self.assertTrue(saved)
                payload = json.loads(saved[0].read_text())
                self.assertEqual(len(payload["charts"]), 3)
                self.assertEqual(len(payload["charts"][2]["y"]["processed"]), 2)
                self.assertTrue(all(chart["config"]["custom_type"] == "histogram"
                                    for chart in payload["charts"]))
        finally:
            manager.stop_task()
            config._data, manager._tasks_list, manager._is_running = old_config, old_tasks, old_running

    def test_pymeasure_drivers_execute_the_acquisition(self):
        from pymeasure.adapters import Adapter
        from pymeasure.instruments.keithley import Keithley2182, Keithley6221
        from addons.instruments.RelayMatrix import RelayMatrix

        class ScriptedAdapter(Adapter):
            def __init__(self, voltages=(), handshake=False):
                super().__init__()
                self.handshake = handshake
                self.pending = []
                self.voltages = iter(voltages)
                self.commands = []

            def _write(self, command, **kwargs):
                if self.handshake:
                    assert not self.pending, "Command sent before consuming handshake/response"
                    self.pending = ["1", "OK"] if command.upper() == "*OPC?" else ["OK"]
                self.commands.append(command)

            def _read(self, **kwargs):
                if self.handshake:
                    return self.pending.pop(0)
                command = self.commands[-1].upper()
                if "READ?" in command:
                    return str(next(self.voltages))
                if "ERR?" in command:
                    return '0,"No error"'
                if "COND?" in command:
                    return "0"
                if "OPC?" in command:
                    return "1"
                raise AssertionError(f"Unexpected query {command}")

        src_adapter, meter_adapter, relay_adapter = ScriptedAdapter(), ScriptedAdapter((.001023, -.000977, .002023, -.001977)), ScriptedAdapter(handshake=True)
        ctx = self.context()
        ctx.instruments = {"source": Keithley6221(src_adapter), "meter": Keithley2182(meter_adapter),
                           "matrix": RelayMatrix(relay_adapter, "Matrix")}
        self.spec.run(ctx)
        self.assertAlmostEqual(ctx.data[2].y_series.processed[0], self.solve(10, 20))
        self.assertIn("switch:commute:exclusive c1 d2 a4 b3", relay_adapter.commands)
        self.assertIn(":SENS:VOLT:NPLC 5", meter_adapter.commands)
        self.assertEqual(src_adapter.commands[-2:], ["OUTPUT OFF", ":SOUR:CURR 0"])


if __name__ == "__main__":
    unittest.main()
