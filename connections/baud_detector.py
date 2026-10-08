import concurrent.futures
import json
import logging
import os
import string
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from pymeasure.adapters import SerialAdapter
from pyvisa.constants import StopBits

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 0.15
CACHE_TIMEOUT = 0.1

HANDSHAKE_TOKENS = {"ok", "ready"}

FAST_BAUDRATES = (9600, 115200, 19200)
BAUDRATES = (
    110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200,
    115200, 128000, 230400, 256000, 460800, 576000, 921600,
)

SERIAL_CACHE_FILE = os.path.join(os.path.dirname(__file__), "wasic_serial_cache.tmp")
BLACKLIST_THRESHOLD = 5

_TRIAL_TIMEOUT_MULTIPLIER = 6
_TRIAL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


@dataclass(frozen=True)
class BaudTrialResult:
    baud_rate: int
    stop_bits: StopBits
    idn: str


class SerialParamCache:
    def __init__(self, path: str = SERIAL_CACHE_FILE) -> None:
        self.path = path

    def read(self) -> dict:
        try:
            if not os.path.exists(self.path):
                return {}

            with open(self.path, "r", encoding="utf-8") as file:
                return json.load(file) or {}
        except Exception:
            return {}

    def write(self, data: dict) -> None:
        try:
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as file:
                json.dump(data, file)

            os.replace(tmp_path, self.path)
        except Exception:
            logger.debug("Failed to write serial cache", exc_info=True)

    def get(self, port: str) -> Optional[dict]:
        entry = self.read().get(self._key(port))
        if not entry or entry.get("blacklisted"):
            return None
        return entry

    def save_success(self, port: str, baud_rate: int, stop_bits: StopBits) -> None:
        cache = self.read()

        cache[self._key(port)] = {
            "baud_rate": int(baud_rate),
            "stop_bits": stop_bits.name,
            "ts": int(time.time()),
        }

        self.write(cache)

    def register_failure(self, port: str) -> int:
        cache = self.read()
        key = self._key(port)

        entry = cache.get(key, {})
        count = int(entry.get("failed_attempts", 0)) + 1

        entry["failed_attempts"] = count

        if count >= BLACKLIST_THRESHOLD:
            entry["blacklisted"] = True
            entry["blacklisted_ts"] = int(time.time())

        cache[key] = entry
        self.write(cache)

        return count

    @staticmethod
    def _key(port: str) -> str:
        return str(port).upper()


class BaudTrialDetector:
    """Rileva baud rate e stop bit interrogando una porta seriale."""

    def __init__(
        self,
        port: Any,
        data: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        scan_all: bool = False,
        print_all: bool = False,
        clear_on_connect: bool = True,
        cache: Optional[SerialParamCache] = None,
    ) -> None:
        self.port = str(port)
        self.query_cmd = prepare_query_cmd(data)
        self.timeout = timeout
        self.scan_all = scan_all
        self.print_all = print_all
        self.clear_on_connect = clear_on_connect
        self.resource_name = build_resource_name(port)
        self.cache = cache or SerialParamCache()

    def detect(self) -> Optional[BaudTrialResult]:
        cached_combo: Optional[tuple[int, StopBits]] = None
        cached_entry = self.cache.get(self.port)

        if cached_entry is not None:
            try:
                cached_combo = (
                    int(cached_entry["baud_rate"]),
                    parse_stop_bits(cached_entry["stop_bits"]),
                )
            except Exception:
                cached_combo = None

        cached = self._try_cached_params()
        if cached is not None:
            return cached

        for baud_rate in self._baudrates_to_try():
            for stop_bits in (StopBits.one, StopBits.two):
                if cached_combo is not None and baud_rate == cached_combo[0] and stop_bits == cached_combo[1]:
                    continue

                idn = self._try_candidate(baud_rate, stop_bits)

                if idn is not None:
                    self.cache.save_success(self.port, baud_rate, stop_bits)
                    return BaudTrialResult(baud_rate, stop_bits, idn)

        self.cache.register_failure(self.port)
        return None

    def _baudrates_to_try(self) -> tuple[int, ...]:
        return BAUDRATES if self.scan_all else FAST_BAUDRATES

    def _try_cached_params(self) -> Optional[BaudTrialResult]:
        entry = self.cache.get(self.port)
        if entry is None:
            return None

        try:
            baud_rate = int(entry["baud_rate"])
            stop_bits = parse_stop_bits(entry["stop_bits"])
        except Exception:
            return None

        idn = self._try_candidate(baud_rate, stop_bits)
        if idn is None:
            return None

        logger.debug(
            "Using cached serial params for port %s: baud=%s stop_bits=%s",
            self.port,
            baud_rate,
            stop_bits,
        )

        return BaudTrialResult(baud_rate, stop_bits, idn)

    def _try_candidate(self, baud_rate: int, stop_bits: StopBits) -> Optional[str]:
        future = _TRIAL_EXECUTOR.submit(
            self._try_candidate_worker,
            baud_rate,
            stop_bits,
        )

        timeout = max(0.3, self.timeout * _TRIAL_TIMEOUT_MULTIPLIER)

        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            self._debug("Timeout at baud=%s stop_bits=%s", baud_rate, stop_bits)
            return None
        except Exception:
            self._debug(
                "Exception at baud=%s stop_bits=%s",
                baud_rate,
                stop_bits,
                exc_info=True,
            )
            return None

    def _try_candidate_worker(self, baud_rate: int, stop_bits: StopBits) -> Optional[str]:
        adapter: Optional[SerialAdapter] = None

        try:
            adapter = open_serial_adapter(
                self.port,
                baud_rate,
                stop_bits,
                self.timeout,
            )

            self._debug("Trying baud=%s stop_bits=%s", baud_rate, stop_bits)

            if self.clear_on_connect:
                safe_clear(adapter, self.resource_name, baud_rate, self.print_all)

            time.sleep(0.01)

            adapter.write(self.query_cmd)

            for _ in range(4):
                try:
                    response = adapter.read()
                except Exception:
                    break

                if response == "":
                    break

                parsed = parse_response(response)
                if parsed is not None:
                    return parsed

            try:
                return parse_response(adapter.ask(self.query_cmd))
            except Exception:
                return None

        except Exception:
            self._debug(
                "Candidate failed at baud=%s stop_bits=%s",
                baud_rate,
                stop_bits,
                exc_info=True,
            )
            return None

        finally:
            close_quietly(adapter)

    def _debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.print_all:
            logger.debug(
                f"{self.resource_name}: {message}",
                *args,
                **kwargs,
            )


