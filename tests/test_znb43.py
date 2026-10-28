"""ZNB43 SCPI protocol and WASIC integration tests; no hardware required."""

import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch

if importlib.util.find_spec("pymeasure"):
    from pymeasure.adapters import FakeAdapter
    from pymeasure.test import expected_protocol

    from addons.instruments.ZNB43 import PLUGIN, ZNB43


@unittest.skipUnless(importlib.util.find_spec("pymeasure"), "Project dependencies required")
class ZNB43Tests(unittest.TestCase):
    def test_construction_and_channel_access_do_not_communicate(self):
        with expected_protocol(ZNB43, []) as vna:
            self.assertIs(vna.ch_1, vna.channel())
            self.assertIs(vna.channel(2), vna.channel(2))
            self.assertEqual(vna.channel(2).id, 2)
            self.assertTrue(vna.properties_list)

    def test_settings_address_measurement_channels_and_global_rf(self):
        with expected_protocol(ZNB43, [
            ("SENS2:FREQ:STAR 100000", None),
            ("SENS2:FREQ:STOP 43500000000", None),
            ("SENS2:SWE:POIN 401", None),
            ("SENS2:SWE:POIN?", "401"),
            ("SENS2:SWE:TYPE LOG", None),
            ("SENS2:SWE:TYPE?", "LOG"),
            ("SENS2:BAND 1000", None),
            ("SOUR2:POW -20", None),
            ("SOUR2:POW?", "-2.000000E+01"),
            ("TRIG2:SOUR EXT", None),
            ("CALC2:FORM MLOG", None),
            ("OUTP 0", None),
            ("OUTP?", "0"),
            ("OUTP 1", None),
            ("OUTP?", "1"),
        ]) as vna:
            ch = vna.channel(2)
            ch.start_frequency = 100e3
            ch.stop_frequency = 43.5e9
            ch.sweep_points = 401
            self.assertEqual(ch.sweep_points, 401)
            ch.sweep_type = "LOG"
            self.assertEqual(ch.sweep_type, "LOG")
            ch.if_bandwidth = 1000
            ch.source_power = -20
            self.assertEqual(ch.source_power, -20)
            ch.trigger_source = "EXT"
            ch.trace_format = "MLOG"
            vna.rf_enabled = False
            self.assertIs(vna.rf_enabled, False)
            vna.rf_enabled = True
            self.assertIs(vna.rf_enabled, True)

    def test_full_average_cycle_and_complex_logarithmic_trace(self):
        with expected_protocol(ZNB43, [
            ("CALC1:PAR:SDEF 'Transmission','S21'", None),
            ("CALC1:PAR:SEL 'Transmission'", None),
            ("SENS1:AVER:COUN 3", None),
            ("SENS1:AVER:STAT 1", None),
            ("SENS1:SWE:COUN 3", None),
            ("SENS1:AVER:CLE", None),
            ("INIT1:CONT 0", None),
            ("INIT1:IMM", None),
            ("*OPC?", "1"),
            ("CALC1:PAR:SEL 'Transmission'", None),
            ("FORM ASC", None),
            ("CALC1:DATA:STIM?", "1e6,1e7,1e8"),
            ("CALC1:DATA? SDAT", "1,0,0,-1,-0.5,0.25"),
        ]) as vna:
            ch = vna.ch_1
            ch.define_trace("Transmission", "s21")
            ch.average_count = 3
            ch.averaging_enabled = True
            ch.sweep_count = 3
            ch.clear_averages()
            ch.sweep()
            stimulus, values = ch.read_trace("Transmission")
            self.assertEqual(stimulus, [1e6, 1e7, 1e8])
            self.assertEqual(values, [1+0j, -1j, -0.5+0.25j])

    def test_async_sweep_does_not_wait_or_change_trigger_and_counts(self):
        with expected_protocol(ZNB43, [
            ("INIT2:CONT 0", None), ("INIT2:IMM", None),
        ]) as vna:
            vna.channel(2).sweep(wait=False)

    def test_formatted_polar_data_preserves_both_values_per_point(self):
        with expected_protocol(ZNB43, [
            ("FORM ASC", None),
            ("CALC1:DATA? FDAT", "1,0,0.5,90"),
        ]) as vna:
            self.assertEqual(vna.ch_1.read_formatted_data(), [1, 0, 0.5, 90])

    def test_trace_names_escape_quotes_and_preserve_braces(self):
        with expected_protocol(ZNB43, [
            ("CALC2:PAR:SEL 'DUT''s {ch} trace'", None),
        ]) as vna:
            vna.channel(2).select_trace("DUT's {ch} trace")

    def test_malformed_trace_responses_are_rejected(self):
        for stimulus, data in [("1e6,2e6", "1,2,3"), ("1e6", "1,2,3,4"),
                                ("", "1,2"), ("1e6", ""), ("1e6", "bad,0")]:
            with self.subTest(stimulus=stimulus, data=data):
                with expected_protocol(ZNB43, [
                    ("FORM ASC", None),
                    ("CALC1:DATA:STIM?", stimulus),
                    *(([("CALC1:DATA? SDAT", data)]) if stimulus else []),
                ]) as vna:
                    with self.assertRaises(ValueError):
                        vna.ch_1.read_trace()

    def test_invalid_settings_are_rejected_before_io(self):
        cases = [
            ("start_frequency", 99999), ("stop_frequency", 43.6e9),
            ("center_frequency", float("nan")), ("frequency_span", -1),
            ("sweep_points", 0), ("sweep_points", 100002),
            ("sweep_points", 3.5), ("sweep_points", True),
            ("if_bandwidth", 0), ("if_bandwidth", float("inf")),
            ("source_power", float("nan")), ("source_power", float("inf")),
            ("average_count", 1001), ("average_count", 2.5),
            ("sweep_count", 100001), ("sweep_count", 1.5),
            ("sweep_type", "INVALID"), ("trigger_source", "BUS"),
            ("trace_format", "INVALID"), ("averaging_enabled", "ON"),
        ]
        with expected_protocol(ZNB43, []) as vna:
            for attr, value in cases:
                with self.subTest(attr=attr, value=value), self.assertRaises(ValueError):
                    setattr(vna.ch_1, attr, value)
            for number in (0, -1, True, 1.5, "2"):
                with self.subTest(number=number), self.assertRaises(ValueError):
                    vna.channel(number)
            for name in ("", "  ", "trace\n*RST", "trace\x00", None):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    vna.ch_1.select_trace(name)
            for parameter in ("S00", "S51", "S111", "S21;*RST", "a1", None):
                with self.subTest(parameter=parameter), self.assertRaises(ValueError):
                    vna.ch_1.define_trace("test", parameter)

    def test_timeout_and_unexpected_opc_response_propagate(self):
        with expected_protocol(ZNB43, [("*OPC?", "0")]) as vna:
            with self.assertRaises(RuntimeError):
                vna.wait_for_complete()
        vna = ZNB43(FakeAdapter())
        with patch.object(vna.adapter, "read", side_effect=TimeoutError("timed out")):
            with self.assertRaises(TimeoutError):
                vna.ch_1.sweep()

    def test_wasic_panel_getters_and_setters_keep_their_own_property(self):
        with expected_protocol(ZNB43, [
            ("SENS1:FREQ:STAR?", "1e6"),
            ("SENS1:FREQ:STOP 2000000000", None),
            ("SENS1:AVER:COUN 4", None),
            ("OUTP 0", None),
        ]) as vna:
            fields = {p.alias: p for p in vna.properties_list}
            self.assertEqual(fields["CH1 Start frequency (Hz)"].associated_getter(), 1e6)
            fields["CH1 Stop frequency (Hz)"].associated_setter(2e9)
            fields["CH1 Average count"].associated_setter(4)
            fields["RF enabled (all channels)"].associated_setter(False)

    def test_addon_discovery_and_factory(self):
        from addons.loader import AddonRegistry

        registry = AddonRegistry()
        registry.discover("instruments")
        self.assertFalse(registry.errors)
        spec = registry.match_instrument("Rohde-Schwarz,ZNB43-4Port,123456,4.25")
        self.assertIs(spec, PLUGIN)
        self.assertIsNone(registry.match_instrument("Rohde-Schwarz,ZNB40,123456,4.25"))
        vna = spec.factory(FakeAdapter(), SimpleNamespace(name="VNA bench"))
        self.assertIsInstance(vna, ZNB43)
        self.assertEqual(vna.name, "VNA bench")


if __name__ == "__main__":
    unittest.main()
