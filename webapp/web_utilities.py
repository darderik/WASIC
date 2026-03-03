from instruments.properties import property_info
from tasks import ChartData, Tasks, Task, ChartData_Config
import pandas as pd
import plotly.express as px
import inspect
from typing import List, Tuple, Callable, Dict, get_type_hints, get_origin, get_args, Union
from types import UnionType


def val_to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "on", "yes", "y", "t"}:
        return True
    if normalized in {"0", "false", "off", "no", "n", "f", ""}:
        return False
    raise ValueError(f"Cannot convert '{value}' to bool")

def _to_list(value):
    """Convert many possible container/array-like inputs to a plain Python list.
    Safe for None, scalars, pandas Series, numpy arrays, lists, etc.
    """
    if value is None:
        return []
    try:
        # pandas handles many types (numpy arrays, Series, lists, scalars)
        return pd.Series(value).tolist()
    except Exception:
        try:
            return list(value)
        except Exception:
            return [value]


def make_plotly_figure(chart_data: ChartData):
    """Create a Plotly figure from a ChartData object.

    Rules:
    - For histograms: Use only y_series.processed, ignore x_series.
    - For other plots: If y_series.processed is None or empty, return empty figure.
      If y_series.processed exists, check for x_series.processed.
      If x_series.processed exists, slice both to the same length.
      If not, use an index for x.
    """
    chart_data_config: ChartData_Config = chart_data.config
    custom_type = chart_data_config.custom_type
    title = chart_data.name
    x_label = chart_data.x_series.meta.label if chart_data.x_series else ""
    y_label = chart_data.y_series.meta.label if chart_data.y_series else ""

    # Get processed data
    y_processed = chart_data.y_series.processed if chart_data.y_series else None
    x_processed = chart_data.x_series.processed if chart_data.x_series else None

    # Convert to lists
    y_list = _to_list(y_processed)
    x_list = _to_list(x_processed)
    # Filter out nan in couple (check if x is not null)
    if x_list and y_list:
        filtered_pairs = [(x, y) for x, y in zip(x_list, y_list) if pd.notna(x) and pd.notna(y)]
        if filtered_pairs:
            x_list, y_list = zip(*filtered_pairs)
            x_list = list(x_list)
            y_list = list(y_list)
        else:
            x_list = []
            y_list = []
    elif y_list:
        y_list = [y for y in y_list if pd.notna(y)]
    elif x_list:
        x_list = [x for x in x_list if pd.notna(x)]

    if custom_type in ("histogram", "hist"):
        # Histogram: prioritize y, then x if y is empty
        if y_list:
            # Use y if available (whether x is present or not)
            data_list = y_list
            data_label = y_label
        elif x_list:
            # Use x if y is empty but x is available
            data_list = x_list
            data_label = x_label
        else:
            # Both empty, empty histogram
            data_list = []
            data_label = y_label  # or x_label, doesn't matter
        
        fig = px.histogram(pd.DataFrame({"data": data_list}), x="data", title=title, labels={"data": data_label})
    else:
        # Other plots: scatter, line, etc.
        if not y_list:
            # No y data, return empty
            fig = px.scatter(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title, labels={"x": x_label, "y": y_label})
        else:
            if x_list:
                # Both x and y, slice to min length
                min_len = min(len(x_list), len(y_list))
                x_trim = x_list[:min_len]
                y_trim = y_list[:min_len]
            else:
                # No x, use index
                x_trim = list(range(len(y_list)))
                y_trim = y_list

            df = pd.DataFrame({"x": x_trim, "y": y_trim})

            if custom_type in ("", "scatter"):
                fig = px.scatter(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})
            else:
                # Default to line
                fig = px.line(df, x="x", y="y", title=title, labels={"x": x_label, "y": y_label})

    return fig


def property_pairs_from_descriptors(obj):
    pairs: Dict[str, Tuple[Callable, Callable]] = {}
    for name, attr in vars(type(obj)).items():
        if isinstance(attr, property) and attr.fget and attr.fset:
            pairs[name] = (attr.fget, attr.fset)
    return pairs