def query_idn(
    port: str,
    baud_rate: int,
    stop_bits: StopBits,
    timeout: float,
    drain_reads: int = 0,
    idn_reads: int = 2,
) -> Optional[str]:
    adapter: Optional[SerialAdapter] = None

    try:
        adapter = open_serial_adapter(port, baud_rate, stop_bits, timeout)

        for _ in range(drain_reads):
            try:
                line = str(adapter.read()).strip().lower()
            except Exception:
                break

            if line and line not in HANDSHAKE_TOKENS:
                break

        adapter.write("*IDN?")

        for _ in range(idn_reads):
            try:
                parsed = parse_response(adapter.read())
            except Exception:
                break

            if parsed is not None:
                return parsed

        return None

    except Exception:
        return None

    finally:
        close_quietly(adapter)


def open_serial_adapter(
    port: str,
    baud_rate: int,
    stop_bits: StopBits,
    timeout: float,
) -> SerialAdapter:
    adapter = SerialAdapter(
        port,
        baudrate=baud_rate,
        bytesize=8,
        stopbits=2 if stop_bits == StopBits.two else 1,
        timeout=timeout,
        read_termination="\n",
        write_termination="\n",
    )

    if adapter.connection is not None:
        adapter.connection.timeout = timeout
        adapter.connection.write_timeout = timeout

    return adapter


def safe_clear(adapter: Any, resource_name: str, baud_rate: int, print_all: bool) -> None:
    try:
        low_level = getattr(adapter, "instrument", None) or getattr(adapter, "connection", None)

        if low_level is not None and hasattr(low_level, "clear"):
            try:
                low_level.clear()
            except Exception:
                pass

        try:
            adapter.write("*CLS")
        except Exception:
            pass

    except Exception as error:
        if print_all:
            logger.debug(
                "clear/*CLS failed for %s at %s: %s",
                resource_name,
                baud_rate,
                error,
            )


def parse_response(response: Any) -> Optional[str]:
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

        return bool(response_str.strip()) and any(
            char in string.printable for char in response_str
        )

    except Exception:
        return False


def parse_stop_bits(value: Any) -> StopBits:
    try:
        return StopBits[value]
    except Exception:
        try:
            return StopBits(int(value))
        except Exception:
            return StopBits.one


def build_resource_name(port: Any) -> str:
    port_str = str(port).upper()

    if port_str.startswith("COM"):
        digits = "".join(char for char in port_str if char.isdigit())
        return f"ASRL{digits}::INSTR"

    return str(port)


def prepare_query_cmd(data: Any) -> str:
    if data is None:
        return "*IDN?"

    if isinstance(data, bytes):
        try:
            return data.decode().strip() or "*IDN?"
        except Exception:
            return "*IDN?"

    return str(data).strip() or "*IDN?"


def close_quietly(adapter: Optional[Any]) -> None:
    try:
        if adapter is not None:
            adapter.close()
    except Exception:
        pass


def detect_baud_rate(
    port: Any,
    data: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    scan_all: bool = False,
    print_all: bool = False,
    clear_on_connect: bool = True,
) -> Optional[tuple[int, str]]:
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

    return result.baud_rate, result.idn


def detect_baud_wrapper(
    port: Any,
    target: list[tuple[str, str, int]],
    target_lock: Lock,
) -> None:
    result = detect_baud_rate(port=port)

    if result is None:
        logger.debug("Failed to detect baud rate for port %s", port)
        return

    baud_rate, idn = result
    row = (str(port), idn, baud_rate)

    logger.debug(
        "BR Detection on port %s with Baud %s and IDN %s",
        row[0],
        row[2],
        row[1],
    )

    with target_lock:
        target.append(row)