import numpy as np
import logging

logger = logging.getLogger(__name__)

def calculate_rise_time(transient):
    """
    Placeholder for calculating rise time from transient data.
    transient is expected to be [t, V] where t is time array, V is voltage array.
    """
    # Implement rise time calculation logic here
    # For example, find time from 10% to 90% of max voltage
    t, V = transient
    if not t or not V:
        return 0.0
    # Placeholder: return a dummy value
    hi_thresh = 4.5
    res = transient_value_extractor(transient, hi_thresh)
    return res 

def calculate_fall_time(transient) -> float:
    """
    Placeholder for calculating fall time from transient data.
    transient is expected to be [t, V] where t is time array, V is voltage array.
    """
    t, V = transient
    if not t or not V:
        return 0.0
    lo_thresh = 0.5
    res: float = transient_value_extractor(transient, lo_thresh)
    return res
def transient_value_extractor(transient, value:float) -> float:
        """
        Extracts the voltage value from the transient data.
        transient is expected to be [t, V] where t is time array, V is voltage array.
        """
        t, V = transient
        first_val = V[0] if V else 0.0
        if (first_val > value):
            # Fall transient
            np_V = np.array(V)
            above_threshold_indices = np.where(np_V >= value)[0]
            if len(above_threshold_indices) == 0:
                logger.warning("No values above threshold %.3f found in fall transient.", value)
                return np.nan
            last_above_index = above_threshold_indices[-1]
            below_threshold_indices = np.where(np_V < value)[0]
            below_after_indices = below_threshold_indices[below_threshold_indices > last_above_index]
            if len(below_after_indices) == 0:
                logger.warning("No values below threshold %.3f after last above-threshold index in fall transient.", value)
                return np.nan
            first_below_index = below_after_indices[0]
            V1 = np_V[last_above_index]
            V2 = np_V[first_below_index]
            t1 = t[last_above_index]
            t2 = t[first_below_index]
            if V2 == V1:
                return t1
            lin_fit_res = np.interp(value, [V1, V2], [t1, t2])
        else:
            # Rise transient
            np_V = np.array(V)
            above_threshold_indices = np.where(np_V >= value)[0]
            if len(above_threshold_indices) == 0:
                logger.warning("No values above threshold %.3f found in rise transient.", value)
                return np.nan
            first_above_index = above_threshold_indices[0]
            below_threshold_indices = np.where(np_V < value)[0]
            below_before_indices = below_threshold_indices[below_threshold_indices < first_above_index]
            if len(below_before_indices) == 0:
                logger.warning("No values below threshold %.3f before first above-threshold index in rise transient.", value)
                return np.nan
            last_below_index = below_before_indices[-1]
            V1 = np_V[last_below_index]
            V2 = np_V[first_above_index]
            t1 = t[last_below_index]
            t2 = t[first_above_index]
            if V2 == V1:
                return t1
            lin_fit_res = np.interp(value, [V1, V2], [t1, t2])
        return float(lin_fit_res)
