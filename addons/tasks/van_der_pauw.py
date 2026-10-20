"""Finite van der Pauw measurement using DC current reversal and four contacts."""
import logging
import math
import re
from statistics import fmean

from tasks import ChartData, ChartData_Config
from wasic_api import ParameterSpec, TaskContext, TaskSpec

logger = logging.getLogger(__name__)


def sheet_resistance(ra: float, rb: float) -> float:
    """Solve exp(-pi*RA/Rs) + exp(-pi*RB/Rs) = 1 in ohms/square.

    Normalize to avoid absolute-tolerance errors on small resistances. expm1
    avoids subtracting two nearly equal numbers for asymmetric samples.
    """
    if not all(math.isfinite(r) and r > 0 for r in (ra, rb)):
        raise ValueError("RA and RB must be finite and positive; check contact order/polarity")
    scale = max(ra, rb)
    small = min(ra, rb) / scale
    lo, hi = 0.0, math.pi / math.log(2)
    for _ in range(160):
        mid = (lo + hi) / 2
        residual = math.expm1(-math.pi * small / mid) + math.exp(-math.pi / mid)
        if residual > 0:
            hi = mid
        else:
            lo = mid
    result = (lo + hi) / 2 * scale
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Sheet resistance is outside the supported numeric range")
    return result


def relay_routes(parameters: dict) -> dict:
    """Contacts 1..4 are ordered around the perimeter; values are relay indices."""
    groups = [parameters[f"{role}_group"].strip().lower()
              for role in ("current_hi", "current_lo", "voltage_hi", "voltage_lo")]
    if any(not re.fullmatch(r"[a-z]", group) for group in groups) or len(set(groups)) != 4:
        raise ValueError("Use four distinct single-letter relay groups for I HI/LO and V HI/LO")
    contacts = [parameters[f"contact_{i}"] for i in range(1, 5)]
    if len(set(contacts)) != 4:
        raise ValueError("The four contact relay indices must be distinct")
    # RA = V43/I12; RB = V14/I23: both positive for the stated ordering.
    return {
        "RA": tuple(f"{g}{contacts[i]}" for g, i in zip(groups, (0, 1, 3, 2))),
        "RB": tuple(f"{g}{contacts[i]}" for g, i in zip(groups, (1, 2, 0, 3))),
    }


class _Stopped(Exception):
    """Cooperative cancellation, including during relay and current settling."""


class _Compliance(RuntimeError):
    """Reject the current RA/RB cycle while allowing subsequent repetitions."""


def _wait(ctx, seconds=0):
    if ctx.exit_flag.wait(seconds):
        raise _Stopped


def _check_source(source, *, current=None, compliance=None, route=()):
    # 622x reference manual, section 11: bit 1 means interlock asserted
    # (output permitted), not an interlock fault. Bits 0, 2 and 3 are faults.
    status = int(source.ask(":STAT:MEAS:COND?"))
    faults = [name for bit, name in (
        (0x1, "reading overflow"), (0x4, "overtemperature"),
        (0x8, "voltage compliance reached"),
    ) if status & bit]
    if faults:
        details = f"6221: {', '.join(faults)} (status={status:#x})"
        if current is not None and compliance is not None:
            details += f"; requested current={current:g} A, voltage limit={compliance:g} V"
        if route:
            details += f"; relay route={' '.join(route)}"
        if status & 0x8:
            details += "; check current HI/LO relay groups, wiring and sample contacts"
            if current and compliance is not None:
                limit = compliance / abs(current)
                details += f"; source-loop resistance limit at this current is {limit:g} ohm"
            details += "; reduce current if the connected sample needs more voltage"
        if status & 0x8 and not status & 0x5:
            raise _Compliance(details)
        raise RuntimeError(details)


def _chart(name, label, unit="ohm"):
    chart = ChartData(name="Van der Pauw - " + name, config=ChartData_Config(
        pop_raw=False, include_raw_on_save=True, atomic_save=True, custom_type="histogram",
    ))
    chart.configure_x_axis("Repetition", "")
    chart.configure_y_axis(label, unit)
    return chart


