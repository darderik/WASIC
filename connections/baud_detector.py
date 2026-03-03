import json
import logging
import os
import string
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, List, Optional, Tuple

from pymeasure.adapters import SerialAdapter
from pyvisa.constants import StopBits

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 0.15
LOAD_CACHE_TIMEOUT = 0.1
LOAD_CACHE_MAX_DRAIN_READS = 2
LOAD_CACHE_MAX_IDN_READS = 2
HANDSHAKE_TOKENS = {"ok", "ready"}
FAST_BAUDRATES = (9600, 115200, 19200)
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

SERIAL_CACHE_FILE = os.path.join(os.path.dirname(__file__), "wasic_serial_cache.tmp")
BLACKLIST_THRESHOLD = 5


@dataclass(frozen=True)
class BaudTrialResult:
    baud_rate: int
    stop_bits: StopBits
    idn: str


class BaudTrialDetector:
    """Try serial baud/stop-bit combinations and return the first valid IDN response."""

    def __init__(
        self,
        port: Any,
        data: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        scan_all: bool = False,
        print_all: bool = False,
        clear_on_connect: bool = True,
    ) -> None:
        self.port = str(port)
        self.query_cmd = _prepare_query_cmd(data)
        self.timeout = timeout
        self.scan_all = scan_all
        self.print_all = print_all
        self.clear_on_connect = clear_on_connect
        self.resource_name = _build_resource_name(port)

    def detect(self) -> Optional[BaudTrialResult]:
        cached = load_serial_params(self.port)
        if cached is not None:
            baud, stop_bits, idn = cached
            logger.debug("Using cached serial params for port %s: %s", self.port, cached)
            return BaudTrialResult(baud_rate=baud, stop_bits=stop_bits, idn=idn)

        for baudrate in (BAUDRATES if self.scan_all else FAST_BAUDRATES):
            for stopbits in (StopBits.one, StopBits.two):
                match = self._try_candidate(baudrate, stopbits)
                if match is not None:
                    save_serial_params(self.port, baudrate, stopbits)
                    return BaudTrialResult(baud_rate=baudrate, stop_bits=stopbits, idn=match)

        _increment_failure_count(self.port)
        return None

    def _try_candidate(self, baudrate: int, stopbits: StopBits) -> Optional[str]:
        adapter: Optional[SerialAdapter] = None
        try:
            adapter = SerialAdapter(
                self.port,
                baudrate=baudrate,
                bytesize=8,
                stopbits=2 if stopbits == StopBits.two else 1,
                timeout=self.timeout,
                read_termination="\n",
                write_termination="\n",
            )
            logger.debug(
                "Trying baudrate %s on resource %s with stopbits %s",
                baudrate,
                self.resource_name,
                stopbits,
            )
            if self.clear_on_connect:
                _safe_clear(adapter, self.resource_name, baudrate, self.print_all)
            time.sleep(0.01)

            adapter.write(self.query_cmd)
            for _ in range(4):
                try:
                    response = adapter.read()
                except Exception:
                    break
                # If response is neither handshake nor idn, string is empty, baudrate/Sbits wrong
                if response == '':
                    break
                parsed = _parse_response(response)
                if parsed is not None:
                    return parsed

            try:
                fallback = adapter.ask(self.query_cmd)
                return _parse_response(fallback)
            except Exception:
                return None

        except Exception as e:
            if self.print_all:
                logger.debug(
                    "Exception for %s at %s (%s): %s",
                    self.resource_name,
                    baudrate,
                    stopbits,
                    e,
                )
            return None
        finally:
            try:
                if adapter is not None:
                    adapter.close()
            except Exception:
                pass


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
        with open(SERIAL_CACHE_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(SERIAL_CACHE_FILE + ".tmp", SERIAL_CACHE_FILE)
    except Exception:
        pass


def _increment_failure_count(port: str) -> int:
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
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        cache[key] = {
            "baud_rate": int(baud_rate),
            "stop_bits": stop_bits.name if hasattr(stop_bits, "name") else str(stop_bits),
            "ts": int(time.time()),
        }
        _write_serial_cache(cache)
        _reset_failure_count(port)
    except Exception:
        pass


def load_serial_params(port: str) -> Optional[Tuple[int, StopBits, str]]:
    try:
        cache = _read_serial_cache()
        key = str(port).upper()
        entry = cache.get(key)
        if not entry or entry.get("blacklisted"):
            return None

        baud = int(entry.get("baud_rate"))
        stop_bits_entry = entry.get("stop_bits")
        if stop_bits_entry is None:
            return None

        try:
            stop_bits = StopBits[stop_bits_entry]
        except Exception:
            try:
                stop_bits = StopBits(int(stop_bits_entry))
            except Exception:
                stop_bits = StopBits.one

        adapter: Optional[SerialAdapter] = None
        try:
            adapter = SerialAdapter(
                str(port),
                baudrate=baud,
                bytesize=8,
                stopbits=2 if stop_bits == StopBits.two else 1,
                timeout=LOAD_CACHE_TIMEOUT,
                read_termination="\n",
                write_termination="\n",
            )
            if adapter.connection is not None:
                previous_timeout = adapter.connection.timeout
                try:
                    adapter.connection.timeout = LOAD_CACHE_TIMEOUT
                    for _ in range(LOAD_CACHE_MAX_DRAIN_READS):
                        try:
                            line = adapter.read()
                        except Exception:
                            break
                        line_s = str(line).strip().lower()
                        if not line_s or line_s in HANDSHAKE_TOKENS:
                            continue
                finally:
                    if adapter.connection is not None:
                        adapter.connection.timeout = previous_timeout

            adapter.write("*IDN?")
            for _ in range(LOAD_CACHE_MAX_IDN_READS):
                try:
                    response = adapter.read()
                except Exception:
                    break
                parsed = _parse_response(response)
                if parsed is not None:
                    return (baud, stop_bits, parsed)
            return None
        except Exception:
            return None
        finally:
            try:
                if adapter is not None:
                    adapter.close()
            except Exception:
                pass
    except Exception:
        return None


def _build_resource_name(port: Any) -> str:
    port_str = str(port).upper()
    if port_str.startswith("COM"):
        digits = "".join(char for char in port_str if char.isdigit())
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


def _safe_clear(inst: Any, resource_name: str, baudrate: int, print_all: bool) -> None:
    try:
        low_level = getattr(inst, "instrument", None) or getattr(inst, "connection", None)
        if low_level is None:
            return

        if hasattr(low_level, "clear"):
            try:
                low_level.clear()
            except Exception:
                pass

        try:
            inst.write("*CLS")
        except Exception:
            pass
    except Exception as error:
        if print_all:
            logger.debug("clear/*CLS failed for %s at %s: %s", resource_name, baudrate, error)


def _parse_response(response: Any) -> Optional[str]:
    response_str = str(response).strip()
    if not response_str:
        return None
    if response_str.lower() in HANDSHAKE_TOKENS:
        return None
    if not validate_response(response_str):
        return None
    return "".join(char for char in response_str if char in string.printable)


def validate_response(response: str | bytes) -> bool:
    try:
        if isinstance(response, bytes):
            response_str = response.decode(errors="ignore")
        else:
            response_str = str(response)
        return bool(response_str.strip()) and any(char in string.printable for char in response_str)
    except Exception:
        return False


def detect_baud_rate(
    port: Any,
    data: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    scan_all: bool = False,
    print_all: bool = False,
    clear_on_connect: bool = True,
) -> Optional[Tuple[int, str]]:
    detector = BaudTrialDetector(
        port=port,
        data=data,
        timeout=timeout,
        scan_all=scan_all,
        print_all=print_all,
        clear_on_connect=clear_on_connect,
    )
    result = detector.detect()
    if result is None:
        return None
    return (result.baud_rate, result.idn)


def detect_baud_wrapper(
    port: Any,
    target: List[Tuple[str, str, int]],
    target_lock: Lock,
) -> None:
    baud_and_idn = detect_baud_rate(port=port)
    if baud_and_idn is None:
        logger.debug("Failed to detect baud rate for port %s", port)
        return

    result = (str(port), baud_and_idn[1], baud_and_idn[0])
    logger.debug(
        "BR Detection on port %s with Baud %s and IDN %s",
        result[0],
        result[2],
        result[1],
    )
    with target_lock:
        target.append(result)
