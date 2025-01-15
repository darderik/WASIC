from typing import List
from dataclasses import dataclass, field


@dataclass
class ChartData:
    name: str = "Custom Chart"
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
