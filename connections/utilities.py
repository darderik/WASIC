# MIT License
#
# Copyright (c) 2023 Fikret Garipay
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import string
import pyvisa
import os
import json
import tempfile
from typing import Tuple, List, Optional
from config import Config
from threading import Lock
import logging
from pyvisa.constants import StopBits
# from pyvisa.resources import MessageBasedResource  # unused
from easy_scpi.scpi_instrument import SCPI_Instrument

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 0.5  # seconds (faster; devices are \n-terminated)
BAUDRATES = (
    110,
    300,
    600,
    1200,
    2400,
    4800,
    9600,
    14400,
    19200,
    115200,
    128000,
    230400,
    256000,
    460800,
    576000,
    921600,
)

# Simple JSON cache of last-working serial params per-port.
# Stored next to this module; user may delete file to clear state.
SERIAL_CACHE_FILE = os.path.join(os.path.dirname(__file__), "wasic_serial_cache.tmp")

# Blacklist threshold: number of failed detection attempts before marking a port blacklisted.
BLACKLIST_THRESHOLD = 5


def _read_serial_cache() -> dict:
    try:
        if not os.path.exists(SERIAL_CACHE_FILE):
            return {}
        with open(SERIAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_serial_cache(data: dict) -> None:
    try:
        # best-effort write
        with open(SERIAL_CACHE_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(SERIAL_CACHE_FILE + ".tmp", SERIAL_CACHE_FILE)
    except Exception:
        pass


def _increment_failure_count(port: str) -> int:
    """Increment failed_attempts for a port and mark blacklisted when threshold reached."""
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        entry = cache.get(key, {})
        count = int(entry.get("failed_attempts", 0)) + 1
        entry["failed_attempts"] = count
        if count >= BLACKLIST_THRESHOLD:
            entry["blacklisted"] = True
            entry["blacklisted_ts"] = int(time.time())
        cache[key] = entry
        _write_serial_cache(cache)
        return count
    except Exception:
        return 0


def _reset_failure_count(port: str) -> None:
    """Clear failed_attempts and blacklisted flags for a port on successful detection."""
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        entry = cache.get(key)
        if not entry:
            return
        entry.pop("failed_attempts", None)
        entry.pop("blacklisted", None)
        entry.pop("blacklisted_ts", None)
        cache[key] = entry
        _write_serial_cache(cache)
    except Exception:
        pass


def save_serial_params(port: str, baud_rate: int, stop_bits: StopBits) -> None:
    """Save the successful serial parameters for a port into a temp JSON file."""
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        cache[key] = {
            "baud_rate": int(baud_rate),
            "stop_bits": stop_bits.name if hasattr(stop_bits, "name") else str(stop_bits),
            "ts": int(time.time()),
        }
        _write_serial_cache(cache)
        # reset failure counter when we have a success
        try:
            _reset_failure_count(port)
        except Exception:
            pass
    except Exception:
        pass


def load_serial_params(port: str) -> Optional[Tuple[int, StopBits]]:
    """Load cached params for a port. Returns (baud_rate, StopBits) or None."""
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        entry = cache.get(key)
        if not entry:
            return None
        # Respect blacklist: do not return params if port is blacklisted
        if entry.get("blacklisted"):
            logger.debug("Port %s is blacklisted (skipping cached params)", key)
            return None
        baud = int(entry.get("baud_rate"))
        sb = entry.get("stop_bits")
        # Convert back to StopBits when possible
        try:
            stopbits = StopBits[sb]
        except Exception:
            # Fallback: try numeric value
            try:
                stopbits = StopBits(int(sb))
            except Exception:
                stopbits = StopBits.one
        return (baud, stopbits)
    except Exception:
        return None


def detect_baud_rate(
    port,
    data=None,
    timeout: float = DEFAULT_TIMEOUT,
    scan_all: bool = False,
    print_all: bool = False,
) -> Tuple[int, str] | None:
    """Try to detect a device baud rate using easy_scpi.SCPI_Instrument.

    Optimized for serial instruments using \n termination. Tries 1 and 2 stop bits
    and returns (baudrate, idn_string) on success.
    """
    # Favor common/fast first; fall back to the rest (kept for scan_all)
    fast_order = ( 9600, 19200, 115200,)
    baudrates = BAUDRATES if scan_all else fast_order

    # Prepare query string
    if data is None:
        query_cmd = "*IDN?"
    elif isinstance(data, bytes):
        try:
            query_cmd = data.decode().strip()
        except Exception:
            query_cmd = "*IDN?"
    else:
        query_cmd = str(data)

    # Convert port like 'COM3' -> ASRL resource name (for logging only)
    port_upper = str(port).upper()
    if port_upper.startswith("COM"):
        digits = "".join([c for c in port_upper if c.isdigit()])
        resource_name = f"ASRL{digits}::INSTR"
    else:
        resource_name = port

    # If we have cached params for this port, try them first and exit early on success.
    try:
        cached = load_serial_params(port)
        if cached is not None:
            cached_baud, cached_stopbits = cached
            logger.debug("Found cached serial params for %s: %s %s", resource_name, cached_baud, cached_stopbits)
            try:
                inst = SCPI_Instrument(
                    port=port,
                    baud_rate=cached_baud,
                    data_bits=8,
                    stop_bits=cached_stopbits,
                    timeout=int(timeout * 1000),
                    read_termination="\n",
                    write_termination="\n",
                    encoding="ascii",
                )
                inst.connect(explicit_remote=2)
                try:
                    first = inst.query(query_cmd)
                    first_stripped = str(first).strip()
                    logger.debug(
                        "Cached attempt received response from %s at %s: '%s'", resource_name, cached_baud, first_stripped
                    )
                    if first_stripped and first_stripped.lower() not in {"ok", "ready"} and validate_response(first):
                        current_idn = "".join(c for c in first_stripped if c in string.printable)
                        # Save again to refresh timestamp and exit early
                        save_serial_params(port, cached_baud, cached_stopbits)
                        try:
                            if inst is not None and inst.is_connected:
                                inst.disconnect()
                        except Exception:
                            pass
                        return (cached_baud, current_idn)
                except Exception:
                    # Cached params not valid; fall through to scanning
                    logger.debug("Cached serial params for %s did not work; falling back", resource_name)
                finally:
                    try:
                        if inst is not None and inst.is_connected:
                            inst.disconnect()
                    except Exception:
                        pass
            except Exception:
                # Could not open with cached params; continue to full scan
                logger.debug("Could not open %s with cached params; will scan", resource_name)
    except Exception:
        # Ignore cache errors and continue
        pass

    stopbits_to_try = [StopBits.one, StopBits.two]

    for baudrate in baudrates:
        for stopbits in stopbits_to_try:
            logger.debug(
                "Trying baudrate %s on resource %s with stopbits %s",
                baudrate,
                resource_name,
                stopbits,
            )
            inst: Optional[SCPI_Instrument] = None
            try:
                # Build instrument with desired serial params; easy_scpi forwards these
                inst = SCPI_Instrument(
                    port=port,
                    # ensure params are applied before first query in connect()
                    baud_rate=baudrate,
                    data_bits=8,
                    stop_bits=stopbits,
                    timeout=int(timeout * 1000),  # ms
                    read_termination="\n",
                    write_termination="\n",
                    encoding="ascii",
                )
                inst.connect(explicit_remote=2)  # no cmd

                # Force a resource clear to recover from possible corrupted state
                try:
                    if inst.instrument is not None and hasattr(inst.instrument, "clear"):
                        try:
                            inst.instrument.clear()
                        except pyvisa.errors.VisaIOError:
                            pass
                    time.sleep(0.1)
                    # Best-effort SCPI status clear (ignored if unsupported)
                    try:
                        inst.write(":SYST:REM")
                        inst.write("*CLS")
                        inst.query("*OPC?")
                    except Exception:
                        pass
                except Exception as e:
                    if print_all:
                        logger.debug(
                            "clear/*CLS failed for %s at %s: %s", resource_name, baudrate, e
                        )

                # Issue query; with proper termination this should be a single read
                try:
                    first = inst.query(query_cmd)
                except Exception as e:
                    logger.debug(
                        "easy_scpi query failed for %s at %s: %s",
                        resource_name,
                        baudrate,
                        e,
                    )
                    continue

                # Fast path: if not a handshake token and looks valid, accept
                first_stripped = str(first).strip()
                logger.debug(
                    "Received response from %s at %s: '%s'", resource_name, baudrate, first_stripped
                )
                if first_stripped and first_stripped.lower() not in {"ok", "ready"} and validate_response(first):
                    current_idn = "".join(c for c in first_stripped if c in string.printable)
                    # Save successful params to cache for next time
                    try:
                        save_serial_params(port, baudrate, stopbits)
                    except Exception:
                        pass
                    return (baudrate, current_idn)
            except Exception as e:
                if print_all:
                    logger.debug(
                        "Exception for %s at %s: %s", resource_name, baudrate, e
                    )
            finally:
                try:
                    if inst is not None and inst.is_connected:
                        inst.disconnect()
                except Exception:
                    pass
            # Very short pause before next try (preserve original timing)
    # All attempts failed -> increment failure count and potentially blacklist the port
    try:
        failures = _increment_failure_count(port)
        logger.debug("Detection failed for %s; failure count=%s", resource_name, failures)
        if failures >= BLACKLIST_THRESHOLD:
            logger.debug("Port %s blacklisted after %s failures", resource_name, failures)
    except Exception:
        pass
    return None


def validate_response(response: str | bytes) -> bool:
    try:
        # Accept both bytes and str
        if isinstance(response, bytes):
            response_str = response.decode(errors="ignore")
        else:
            response_str = str(response)
        return (
            any(c in string.printable for c in response_str)
            and len(response_str.strip()) > 0
        )
    except Exception:
        return False


def detect_baud_wrapper(
    port,
    target: List[Tuple[str, str, int]],
    target_lock: Lock,
) -> None:
    BR_IDN: Optional[Tuple[int, str]] = detect_baud_rate(
        port=port
    )
    # PORT, IDN, BAUD
    if BR_IDN is not None:
        result_tuple: Tuple[str, str, int] = (port, BR_IDN[1], BR_IDN[0])
        logger.debug(
            f"BR Detection on port {result_tuple[0]} with Baud {result_tuple[2]} and IDN {result_tuple[1]}"
        )
        with target_lock:
            target.append(result_tuple)
    else:
        logger.debug(f"Failed to detect baud rate for port {port}")


def is_instrument_in_aliases(idn: str) -> Optional[str]:
    for alias in (Config().get("instr_aliases") or []):
        if alias.lower() in idn.lower():
            return alias
    return None
