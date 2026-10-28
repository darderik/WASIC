"""Per-instrument communication and connection lifetime protection."""
from contextlib import contextmanager
from functools import wraps
from threading import RLock

from pymeasure.instruments import Channel, Instrument


class InstrumentInUseError(RuntimeError):
    """A running task still needs this connection, including for cleanup."""


class InstrumentIO:
    """Serialize exchanges, without holding a lock for a whole task.

    Entry construction installs guards on the driver's communication methods.
    The original driver identity, properties and channels are preserved. Existing
    driver locks (e.g. RelayMatrix's response/OK handshake) are reused so nested
    calls all acquire the same reentrant lock.
    """

    _binding_lock = RLock()
    _methods = (
        "ask", "values", "binary_values", "write", "read",
        "write_bytes", "read_bytes", "write_binary_values", "read_binary_values",
    )

    def __init__(self, lock=None):
        self.lock = lock if lock is not None else RLock()
        self._users = 0
        self._closed = False

    @classmethod
    def for_instrument(cls, instrument):
        """Bind once, also when multiple entries refer to the same driver."""
        # Lightweight stand-ins used by library callers need not be PyMeasure
        # drivers. Their lifetime is still protected by their entry.
        if not isinstance(instrument, Instrument):
            return cls()
        with cls._binding_lock:
            existing = vars(instrument).get("_wasic_io")
            if existing is not None:
                return existing
            io = cls(vars(instrument).get("_io_lock"))
            io._bind(instrument)
            return io

    def _bind(self, component):
        if vars(component).get("_wasic_io") is self:
            return
        component._io_lock = self.lock
        component._wasic_io = self
        for name in self._methods:
            method = getattr(component, name, None)
            if callable(method):
                setattr(component, name, self._guard(method))

        # Channel.ask() performs its own write/read instead of calling the
        # parent's ask(). Guard both existing and subsequently created channels.
        add_child = component.add_child

        @wraps(add_child)
        def add_managed_child(*args, **kwargs):
            with self.transaction():
                child = add_child(*args, **kwargs)
                self._bind(child)
                return child

        component.add_child = add_managed_child
        for value in tuple(vars(component).values()):
            if isinstance(value, Channel):
                self._bind(value)
            elif isinstance(value, dict):
                for child in tuple(value.values()):
                    if isinstance(child, Channel):
                        self._bind(child)

    def _guard(self, method):
        @wraps(method)
        def guarded(*args, **kwargs):
            with self.transaction():
                return method(*args, **kwargs)
        return guarded

    @contextmanager
    def transaction(self):
        """Cover a whole query or an explicitly indivisible command sequence."""
        with self.lock:
            if self._closed:
                raise RuntimeError("Instrument connection is closed; reconnect before use")
            yield

    def retain(self):
        """Pin the connection only; leave communication available to everyone."""
        with self.transaction():
            self._users += 1

    def release(self):
        with self.lock:
            if self._users <= 0:
                raise RuntimeError("Instrument connection was released without a retain")
            self._users -= 1

    def close(self, close_connection):
        with self.lock:
            if self._users:
                raise InstrumentInUseError("Instrument is in use by a task; connection kept open")
            if not self._closed:
                close_connection()
                self._closed = True