def _normalize_typehint(type_hint):
    # Normalize Optional[T]/Union[T, None] and generic aliases to a concrete runtime type.
    if type_hint is None or type_hint is inspect._empty:
        return None

    origin = get_origin(type_hint)
    if origin in (Union, UnionType):
        args = [arg for arg in get_args(type_hint) if arg is not type(None)]
        if len(args) == 1:
            return _normalize_typehint(args[0])
        return None

    if origin is not None:
        return origin if isinstance(origin, type) else None

    return type_hint if isinstance(type_hint, type) else None


def _infer_property_type(prop: property) -> type:
    # Prefer setter parameter type (editable input), then fallback to getter return type.
    if prop.fset:
        try:
            setter_hints = get_type_hints(prop.fset)
        except Exception:
            setter_hints = getattr(prop.fset, "__annotations__", {}) or {}

        for param_name in inspect.signature(prop.fset).parameters.keys():
            if param_name == "self":
                continue
            inferred = _normalize_typehint(setter_hints.get(param_name))
            if inferred:
                return inferred
            break

    if prop.fget:
        try:
            getter_hints = get_type_hints(prop.fget)
        except Exception:
            getter_hints = getattr(prop.fget, "__annotations__", {}) or {}

        inferred = _normalize_typehint(getter_hints.get("return"))
        if inferred:
            return inferred

    return str


def _is_user_property(prop: property) -> bool:
    # Keep only writable properties and ignore pymeasure base descriptors in fallback mode.
    if not (prop.fget and prop.fset):
        return False

    getter_module = getattr(prop.fget, "__module__", "") or ""
    setter_module = getattr(prop.fset, "__module__", "") or ""
    if getter_module.startswith("pymeasure") or setter_module.startswith("pymeasure"):
        return False

    return True

def craft_property_info_list(obj) -> List[property_info]:
    property_info_list: List[property_info] = []
    # vars(type(obj)) returns only attributes defined in the class, not inherited ones. 
    # This is intentional to avoid picking up properties from base classes that might not be relevant.
    for name, attr in vars(type(obj)).items():
        if isinstance(attr, property) and _is_user_property(attr):
            inferred_type = _infer_property_type(attr)
            getter = attr.fget
            setter = attr.fset
            if getter is None or setter is None:
                continue
            property_info_list.append(
                property_info(
                    alias=name,
                    typecheck=inferred_type,
                    associated_getter=lambda getter=getter: getter(obj),
                    associated_setter=lambda value, setter=setter: setter(obj, value),
                )
            )
    return property_info_list


def send_parameters(instr_properties: List[property_info], edited_data: pd.DataFrame) -> List[str]:
    messages: List[str] = []
    for i, prop in enumerate(instr_properties):
        try:
            new_value = edited_data.iloc[i]["Current Value"]
            supposed_type = prop.typecheck

            if supposed_type == bool:
                parsed_value = val_to_bool(new_value)
            else:
                parsed_value = supposed_type(new_value)

            # Compare before writing to avoid unnecessary instrument traffic.
            current_value = prop.associated_getter()
            if parsed_value != current_value:
                prop.associated_setter(parsed_value)
                messages.append(f"Updated {prop.alias} to {parsed_value}")
        except Exception as e:
            messages.append(f"Error updating {prop.alias}: {str(e)}")

    return messages


def create_properties_dataframe(instr_properties: List[property_info]) -> pd.DataFrame:
    data = []
    for prop in instr_properties:
        try:
            current_value = prop.associated_getter()
            if prop.typecheck == bool:
                display_value = "ON" if val_to_bool(current_value) else "OFF"
            else:
                display_value = str(current_value)
        except Exception:
            # Keep the table renderable even if one property read fails.
            display_value = "<read error>"

        data.append(
            {
                "Property": prop.alias,
                "Type": prop.typecheck.__name__,
                "Current Value": display_value,
            }
        )

    return pd.DataFrame(data)