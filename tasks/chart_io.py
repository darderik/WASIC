"""Tabular chart samples and typed CSV metadata, without embedded objects."""

import csv
from dataclasses import asdict, dataclass
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
from itertools import zip_longest

from .structures import ChartData


def _write_text(path, text, atomic=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not atomic:
        path.write_text(text, encoding="utf-8", newline="")
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, suffix=".tmp", encoding="utf-8",
            newline="", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _scalar_type(value):
    if value is None:
        return "none"
    if type(value) in (str, bool, int, float):
        return type(value).__name__
    raise ValueError(f"Unsupported CSV value type: {type(value).__name__}")


def _scalar_text(value):
    return "" if value is None else str(value)


def _parse_scalar(kind, value):
    if kind == "none":
        return None
    if kind == "bool":
        if value not in ("True", "False"):
            raise ValueError(f"Invalid boolean: {value}")
        return value == "True"
    parsers = {"str": str, "int": int, "float": float}
    if kind not in parsers:
        raise ValueError(f"Invalid CSV value type: {kind}")
    return parsers[kind](value)


@dataclass
class _Cell:
    row: int
    column: int
    kind: str


def _tree_rows(value, path=""):
    """Flatten metadata into path/type/value rows; samples reference CSV cells."""
    if isinstance(value, _Cell):
        yield path, f"cell:{value.kind}", f"{value.row}:{value.column}"
    elif isinstance(value, (dict, list, tuple)):
        yield path, "dict" if isinstance(value, dict) else "list", ""
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in items:
            if not isinstance(key, (str, int)):
                raise ValueError("CSV record keys must be strings or integers")
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from _tree_rows(child, f"{path}/{token}")
    else:
        yield path, _scalar_type(value), _scalar_text(value)


def _restore_tree(rows, samples):
    root = None
    for path, kind, text in rows:
        if kind.startswith("cell:"):
            row, column = map(int, text.split(":"))
            if row < 0 or column < 0:
                raise ValueError("Invalid CSV sample reference")
            value = _parse_scalar(kind[5:], samples[row][column])
        elif kind in ("dict", "list"):
            value = {} if kind == "dict" else []
        else:
            value = _parse_scalar(kind, text)
        if path == "":
            root = value
            continue
        tokens = [token.replace("~1", "/").replace("~0", "~")
                  for token in path[1:].split("/")]
        parent = root
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        if isinstance(parent, list):
            if int(tokens[-1]) != len(parent):
                raise ValueError("Invalid CSV list index")
            parent.append(value)
        else:
            parent[tokens[-1]] = value
    return root


def save_charts_csv(charts, path, *, include_raw=True, metadata=None, atomic=True):
    """Write processed pairs and flattened raw columns with Name(Unit) headers.

    A typed .meta.csv table preserves chart settings, raw structure and series
    lengths. All sample values live in the main CSV, at full numeric precision.
    """
    charts = list(charts)
    headers, columns, records = [], [], []
    used_headers = set()

    def add_column(label, unit, values):
        base_label, number = label, 2
        while f"{label}({unit})" in used_headers:
            label = f"{base_label}_{number}"
            number += 1
        header = f"{label}({unit})"
        used_headers.add(header)
        headers.append(header)
        columns.append(values)
        return len(headers) - 1

    for chart in charts:
        record = chart.to_dict(include_raw=False)
        record["config"] = asdict(chart.config)
        record["columns"] = []
        for axis, series in (("x", chart.x_series), ("y", chart.y_series)):
            label = series.meta.label or axis
            if len(charts) > 1:
                label = f"{chart.name}: {label}"
            values = list(series.processed)
            index = add_column(label, series.meta.unit, values)
            record[axis].pop("processed")
            record[axis]["meta"] = asdict(series.meta)
            record["columns"].append({"index": index, "axis": axis, "length": len(values),
                                      "types": [_scalar_type(value) for value in values]})

        if include_raw and chart.config.include_raw_on_save:
            for axis, series in (("x", chart.x_series), ("y", chart.y_series)):
                label = series.meta.label or axis
                if len(charts) > 1:
                    label = f"{chart.name}: {label}"
                raw = list(series.raw)
                fields = {}

                def raw_cells(value, row, field_path=()):
                    if isinstance(value, dict):
                        if any(not isinstance(key, str) for key in value):
                            raise ValueError("Raw record keys must be strings")
                        return {key: raw_cells(child, row, (*field_path, key))
                                for key, child in value.items()}
                    if isinstance(value, (list, tuple)):
                        return [raw_cells(child, row, (*field_path, index))
                                for index, child in enumerate(value)]
                    kind = _scalar_type(value)
                    if field_path not in fields:
                        suffix = "".join(f".{part}" for part in field_path)
                        fields[field_path] = add_column(
                            f"{label}_raw{suffix}", series.meta.unit if not field_path else "",
                            [None] * len(raw))
                    index = fields[field_path]
                    columns[index][row] = value
                    return _Cell(row, index, kind)

                record[axis]["raw"] = [raw_cells(value, row) for row, value in enumerate(raw)]
                if not fields:
                    add_column(f"{label}_raw", series.meta.unit, [None] * len(raw))
        records.append(record)

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows([_scalar_text(value) for value in row]
                     for row in zip_longest(*columns))
    csv_text = output.getvalue()
    details = {"format": "wasic-chart-csv-v2", "headers": headers,
               "sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
               "charts": records, "metadata": metadata or {}}
    metadata_output = io.StringIO(newline="")
    writer = csv.writer(metadata_output)
    writer.writerow(["Path()", "Type()", "Value()"])
    writer.writerows(_tree_rows(details))
    path = Path(path)
    _write_text(path, csv_text, atomic)
    _write_text(Path(str(path) + ".meta.csv"), metadata_output.getvalue(), atomic)


def load_charts_file(path):
    """Read CSV charts, including plain two-column comma/semicolon/tab files."""
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("Chart files must use the .csv extension")
    metadata_path = Path(str(path) + ".meta.csv")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(8192)
        stream.seek(0)
        delimiter = ","
        if sample and not metadata_path.exists():
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error as exc:
                raise ValueError("Cannot determine CSV delimiter") from exc
        rows = list(csv.reader(stream, delimiter=delimiter))
    if not rows or (not rows[0] and not metadata_path.exists()):
        raise ValueError("CSV has no column headers")
    headers, rows = rows[0], rows[1:]
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("CSV row length does not match its headers")
    if metadata_path.exists():
        with metadata_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["Path()", "Type()", "Value()"]:
                raise ValueError("Invalid CSV metadata headers")
            details = _restore_tree(reader, rows)
        if details.get("format") != "wasic-chart-csv-v2" or details["headers"] != headers:
            raise ValueError("CSV metadata does not match its column headers")
        if hashlib.sha256(path.read_bytes()).hexdigest() != details["sha256"]:
            raise ValueError("CSV and metadata are from different saves or have been modified")
        charts = []
        for record in details["charts"]:
            for column in record.pop("columns"):
                length, index = column["length"], column["index"]
                if length > len(rows):
                    raise ValueError("CSV is missing saved samples")
                record[column["axis"]]["processed"] = [
                    _parse_scalar(kind, row[index])
                    for kind, row in zip(column["types"], rows[:length])
                ]
            charts.append(ChartData.from_dict(record))
        return charts
    if len(headers) != 2:
        raise ValueError("CSV with more than two columns requires its .csv.meta.csv file")
    chart = ChartData(name=path.stem)
    for index, series in enumerate((chart.x_series, chart.y_series)):
        match = re.fullmatch(r"(.*)\((.*)\)", headers[index])
        series.meta.label = match[1] if match else headers[index]
        series.meta.unit = match[2] if match else ""
        cells = [row[index] for row in rows]
        while cells and cells[-1] == "":
            cells.pop()
        series.processed = [float(cell.replace(",", ".")) if cell else None for cell in cells]
    return [chart]
