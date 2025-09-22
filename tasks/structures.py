from typing import List, Callable, Optional, Any, Dict
from dataclasses import dataclass, field, asdict
from datetime import datetime
import math
import json
import tempfile
from pathlib import Path

@dataclass
class AxisMeta:
    """Metadata for an axis (label, unit, scale).

    Fields are documented in their metadata so IDEs can surface them when available.
    """
    label: str = field(default="", metadata={"help": "Axis label (e.g. 'Voltage')."})
    unit: str = field(default="", metadata={"help": "Unit string (e.g. 'V')."})
    scale: str = field(default="linear", metadata={"help": "Scale: 'linear' or 'log'."})


@dataclass
class Series:
    """Pair of raw/processed series with axis metadata."""
    raw: List[Any] = field(default_factory=list, metadata={"help": "Raw samples for this series."})
    processed: List[float] = field(default_factory=list, metadata={"help": "Processed samples for this series."})
    meta: AxisMeta = field(default_factory=AxisMeta, metadata={"help": "Axis metadata."})


@dataclass
class ChartData_Config:
    """Configuration/options that affect sanitization, saving and memory behavior.

    Parameters
    ----------
    pop_raw: bool
        If True, raw buffers will be cleared after compute/save when applicable.
    include_raw_on_save: bool
        If False, raw arrays are excluded from exported JSON.
    atomic_save: bool
        If True, saving will be atomic (write temp file then move into place).
    sample_points_x, sample_points_y: int
        Per-axis sample limits (0 = unlimited).
    pairwise_sync: bool
        If True, sanitize will keep x/y samples pairwise to avoid desync.
    backup_enabled: bool
        Per-chart backup switch (overrides global switch if set).
    backup_interval_s: float
        Per-chart backup frequency in seconds.
    backup_path: Optional[str]
        Per-chart backup directory. If None use global path.
    custom_type: str
        Optional chart type/category.
    schema_version: int
        Config schema version for migrations.
    """

    pop_raw: bool = field(default=False, metadata={"help": "Clear raw buffers after save when True."})
    include_raw_on_save: bool = field(default=True, metadata={"help": "Include raw arrays when saving JSON."})
    atomic_save: bool = field(default=True, metadata={"help": "Use atomic write when saving to disk."})
    sample_points_x: int = field(default=0, metadata={"help": "Max X points to keep (0=unlimited)."})
    sample_points_y: int = field(default=0, metadata={"help": "Max Y points to keep (0=unlimited)."})
    refresh_all: bool = field(default=False, metadata={"help": "If True, request full UI refresh when this chart updates."})
    custom_type: str = field(default="", metadata={"help": "Chart type or category."})
    schema_version: int = field(default=1, metadata={"help": "Config schema version."})



