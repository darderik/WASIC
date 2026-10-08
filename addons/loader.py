"""Discover declarative addons independently, without opening hardware."""
import importlib
import logging
from pathlib import Path
from threading import RLock
from wasic_api import InstrumentSpec, TaskSpec

logger = logging.getLogger(__name__)

class AddonRegistry:
    def __init__(self):
        self.tasks = {}
        self.instruments = {}
        self.errors = {}
        self._loaded = set()
        self._lock = RLock()

    def register(self, spec):
        if not isinstance(spec, (TaskSpec, InstrumentSpec)):
            raise TypeError("PLUGIN must be a TaskSpec or InstrumentSpec")
        if not spec.id or not spec.name:
            raise ValueError("Addon id and name are required")
        if isinstance(spec, TaskSpec):
            if not callable(spec.run):
                raise TypeError("Task run must be callable")
            spec.parse_parameters({})
            if any(existing.name == spec.name for existing in self.tasks.values()):
                raise ValueError(f"Duplicate task name: {spec.name}")
            if any(not role or not isinstance(driver, str) or not driver
                   for role, driver in spec.instruments.items()):
                raise ValueError("Instrument roles require nonempty driver IDs")
            target = self.tasks
        else:
            if not callable(spec.factory) or not spec.idn_keywords or any(
                not isinstance(k, str) or not k.strip() for k in spec.idn_keywords
            ):
                raise ValueError("Instrument needs a factory and nonempty IDN keywords")
            target = self.instruments
        if spec.id in target:
            raise ValueError(f"Duplicate addon id: {spec.id}")
        target[spec.id] = spec

    def discover(self, kind):
        with self._lock:
            if kind in self._loaded:
                return
            root = Path(__file__).parent / kind
            for path in sorted(root.rglob("*.py")):
                if path.name.startswith("_"):
                    continue
                module_name = "addons." + ".".join(path.relative_to(root.parent).with_suffix("").parts)
                try:
                    module = importlib.import_module(module_name)
                    spec = getattr(module, "PLUGIN", None)
                    if spec is not None:
                        expected = TaskSpec if kind == "tasks" else InstrumentSpec
                        if not isinstance(spec, expected):
                            raise TypeError(f"Expected {expected.__name__}")
                        self.register(spec)
                except Exception as exc:
                    self.errors[module_name] = str(exc)
                    logger.exception("Cannot load addon %s", module_name)
            self._loaded.add(kind)

    def match_instrument(self, idn):
        self.discover("instruments")
        matches = [spec for spec in self.instruments.values() if spec.matches(idn)]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous instrument IDN: {idn}")
        return matches[0] if matches else None

registry = AddonRegistry()

def load_addons():
    """Explicit, idempotent application/library bootstrap."""
    registry.discover("instruments")
    registry.discover("tasks")
    from tasks import Tasks
    Tasks().load_specs(registry.tasks.values())
    return registry