def _read_voltage(ctx, source, meter, route, record, key, p):
    """Retry explicit invalid readings only; a transport timeout must abort."""
    current = p["current_A"] if key == "positive_V" else -p["current_A"]
    for attempt in range(p["overrange_retries"] + 1):
        _wait(ctx)
        _check_source(source, current=current,
                      compliance=p["compliance_V"], route=route)
        voltage = float(meter.voltage)
        if not math.isfinite(voltage) or abs(voltage) >= 1e30:
            event = {"polarity": key, "sample": len(record[key]) + 1,
                     "attempt": attempt + 1, "voltage": repr(voltage)}
            record.setdefault("invalid_readings", []).append(event)
            logger.warning("2182 invalid voltage %s; route=%s, polarity=%s, attempt=%d/%d",
                           voltage, " ".join(route), key, attempt + 1,
                           p["overrange_retries"] + 1)
            _check_source(source, current=current,
                          compliance=p["compliance_V"], route=route)
            if attempt == p["overrange_retries"]:
                raise RuntimeError("2182 returned a nonfinite/overrange voltage "
                                   f"after {attempt + 1} attempts; check voltage contacts and settling")
            _wait(ctx, p["overrange_retry_delay_s"])
            continue
        record[key].append(voltage)
        _check_source(source, current=current,
                      compliance=p["compliance_V"], route=route)
        return


def _measure_resistance(ctx, source, meter, matrix, route, chart, repetition, p):
    _wait(ctx)
    # Keep output enabled: compliance while the current path is open is
    # expected. Check source status only after reconnecting and settling.
    matrix.switch_commute_reset_all()
    _wait(ctx, p["relay_settle_s"])
    matrix.switch_commute_exclusive(*route)
    _wait(ctx, p["relay_settle_s"])

    record = {"repetition": repetition, "relays": list(route),
              "current_A": p["current_A"], "nplc": p["nplc"],
              "compliance_V": p["compliance_V"],
              "current_settle_s": p["current_settle_s"],
              "relay_settle_s": p["relay_settle_s"],
              "voltage_range_V": p["voltage_range_V"],
              "overrange_retries": p["overrange_retries"],
              "overrange_retry_delay_s": p["overrange_retry_delay_s"],
              "positive_V": [], "negative_V": []}
    # Persist even partial raw acquisitions when stopped or a reading fails.
    chart.x_series.raw.append(repetition)
    chart.y_series.raw.append(record)
    for sign, key in ((1, "positive_V"), (-1, "negative_V")):
        _wait(ctx)
        source.source_current = sign * p["current_A"]
        _wait(ctx, p["current_settle_s"])
        for _ in range(p["samples_per_polarity"]):
            _read_voltage(ctx, source, meter, route, record, key, p)
    resistance = abs(fmean(record["positive_V"]) - fmean(record["negative_V"])) / (2 * p["current_A"])
    if not math.isfinite(resistance) or resistance <= 0:
        raise ValueError("Not finite resistance")
    record["resistance_ohm"] = resistance
    return resistance


def _cleanup(source, matrix, delay):
    """Do not switch relays if the source could not be disabled."""
    source_off = False
    failures = []
    try:
        source.disable_source()
        source_off = True
    except Exception as exc:
        failures.append(exc)
        logger.exception("Could not disable the 6221 output")
    try:
        source.source_current = 0
    except Exception as exc:
        failures.append(exc)
        logger.exception("Could not zero the 6221 current")
    if source_off:
        # Cleanup delay must also run when the stop event is set.
        from time import sleep
        sleep(delay)
        try:
            matrix.switch_commute_reset_all()
        except Exception as exc:
            failures.append(exc)
            logger.exception("Could not open the relay matrix")
    if failures:
        raise RuntimeError("Instrument cleanup failed; check output and relay state") from failures[0]


