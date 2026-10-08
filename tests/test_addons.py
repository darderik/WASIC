import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from addons.loader import AddonRegistry
from wasic_api import InstrumentSpec, ParameterSpec, TaskSpec


class AddonContractTests(unittest.TestCase):
    def test_parameter_validation(self):
        spec = TaskSpec("example", "Example", "", lambda ctx: None, parameters={
            "interval": ParameterSpec(float, 1.0, minimum=0.01),
            "enabled": ParameterSpec(bool, False),
            "wires": ParameterSpec(int, 2, choices=(2, 4)),
        })
        self.assertEqual(spec.parse_parameters({"enabled": "true", "wires": "4"}),
                         {"interval": 1.0, "enabled": True, "wires": 4})
        for values in ({"interval": 0}, {"interval": "nan"}, {"wires": 3},
                       {"enabled": "maybe"}, {"extra": 1}, {"wires": 2.5}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                spec.parse_parameters(values)

    def test_duplicate_and_ambiguous_definitions(self):
        registry = AddonRegistry()
        spec = InstrumentSpec("meter", "Meter", ("MODEL",), lambda adapter, info: adapter)
        registry.register(spec)
        with self.assertRaises(ValueError):
            registry.register(spec)
        registry._loaded.add("instruments")
        self.assertIs(registry.match_instrument("vendor,model,123"), spec)
        registry.register(InstrumentSpec("other", "Other", ("model",), spec.factory))
        with self.assertRaises(ValueError):
            registry.match_instrument("vendor,model,123")

    def test_recursive_discovery_isolates_errors_and_is_idempotent(self):
        registry = AddonRegistry()
        spec = TaskSpec("nested", "Nested", "", lambda ctx: None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tasks" / "nested").mkdir(parents=True)
            for name in ("broken.py", "helper.py", "_ignored.py", "nested/task.py"):
                (root / "tasks" / name).touch()
            def importer(name):
                if name.endswith("broken"):
                    raise ImportError("optional dependency unavailable")
                return SimpleNamespace(PLUGIN=spec) if name.endswith("task") else SimpleNamespace()
            with patch("addons.loader.__file__", str(root / "loader.py")), \
                 patch("addons.loader.importlib.import_module", side_effect=importer) as imports, \
                 self.assertLogs("addons.loader", level="ERROR"):
                registry.discover("tasks")
                registry.discover("tasks")
            self.assertEqual(imports.call_count, 3)
        self.assertEqual(list(registry.tasks), ["nested"])
        self.assertIn("addons.tasks.broken", registry.errors)


if __name__ == "__main__":
    unittest.main()
