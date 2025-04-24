from typing import List
import sympy as sp
from scipy.optimize import brentq
import numpy as np


def van_der_pauw_calculation(hor_ver_resistance: List[float]) -> float:
    """Calculate the sheet resistance of a sample using the Van der Pauw method."""
    horizontal_resistance, vertical_resistance = hor_ver_resistance
    R_s = sp.Symbol("R_s")  # Sheet resistance
    R_h: float = abs(horizontal_resistance)
    R_v: float = abs(vertical_resistance)
    vdp_equation = sp.Eq(sp.exp(-sp.pi * R_h / R_s) + sp.exp(-sp.pi * R_v / R_s) - 1, 0)
    vdp_numeric_equation = sp.lambdify(R_s, vdp_equation.lhs, modules="numpy")
    try:
        sheet_resistance: float = brentq(vdp_numeric_equation, 1e-20, 1e6)
    except ValueError:
        sheet_resistance = np.nan
    return sheet_resistance
