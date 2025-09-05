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
from typing import Tuple, List, Optional, Any
from config import Config
from threading import Lock
import logging
from pyvisa.constants import StopBits
# from pyvisa.resources import MessageBasedResource  # unused
from easy_scpi.scpi_instrument import SCPI_Instrument

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 0.8  # seconds (faster; devices are \n-terminated)
HANDSHAKE_TOKENS = {"ok", "ready"}

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
    """Save the successful serial parameters for a port into a temp JSON file.

    Handshake/banner lines are treated as startup noise and are NOT stored as a
    runtime handshake requirement (previous logic removed to avoid false positives).
    """
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


def load_serial_params(port: str) -> Optional[Tuple[int, StopBits, str]]:
    """Load cached params for a port. Returns (baud_rate, StopBits, id_string) or None.

    Procedure (no command echo expected):
      1. Connect with cached params.
      2. Drain any immediate incoming lines (noise, banners, "ok", "ready").
      3. Issue *IDN? explicitly.
      4. Read several lines, skipping empty and handshake tokens.
      5. First validated remaining line becomes the ID string.
    If no valid line is found the cache entry is ignored.
    """
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        entry = cache.get(key)
        if not entry:
            return None
        if entry.get("blacklisted"):
            logger.debug("Port %s is blacklisted (skipping cached params)", key)
            return None
        baud = int(entry.get("baud_rate"))
        sb = entry.get("stop_bits")
        if baud is None or sb is None:
            return None
        try:
            stopbits = StopBits[sb]
        except Exception:
            try:
                stopbits = StopBits(int(sb))
            except Exception:
                stopbits = StopBits.one
        inst: Optional[SCPI_Instrument] = None
        try:
            inst = SCPI_Instrument(
                port=port,
                baud_rate=baud,
                data_bits=8,
                stop_bits=stopbits,
                timeout=int(0.5 * 1000),
                read_termination="\n",
                write_termination="\n",
                encoding="ascii",
                backend="@py"
            )
            inst.connect(2)
            if inst.instrument is not None:
                original_timeout = inst.instrument.timeout
                try:
                    inst.instrument.timeout = 100
                    while True:
                        try:
                            line = inst.read()
                        except pyvisa.errors.VisaIOError:
                            break
                        except Exception:
                            break
                        line_s = str(line).strip()
                        if not line_s:
                            continue
                        if line_s.lower() in HANDSHAKE_TOKENS:
                            continue
                finally:
                    if inst.instrument is not None:
                        inst.instrument.timeout = original_timeout
            try:
                inst.write("*IDN?")
            except Exception:
                raise
            idn_line: Optional[str] = None
            for _ in range(5):
                try:
                    resp = inst.read()
                except pyvisa.errors.VisaIOError:
                    break
                except Exception:
                    break
                resp_s = str(resp).strip()
                if not resp_s:
                    continue
                if resp_s.lower() in HANDSHAKE_TOKENS:
                    continue
                if validate_response(resp_s):
                    idn_line = "".join(c for c in resp_s if c in string.printable)
                    break
            if idn_line:
                inst.disconnect()
                return (baud, stopbits, idn_line)
            # fallback single query
            try:
                alt = inst.query("*IDN?")
                alt_s = str(alt).strip()
                if alt_s and alt_s.lower() not in HANDSHAKE_TOKENS and validate_response(alt_s):
                    alt_idn = "".join(c for c in alt_s if c in string.printable)
                    inst.disconnect()
                    return (baud, stopbits, alt_idn)
            except Exception:
                pass
            inst.disconnect()
            return None
        except Exception:
            try:
                if inst is not None and inst.is_connected:
                    inst.disconnect()
            except Exception:
                pass
            return None
    except Exception:
        return None


# ---------------------- Internal helper utilities ---------------------- #

def _build_resource_name(port: Any) -> str:
    """Return VISA-style resource name for logging (does not validate)."""
    p = str(port).upper()
    if p.startswith("COM"):
        digits = "".join(c for c in p if c.isdigit())
        return f"ASRL{digits}::INSTR"
    return str(port)

def _prepare_query_cmd(data: Any) -> str:
    if data is None:
        return "*IDN?"
    if isinstance(data, bytes):
        try:
            return data.decode().strip() or "*IDN?"
        except Exception:
            return "*IDN?"
    return str(data)

