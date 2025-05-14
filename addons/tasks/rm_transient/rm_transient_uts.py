from typing import List, Optional
import numpy as np


def lin_fit(point1: List[float], point2: List[float], threshold: float) -> float:
    x1 = point1[0]
    y1 = point1[1]
    x2 = point2[0]
    y2 = point2[1]
    rise_time = (x2 - x1) / (y2 - y1) * (threshold - y1) + x1
    return abs(rise_time)


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
    # Define thresholds
    high_threshold = 1  # Voltage threshold to end the rise

    # Extract time and voltage arrays
    cur_time = np.array(transient_pack[0])
    cur_voltage = np.array(transient_pack[1])

    # Find the first index where voltage exceeds the zero threshold
    start_index = np.argmax(cur_voltage > high_threshold)
    if start_index != 0:
        pre_start_index = start_index - 1
        above_threshold_point = [cur_time[start_index], cur_voltage[start_index]]
        below_threshold_point = [
            cur_time[pre_start_index],
            cur_voltage[pre_start_index],
        ]
        # Interpolate to find the time at which voltage crosses the zero threshold
        zero_cross_time = lin_fit(
            below_threshold_point, above_threshold_point, high_threshold
        )
        if zero_cross_time is not None and zero_cross_time > 0:
            return zero_cross_time
    return np.nan


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
    # Define thresholds
    hi_threshold = 3.3  # Voltage threshold to end the fall

    # Extract time and voltage arrays
    cur_time = np.array(transient_pack[0])
    cur_voltage = np.array(transient_pack[1])

    # Find the first index where voltage exceeds the zero threshold
    start_index = np.argmax(cur_voltage < hi_threshold)
    if start_index != 0:
        post_start_index = start_index + 1
        above_threshold_point = [cur_time[start_index], cur_voltage[start_index]]
        below_threshold_point = [
            cur_time[post_start_index],
            cur_voltage[post_start_index],
        ]
        # Interpolate to find the time at which voltage crosses the zero threshold
        zero_cross_time = lin_fit(
            below_threshold_point, above_threshold_point, hi_threshold
        )
        if zero_cross_time is None:
            return np.nan
        else:
            return zero_cross_time
    return np.nan
