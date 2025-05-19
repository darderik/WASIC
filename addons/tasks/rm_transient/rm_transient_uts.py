from typing import List, Optional
import numpy as np
from scipy.interpolate import interp1d


def compute_transient_time(
    transient_pack: List[List[float]],
    threshold: Optional[float] = None,
) -> float:
    times = np.array(transient_pack[0])
    voltages = np.array(transient_pack[1])
    pwl_fit = interp1d(voltages, times, kind="linear", fill_value="extrapolate")
    char_time = pwl_fit(threshold) if threshold is not None else np.nan
    return float(char_time)


def calculate_rise_time(transient_pack: List[List[float]]) -> float:
    """
    Calculates the rise time of a transient signal.

    Args:
        transient_pack (List[List[float]]): A list containing two lists:
            - [0]: Time values
            - [1]: Voltage values

    Returns:
        float: The rise time (time difference between the start and end of the rise).
               Returns NaN if no valid rise is detected.
    """
    high_threshold = 1
    zero_cross = compute_transient_time(transient_pack, threshold=high_threshold)
    return zero_cross


def calculate_fall_time(transient_pack: List[List[float]]) -> float:
    """
    Calculates the fall time of a transient signal.

    Args:
        transient_pack (List[List[float]]): A list containing two lists:
            - [0]: Time values
            - [1]: Voltage values

    Returns:
        float: The fall time (time difference between the start and end of the fall).
               Returns NaN if no valid fall is detected.
    """
    hi_threshold = 4
    high_cross = compute_transient_time(transient_pack, threshold=hi_threshold)
    return high_cross