def van_der_pauw(ctx: TaskContext) -> None:
    p = PLUGIN.parse_parameters(ctx.parameters)
    routes = relay_routes(p)  # Validate mapping before touching hardware.
    source, meter, matrix = (ctx.instruments[k] for k in ("source", "meter", "matrix"))
    ra_chart = _chart("RA", "RA = V43 / I12")
    rb_chart = _chart("RB", "RB = V14 / I23")
    rs_chart = _chart("Sheet resistance", "Rs", "ohm/square")
    ctx.data.extend([ra_chart, rb_chart, rs_chart])
    completed = 0
    discarded = 0
    try:
        _wait(ctx)
        source.disable_source()
        source.reset()
        source.disable_source()
        source.source_current = 0
        source.source_compliance = p["compliance_V"]
        source.source_auto_range = True
        source.output_low_grounded = False
        source.write(":FORM:SREG ASC")
        meter.reset()
        # OPC? waits for command completion, not analog settling. Ensure idle
        # first: OPC? with continuous initiation can lock up the 2182.
        meter.write(":INIT:CONT OFF")
        meter.write(":ABOR")
        if meter.ask("*OPC?").strip() != "1":
            raise RuntimeError("2182 reset did not complete")
        meter.active_channel = 1
        meter.channel_function = "voltage"
        meter.voltage_nplc = p["nplc"]
        meter.auto_zero_enabled = True
        meter.ch_1.voltage_offset_enabled = False
        if p["voltage_range_V"]:
            meter.ch_1.voltage_range = p["voltage_range_V"]
        else:
            meter.ch_1.voltage_range_auto_enabled = True
        meter.trigger_immediately()
        meter.trigger_count = 1
        meter.write(":SAMP:COUN 1")
        if meter.ask("*OPC?").strip() != "1":
            raise RuntimeError("2182 configuration did not complete")
        for instrument in (source, meter):
            errors = instrument.check_errors()
            if any(int(error[0]) != 0 for error in errors):
                raise RuntimeError(f"Instrument configuration errors: {errors}")

        source.source_current = p["current_A"]
        source.enable_source()
        for repetition in range(1, p["repetitions"] + 1):
            _wait(ctx)
            try:
                ra = _measure_resistance(ctx, source, meter, matrix, routes["RA"], ra_chart, repetition, p)
                rb = _measure_resistance(ctx, source, meter, matrix, routes["RB"], rb_chart, repetition, p)
                rs = sheet_resistance(ra, rb)
            except _Compliance as exc:
                discarded += 1
                # Reject both resistances even if RA completed before RB failed.
                for chart in (ra_chart, rb_chart):
                    for record in chart.y_series.raw:
                        if record["repetition"] == repetition:
                            record.pop("resistance_ohm", None)
                            record["accepted"] = False
                            record["discard_reason"] = "voltage_compliance"
                            record["source_error"] = str(exc)
                logger.warning("Van der Pauw repetition %d discarded: %s", repetition, exc)
            else:
                # Publish only complete RA/RB/Rs observations without compliance.
                completed += 1
                ra_chart.add_processed_pair(repetition, ra)
                rb_chart.add_processed_pair(repetition, rb)
                rs_chart.add_processed_pair(repetition, rs)
            if repetition < p["repetitions"]:
                _wait(ctx, p["repeat_delay_s"])
    except _Stopped:
        logger.info("Van der Pauw stopped after %d complete repetitions", completed)
    finally:
        _cleanup(source, matrix, p["relay_settle_s"])
        logger.info("Van der Pauw: %d valid cycles, %d discarded for compliance", completed, discarded)



PLUGIN = TaskSpec(
    id="van_der_pauw", name="Van der Pauw",
    description="RA, RB and Rs histograms with current reversal; compliance cycles are discarded.",
    run=van_der_pauw,
    instruments={"source": "keithley6221", "meter": "keithley2182", "matrix": "relay_matrix"},
    parameters={
        "repetitions": ParameterSpec(int, 1, minimum=1),
        "current_A": ParameterSpec(float, 1e-4, minimum=1e-12, maximum=0.105),
        "compliance_V": ParameterSpec(float, 1.0, minimum=0.1, maximum=105),
        "nplc": ParameterSpec(float, 5.0, minimum=0.01, maximum=50),
        "samples_per_polarity": ParameterSpec(int, 1, minimum=1),
        "overrange_retries": ParameterSpec(int, 3, minimum=0, maximum=10),
        "overrange_retry_delay_s": ParameterSpec(float, 0.5, minimum=0, maximum=10),
        "current_settle_s": ParameterSpec(float, 0.2, minimum=0),
        "relay_settle_s": ParameterSpec(float, 0.1, minimum=0),
        "repeat_delay_s": ParameterSpec(float, 0.0, minimum=0),
        "voltage_range_V": ParameterSpec(float, 0.0, choices=(0.0, 0.01, 0.1, 1.0, 10.0, 100.0)),
        "current_hi_group": ParameterSpec(str, "c"),
        "current_lo_group": ParameterSpec(str, "d"),
        "voltage_hi_group": ParameterSpec(str, "a"),
        "voltage_lo_group": ParameterSpec(str, "b"),
        **{f"contact_{i}": ParameterSpec(int, i, minimum=1) for i in range(1, 5)},
        "merge_chart_files": ParameterSpec(bool, True),
    },
)
