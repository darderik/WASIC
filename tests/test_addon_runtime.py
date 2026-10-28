import importlib.util
import tempfile
import time
import unittest
from threading import Thread
from unittest.mock import patch

from wasic_api import InstrumentSpec, ParameterSpec, TaskContext, TaskSpec


@unittest.skipUnless(importlib.util.find_spec("pymeasure"), "Project dependencies required")
class AddonRuntimeTests(unittest.TestCase):
    def setUp(self):
        from addons.loader import load_addons, registry
        from connections import Connections
        from config import Config
        from tasks import Task, Tasks
        from instruments import Instrument_Entry, SCPI_Info
        self.registry = load_addons()
        self.connections = Connections()
        self.tasks = Tasks()
        self.Task = Task
        self.Entry = Instrument_Entry
        self.Info = SCPI_Info
        self.previous_entries = self.connections.instruments_list
        self.previous_tasks = self.tasks._tasks_list
        self.connections.instruments_list = []
        self.tasks._tasks_list = []
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config()
        self.previous_config = self.config._data
        self.config._data = dict(self.previous_config, data_charts_path=self.temp.name,
                                 backup_schedule=3600)

    def tearDown(self):
        self.tasks.stop_task()
        self.connections.instruments_list = self.previous_entries
        self.tasks._tasks_list = self.previous_tasks
        self.config._data = self.previous_config
        self.temp.cleanup()

    def test_bootstrap_is_complete_and_idempotent(self):
        from addons.loader import load_addons
        self.assertFalse(self.registry.errors)
        self.assertEqual(set(self.registry.tasks), {"thermal_tracking", "test_charts", "van_der_pauw"})
        self.assertEqual(len(self.registry.instruments), 7)
        self.tasks.load_specs(self.registry.tasks.values())
        task = self.tasks.get_task("Test Charts")
        task.parameters["update_interval"] = 0.02
        load_addons()
        self.assertEqual(len(self.tasks._tasks_list), 3)
        self.assertIs(self.tasks.get_task("Test Charts"), task)
        self.assertEqual(task.parameters["update_interval"], 0.02)

    def test_driver_recognition_factory_and_generic_fallback(self):
        from pymeasure.adapters import FakeAdapter
        for spec in self.registry.instruments.values():
            info = self.connections._build_visa_info("USB::TEST", spec.idn_keywords[0])
            self.assertIsNotNone(info)
            with patch.object(self.connections, "_create_visa_adapter", return_value=FakeAdapter()), \
                 patch("addons.instruments.TBS1052C.time.sleep"):
                entry = self.connections._create_instrument_entry(info)
            self.assertIsNotNone(entry, spec.id)
        self.config._data["instr_aliases"] = ["generic-model"]
        self.assertEqual(self.connections._build_serial_info("COM1", "generic-model", 9600).alias,
                         "generic-model")
        self.assertIsNone(self.connections._build_visa_info("USB::TEST", "unknown"))

    def test_named_instrument_injection_and_ambiguity(self):
        meter = object()
        entry = self.Entry(self.Info("COM1", 9600, idn="KEITHLEY,Model 2000,123"), meter)
        self.connections.instruments_list = [entry]
        captured = []
        task = self.Task.from_spec(TaskSpec(
            "capture", "Capture", "", captured.append,
            instruments={"meter": "keithley2000"},
            parameters={"interval": ParameterSpec(float, 1.0)},
        ))
        self.assertTrue(task.has_instruments())
        context = TaskContext(task.resolve_instruments(), task.parameters, task.data, task.exit_flag)
        task._execute(context)
        self.assertIs(captured[0].instruments["meter"], meter)
        self.assertTrue(task.exit_flag.is_set())
        self.connections.instruments_list.append(entry)
        self.assertFalse(task.has_instruments())
        self.connections.instruments_list = []
        self.assertFalse(task.has_instruments())

    def test_chart_example_stop_restart_and_persistence(self):
        from pathlib import Path
        task = self.Task.from_spec(self.registry.tasks["test_charts"])
        task.parameters["update_interval"] = 0.01
        self.tasks.add_task(task)
        for _ in range(2):
            self.tasks.run_task(task.name)
            deadline = time.monotonic() + 3
            while len(task.data) < 4 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(task.data), 4)
            worker = task.thread_handle
            processor = task.data_processor
            stopper = Thread(target=self.tasks.stop_task, daemon=True)
            stopper.start()
            stopper.join(5)
            self.assertFalse(stopper.is_alive(), "Stop must not deadlock")
            self.assertFalse(worker.is_alive())
            self.assertFalse(processor.is_alive())
            self.assertEqual(task.data, [])
            self.assertIsNone(self.tasks._is_running)
        from tasks.chart_io import load_charts_file
        saved = [path for path in Path(self.temp.name).glob("*.csv")
                 if not path.name.endswith(".meta.csv")]
        self.assertTrue(saved)
        self.assertEqual(len(load_charts_file(saved[0])), 4)

    def test_return_and_exception_finish_the_run(self):
        def fail(ctx):
            raise RuntimeError("measurement failed")
        for function in (lambda ctx: None, fail):
            task = self.Task.from_spec(TaskSpec("finish", "Finish", "", function))
            self.tasks._tasks_list = [task]
            with patch("tasks.task.logger.exception"):
                self.tasks.run_task(task.name)
                processor = task.data_processor
                processor.join(5)
            self.assertFalse(processor.is_alive())
            self.assertIsNone(self.tasks._is_running)
            self.assertFalse(task.running)

    @unittest.skipUnless(importlib.util.find_spec("streamlit") and importlib.util.find_spec("plotly"),
                         "UI dependencies required")
    def test_task_page_renders_and_saves_typed_parameters(self):
        from streamlit.testing.v1 import AppTest
        self.tasks.load_specs(self.registry.tasks.values())
        app = AppTest.from_file("webapp/pages/tasks.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Test Charts")
        interval = next(widget for widget in app.number_input if widget.label == "update_interval")
        interval.set_value(0.25)
        app.checkbox[0].set_value(False)
        next(button for button in app.button if button.label == "Save parameters").click()
        app.run()
        self.assertFalse(app.exception)
        parameters = self.tasks.get_task("Test Charts").parameters
        self.assertEqual(parameters["update_interval"], 0.25)
        self.assertIs(parameters["merge_chart_files"], False)

    def test_bad_parameter_never_starts_worker(self):
        task = self.Task.from_spec(self.registry.tasks["test_charts"])
        task.parameters["update_interval"] = -1
        with self.assertRaises(ValueError):
            task.start()
        self.assertIsNone(task.thread_handle)
        self.assertFalse(task.running)


if __name__ == "__main__":
    unittest.main()