class ChartData:
    """
    ChartData_ - runtime object with helpers.

    Constructor parameters
    ----------------------
    name: str
        Chart name.
    schema_version: int
        Schema version for saved payloads.
    created_at: Optional[str]
        ISO timestamp of creation.
    config: Optional[ChartData_Config]
        Per-chart configuration (see ChartData_Config docs).
    x_series, y_series: Optional[Series]
        Prepopulated series; if omitted fresh series are created.
    math_formula_x, math_formula_y: Optional[Callable]
        Runtime-only formulas; not serialized.
    """

    def __init__(
        self,
        name: str = "Custom Chart",
        schema_version: int = 1,
        created_at: Optional[str] = None,
        config: Optional[ChartData_Config] = None,
        x_series: Optional[Series] = None,
        y_series: Optional[Series] = None,
        math_formula_x: Optional[Callable[[Any], float]] = None,
        math_formula_y: Optional[Callable[[Any], float]] = None,
    ):
        self.name = name
        self.schema_version = schema_version
        self.created_at = created_at if created_at is not None else datetime.now().isoformat()

        # Config section
        self.config = config if config is not None else ChartData_Config()

        # Data section - create new Series/AxisMeta instances per object
        self.x_series = x_series if x_series is not None else Series(meta=AxisMeta(label="X-axis"))
        self.y_series = y_series if y_series is not None else Series(meta=AxisMeta(label="Y-axis"))

        # runtime-only callables
        self.math_formula_x = math_formula_x
        self.math_formula_y = math_formula_y

    def __repr__(self):
        return (
            f"ChartData_(name={self.name!r}, schema_version={self.schema_version!r}, "
            f"created_at={self.created_at!r})"
        )
    def compute(self) -> None:
        """Apply math formulas (if present) to the raw series and populate processed series."""
        if self.math_formula_x is not None:
            self.x_series.processed = [self.math_formula_x(v) for v in self.x_series.raw]
        if self.math_formula_y is not None:
            self.y_series.processed = [self.math_formula_y(v) for v in self.y_series.raw]
        if self.config.pop_raw:
            self.x_series.raw.clear()
            self.y_series.raw.clear()

    def to_dict(self, include_raw: bool = True) -> Dict[str, Any]:
        """Return a JSON-serializable dict containing only plain data (no callables or objects)."""
        d: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "name": self.name,
            "created_at": self.created_at,
            "config": {
                "pop_raw": self.config.pop_raw,
                "sample_points_x": self.config.sample_points_x,
                "sample_points_y": self.config.sample_points_y,
                "refresh_all": getattr(self.config, "refresh_all", False),
                "custom_type": self.config.custom_type,
            },
            "x": {
                "processed": list(self.x_series.processed),
                "meta": {
                    "label": self.x_series.meta.label,
                    "unit": self.x_series.meta.unit,
                    "scale": self.x_series.meta.scale,
                },
            },
            "y": {
                "processed": list(self.y_series.processed),
                "meta": {
                    "label": self.y_series.meta.label,
                    "unit": self.y_series.meta.unit,
                    "scale": self.y_series.meta.scale,
                },
            },
        }
        if include_raw and self.config.include_raw_on_save:
            d["x"]["raw"] = list(self.x_series.raw)
            d["y"]["raw"] = list(self.y_series.raw)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChartData":
        cfg = data.get("config", {})
        config = ChartData_Config(
            pop_raw=cfg.get("pop_raw", False),
            sample_points_x=cfg.get("sample_points_x", 0),
            sample_points_y=cfg.get("sample_points_y", 0),
            refresh_all=cfg.get("refresh_all", False) if isinstance(cfg, dict) else False,
            custom_type=cfg.get("custom_type", ""),
        )

        x = data.get("x", {})
        y = data.get("y", {})

        x_meta = x.get("meta", {})
        y_meta = y.get("meta", {})

        x_series = Series(
            raw=list(x.get("raw", [])),
            processed=list(x.get("processed", [])),
            meta=AxisMeta(label=x_meta.get("label", ""), unit=x_meta.get("unit", ""), scale=x_meta.get("scale", "linear")),
        )
        y_series = Series(
            raw=list(y.get("raw", [])),
            processed=list(y.get("processed", [])),
            meta=AxisMeta(label=y_meta.get("label", ""), unit=y_meta.get("unit", ""), scale=y_meta.get("scale", "linear")),
        )

        obj = cls(
            name=data.get("name", "Custom Chart"),
            schema_version=data.get("schema_version", 1),
            created_at=data.get("created_at"),
            config=config,
            x_series=x_series,
            y_series=y_series,
        )
        return obj

    def save_json_atomic(self, path: str, include_raw: bool = True) -> None:
        """Write the dict to a temporary file then atomically replace the destination.

        This avoids partially written files if the process is interrupted.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            if self.config.atomic_save:
                with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
                    json.dump(self.to_dict(include_raw=include_raw), tf, ensure_ascii=False, indent=4)
                    tmp = Path(tf.name)
                tmp.replace(p)
            else:
                p.write_text(json.dumps(self.to_dict(include_raw=include_raw), ensure_ascii=False, indent=4), encoding="utf-8")
        finally:
            # best-effort cleanup
            try:
                if tmp is not None and tmp.exists():
                    tmp.unlink(missing_ok=True)
            except Exception:
                pass
    # Switch: 0 -> X axis, 1 -> Y axis 2-> Total
    def get_length(self, switch: int) -> int:
        """
        Return the length of the processed data.

        Parameters
        ----------
        switch : int
            Selector for which series length to return:
            - 0: length of self.x_series.processed
            - 1: length of self.y_series.processed
            - 2: minimum length of self.x_series.processed and self.y_series.processed
            Any other value results in 0 being returned.

        Returns
        -------
        int
            The requested length as described above. Returns 0 for unknown selector values.

        Raises
        ------
        AttributeError
            If self.x_series or self.y_series or their 'processed' attributes are missing.

        Examples
        --------
        >>> obj.get_length(0)
        42
        >>> obj.get_length(2)
        min(len(obj.x_series.processed), len(obj.y_series.processed))
        """
        """Return the length of the processed data."""
        if switch == 0:
            return len(self.x_series.processed)
        elif switch == 1:
            return len(self.y_series.processed)
        elif switch == 2:
            return min(len(self.x_series.processed), len(self.y_series.processed))
        return 0