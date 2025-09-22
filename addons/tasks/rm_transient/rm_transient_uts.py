import numpy as np
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

def calculate_fall_time(transient):
    """
    Placeholder for calculating fall time from transient data.
    transient is expected to be [t, V] where t is time array, V is voltage array.
    """
    t, V = transient
    if not t or not V:
        return 0.0
    lo_thresh = 0.5
    res = transient_value_extractor(transient, lo_thresh)
    return res

def transient_value_extractor(transient, value:float):
    """
    Extracts the voltage value from the transient data.
    transient is expected to be [t, V] where t is time array, V is voltage array.
    """
    # 1. Unnderstand if we are looking for a rise or fall transient
    t, V = transient
    first_val = V[0] if V else 0.0
    if (first_val > value):
        # Fall transient
        # Look for the last value above the threshold
        # Convert the voltage array to a numpy array for efficient computation
        np_V = np.array(V)
        # Find indices where the voltage is above or equal to the threshold value
        above_threshold_indices = np.where(np_V >= value)[0]
        # If no values are above the threshold, return NaN
        if len(above_threshold_indices) == 0:
            return np.nan
        # Get the last index where the voltage is above the threshold
        last_above_index = above_threshold_indices[-1]
        # Find indices where the voltage is below the threshold
        below_threshold_indices = np.where(np_V < value)[0]
        # Filter indices to only include those after the last above-threshold index
        below_after_indices = below_threshold_indices[below_threshold_indices > last_above_index]
        # If no values are below the threshold after the last above-threshold index, return NaN
        if len(below_after_indices) == 0:
            return np.nan
        # Get the first index where the voltage falls below the threshold after the last above-threshold index
        first_below_index = below_after_indices[0]

        # 2. Perform linear interpolation to find the exact crossing point
        V1 = np_V[last_above_index]
        V2 = np_V[first_below_index]
        t1 = t[last_above_index]
        t2 = t[first_below_index]
        if V2 == V1:
            return t1  # Avoid division by zero, return t1 as a fallback
        # Linear interpolation formula to find the crossing time
        lin_fit_res = np.interp(value, [V1, V2], [t1, t2])
        
        
    else:
        # Rise transient
        # Look for the first value above the threshold
        # Convert the voltage array to a numpy array for efficient computation
        np_V = np.array(V)
        # Find indices where the voltage is above or equal to the threshold value
        above_threshold_indices = np.where(np_V >= value)[0]
        # If no values are above the threshold, return NaN
        if len(above_threshold_indices) == 0:
            return np.nan
        # Get the first index where the voltage is above the threshold
        first_above_index = above_threshold_indices[0]
        # Find indices where the voltage is below the threshold
        below_threshold_indices = np.where(np_V < value)[0]
        # Filter indices to only include those before the first above-threshold index
        below_before_indices = below_threshold_indices[below_threshold_indices < first_above_index]
        # If no values are below the threshold before the first above-threshold index, return NaN
        if len(below_before_indices) == 0:
            return np.nan
        # Get the last index where the voltage is below the threshold before the first above-threshold index
        last_below_index = below_before_indices[-1]

        # 2. Perform linear interpolation to find the exact crossing point
        V1 = np_V[last_below_index]
        V2 = np_V[first_above_index]
        t1 = t[last_below_index]
        t2 = t[first_above_index]
        if V2 == V1:
            return t1  # Avoid division by zero, return t1 as a fallback
        # Linear interpolation formula to find the crossing time
        lin_fit_res = np.interp(value, [V1, V2], [t1, t2])
    
    return lin_fit_res