"""Stable addon contracts: importing this module never initializes WASIC."""
from dataclasses import dataclass, field
from math import isfinite
from threading import Event
from typing import Any, Callable

@dataclass(frozen=True)
class ParameterSpec:
    type: type
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple = ()

    def parse(self, value):
        if self.type not in (str, int, float, bool):
            raise TypeError("Supported parameter types: str, int, float, bool")
        if self.type is int and isinstance(value, float) and not value.is_integer():
            raise ValueError("Expected an integer")
        if self.type is bool:
            if isinstance(value, bool):
                result = value
            elif str(value).lower() in ("true", "1", "yes", "y"):
                result = True
            elif str(value).lower() in ("false", "0", "no", "n"):
                result = False
            else:
                raise ValueError("Expected a boolean")
        else:
            result = self.type(value)
        if isinstance(result, float) and not isfinite(result):
            raise ValueError("Expected a finite value")
        if self.minimum is not None and result < self.minimum:
            raise ValueError(f"Minimum is {self.minimum}")
        if self.maximum is not None and result > self.maximum:
            raise ValueError(f"Maximum is {self.maximum}")
        if self.choices and result not in self.choices:
            raise ValueError(f"Expected one of {self.choices}")
        return result

@dataclass(frozen=True)
class TaskSpec:
    id: str
    name: str
    description: str
    run: Callable[["TaskContext"], None]
    instruments: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, ParameterSpec] = field(default_factory=dict)

    def parse_parameters(self, values):
        unknown = values.keys() - self.parameters.keys()
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")
        result = {}
        for name, spec in self.parameters.items():
            try:
                result[name] = spec.parse(values.get(name, spec.default))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{name}: {exc}") from exc
        return result

@dataclass(frozen=True)
class InstrumentSpec:
    id: str
    name: str
    idn_keywords: tuple[str, ...]
    factory: Callable[[Any, Any], Any]

    def matches(self, idn):
        return any(keyword.lower() in idn.lower() for keyword in self.idn_keywords)

@dataclass
class TaskContext:
    instruments: dict[str, Any]
    parameters: dict[str, Any]
    data: list
    exit_flag: Event
