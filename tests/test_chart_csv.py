"""Persistence tests using only the standard library (no instrument drivers)."""
import csv
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


# Load the data-only modules in an isolated package: tasks.__init__ also
# initializes the instrument runtime, which is unnecessary for these tests.
package_name = "_wasic_csv_tests"
spec = importlib.util.spec_from_loader(package_name, loader=None, is_package=True)
package = importlib.util.module_from_spec(spec)
package.__path__ = [str(Path(__file__).resolve().parents[1] / "tasks")]
sys.modules[package_name] = package
structures = importlib.import_module(f"{package_name}.structures")
chart_io = importlib.import_module(f"{package_name}.chart_io")
ChartData = structures.ChartData


class ChartCsvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "charts.csv"

    def chart(self):
        chart = ChartData(name="Sheet resistance")
        chart.configure_x_axis("Time", "s")
        chart.configure_y_axis("R_s", "ohm", "log")
        chart.config.custom_type = "histogram"
        chart.config.start_index = 1
        chart.x_series.processed = [0, 1, 2]
        chart.y_series.processed = [3.141592653589793, 1e-30]
        chart.y_series.raw = [{"voltage": [1e-8, None], "valid": True}]
        return chart

    def test_tabular_headers_precision_and_roundtrip(self):
        chart = self.chart()
        chart.save_csv_atomic(self.path)
        with self.path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[0], ["Time(s)", "R_s(ohm)", "Time_raw(s)",
                                   "R_s_raw.voltage.0()", "R_s_raw.voltage.1()", "R_s_raw.valid()"])
        self.assertEqual(float(rows[1][1]), chart.y_series.processed[0])
        self.assertEqual(rows[3][1], "")
        restored, = chart_io.load_charts_file(self.path)
        self.assertEqual(restored.to_dict(), chart.to_dict())
        self.assertEqual(restored.y_series.meta.scale, "log")
        with Path(str(self.path) + ".meta.csv").open(newline="", encoding="utf-8") as stream:
            metadata_rows = list(csv.reader(stream))
        self.assertEqual(metadata_rows[0], ["Path()", "Type()", "Value()"])
        self.assertEqual({path.suffix for path in self.path.parent.iterdir()}, {".csv"})

    def test_merged_duplicate_names_and_headers(self):
        charts = [self.chart(), self.chart()]
        charts[1].y_series.processed = [10]
        chart_io.save_charts_csv(charts, self.path, metadata={"task_name": "test"})
        with self.path.open(newline="") as stream:
            headers = next(csv.reader(stream))
        self.assertEqual(len(headers), len(set(headers)))
        self.assertTrue(all(header.endswith(")") for header in headers))
        restored = chart_io.load_charts_file(self.path)
        self.assertEqual([c.to_dict() for c in restored], [c.to_dict() for c in charts])

    def test_raw_exclusion(self):
        for config_raw, include_raw in ((False, True), (True, False)):
            chart = self.chart()
            chart.config.include_raw_on_save = config_raw
            chart_io.save_charts_csv([chart], self.path, include_raw=include_raw)
            restored, = chart_io.load_charts_file(self.path)
            self.assertEqual(restored.y_series.raw, [])
            self.assertEqual(restored.config.include_raw_on_save, config_raw)
            with self.path.open(newline="") as stream:
                self.assertEqual(len(next(csv.reader(stream))), 2)

    def test_raw_structures_and_scalar_types(self):
        chart = self.chart()
        chart.y_series.raw = [
            {"a/b~": [None, "", "True", True, 10, 1e-30], "nested": {"": "a,b\nc"}},
            {}, [], None, "", False, 3, 4.5,
            {"different": [[], {}, "None"]},
        ]
        chart.save_csv_atomic(self.path)
        restored, = chart_io.load_charts_file(self.path)
        self.assertEqual(restored.y_series.raw, chart.y_series.raw)
        for actual, expected in zip(restored.y_series.raw, chart.y_series.raw):
            self.assertIs(type(actual), type(expected))

    def test_raw_only_empty_containers_preserve_sample_count(self):
        chart = ChartData()
        chart.y_series.raw = [{}, [], {}]
        chart.save_csv_atomic(self.path)
        restored, = chart_io.load_charts_file(self.path)
        self.assertEqual(restored.y_series.raw, chart.y_series.raw)

    def test_metadata_settings_and_descriptions(self):
        chart = self.chart()
        chart.config.schema_version = 2
        chart.config.atomic_save = False
        chart.x_series.meta.description = "Elapsed time, in seconds\nfrom the start"
        chart.save_csv_atomic(self.path)
        restored, = chart_io.load_charts_file(self.path)
        self.assertEqual(restored.config, chart.config)
        self.assertEqual(restored.x_series.meta, chart.x_series.meta)

    def test_missing_samples_and_nonfinite_numbers(self):
        chart = self.chart()
        chart.y_series.processed = [None, float("nan"), float("inf")]
        chart.save_csv_atomic(self.path)
        restored, = chart_io.load_charts_file(self.path)
        self.assertIsNone(restored.y_series.processed[0])
        self.assertTrue(math.isnan(restored.y_series.processed[1]))
        self.assertTrue(math.isinf(restored.y_series.processed[2]))

    def test_empty_chart_and_empty_collection(self):
        for charts in ([ChartData()], []):
            chart_io.save_charts_csv(charts, self.path)
            restored = chart_io.load_charts_file(self.path)
            self.assertEqual(len(restored), len(charts))

    def test_plain_csv_and_italian_decimal_separator(self):
        for text in ("Time(s),R_s(ohm)\n0,1.5\n1,\n", "Time(s);R_s(ohm)\n0;1,5\n1;\n"):
            self.path.write_text(text)
            chart, = chart_io.load_charts_file(self.path)
            self.assertEqual(chart.x_series.processed, [0, 1])
            self.assertEqual(chart.y_series.processed, [1.5])
            self.assertEqual(chart.y_series.meta.unit, "ohm")

    def test_non_csv_files_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "must use the .csv extension"):
            chart_io.load_charts_file(self.path.with_suffix(".txt"))

    def test_modified_csv_is_detected(self):
        self.chart().save_csv_atomic(self.path)
        with self.path.open("a") as stream:
            stream.write("0,0,,,,\n")
        with self.assertRaisesRegex(ValueError, "different saves"):
            chart_io.load_charts_file(self.path)

    def test_empty_csv_reports_error(self):
        self.path.touch()
        with self.assertRaisesRegex(ValueError, "no column headers"):
            chart_io.load_charts_file(self.path)

    def test_atomic_failure_keeps_previous_file_and_cleans_temporary(self):
        self.chart().save_csv_atomic(self.path)
        previous = self.path.read_bytes()
        with patch.object(chart_io.os, "replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.chart().save_csv_atomic(self.path)
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