def _drain(inst: SCPI_Instrument, timeout_ms: int, max_reads: int | None = None) -> None:
    """Drain any pending lines from the instrument.

    timeout_ms: temporary timeout used while draining.
    max_reads: number of successful reads to attempt (None = until timeout).
    """
    if inst.instrument is None:
        return
    old_timeout = getattr(inst.instrument, "timeout", None)
    try:
        inst.instrument.timeout = timeout_ms
        reads = 0
        while True:
            if max_reads is not None and reads >= max_reads:
                break
            try:
                _ = inst.read()
                reads += 1
            except pyvisa.errors.VisaIOError:
                break
            except Exception:
                break
    finally:
        if old_timeout is not None and inst.instrument is not None:
            inst.instrument.timeout = old_timeout

def _safe_clear(inst: SCPI_Instrument, resource_name: str, baudrate: int, print_all: bool) -> None:
    if inst.instrument is None:
        return
    try:
        if hasattr(inst.instrument, "clear"):
            try:
                inst.instrument.clear()  # type: ignore[attr-defined]
            except pyvisa.errors.VisaIOError:
                pass
        try:
            inst.write("*CLS")
        except Exception:
            pass
    except Exception as e:
        if print_all:
            logger.debug("clear/*CLS failed for %s at %s: %s", resource_name, baudrate, e)

# ---------------------- Public API ---------------------- #

def detect_baud_rate(
    port,
    data=None,
    timeout: float = DEFAULT_TIMEOUT,
    scan_all: bool = False,
    print_all: bool = False,
    clear_on_connect: bool = True,
) -> Tuple[int, str] | None:
    """Detect baud rate for a serial instrument.

    Tries common baud rates (or all if scan_all) and both 1 / 2 stop bits.
    Returns (baudrate, idn_string) or None on failure.
    Uses easy_scpi for a slightly higher-level & thread-safe wrapper.
    """
    fast_order = (9600, 115200,19200, )
    baudrates = BAUDRATES if scan_all else fast_order
    # Check if  cached
    cached = load_serial_params(port)
    if cached is not None:
        logger.debug("Using cached serial params for port %s: %s", port, cached)
        baud, sb, idn = cached
        return (baud, idn)
    # No cache, iterate
    query_cmd = _prepare_query_cmd(data)
    resource_name = _build_resource_name(port)
    stopbits_to_try = [StopBits.one, StopBits.two]

    for baudrate in baudrates:
        for stopbits in stopbits_to_try:
            logger.debug(
                "Trying baudrate %s on resource %s with stopbits %s",
                baudrate,
                resource_name,
                stopbits,
            )
            time.sleep(0.1)  # brief pause between attempts
            inst: Optional[SCPI_Instrument] = None
            try:
                inst = SCPI_Instrument(
                    port=port,
                    baud_rate=baudrate,
                    data_bits=8,
                    stop_bits=stopbits,
                    timeout=int(timeout * 1000),
                    read_termination="\n",
                    write_termination="\n",
                    encoding="ascii",
                    backend="@py"
                )
                inst.connect(2)  # performs implicit *IDN?

                if clear_on_connect:
                    _safe_clear(inst, resource_name, baudrate, print_all)
                time.sleep(0.1)  # brief pause between attempts

                # Issue our detection query
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

                first_stripped = str(first).strip()
                logger.debug(
                    "Received response from %s at %s: '%s'",
                    resource_name,
                    baudrate,
                    first_stripped,
                )
                if (
                    first_stripped
                    and first_stripped.lower() not in HANDSHAKE_TOKENS
                    and validate_response(first)
                ):
                    current_idn = "".join(c for c in first_stripped if c in string.printable)
                    save_serial_params(port, baudrate, stopbits)
                    return (baudrate, current_idn)

                # Handshake token path: attempt a few more lines quickly
                for _ in range(3):
                    try:
                        nxt = inst.read()
                    except pyvisa.errors.VisaIOError:
                        break
                    nxt_s = str(nxt).strip()
                    if not nxt_s:
                        continue
                    if nxt_s.lower() in HANDSHAKE_TOKENS:
                        continue
                    if validate_response(nxt):
                        current_idn = "".join(c for c in nxt_s if c in string.printable)
                        # previously stored handshake=True; removed (banner is transient)
                        save_serial_params(port, baudrate, stopbits)
                        return (baudrate, current_idn)

            except Exception as e:
                if print_all:
                    logger.debug("Exception for %s at %s: %s", resource_name, baudrate, e)
            finally:
                try:
                    if inst is not None and inst.is_connected:
                        inst.disconnect()
                except Exception:
                    pass
    # All attempts failed: record a failure count (may lead to blacklist)
    try:
        _increment_failure_count(port)
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
