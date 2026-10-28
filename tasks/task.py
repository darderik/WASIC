from math import e
from config import Config
from typing import List, Callable, Dict, Any, Optional
from threading import Thread, Event, Lock, RLock, current_thread
from wasic_api import TaskSpec, TaskContext
from instruments import Instrument_Entry
from .structures import ChartData
from .chart_io import save_charts_csv
from .helper import str_to_bool
from connections import Connections
import datetime
import os
import logging
import time
import copy
import atexit

logger = logging.getLogger(__name__)


class Task:
    """
    Represents a single task that can be run in a separate thread.
    """

    def __init__(
        self,
        name: str,
        description: str,
        instrs_aliases: List[str],
        function: Callable[..., None],
        data: Optional[List[ChartData]] = None,
        custom_alias: str = "",
        custom_web_status: Optional[Callable] = None,
        parameters: Optional[Dict[str, Any]] = None,
        spec: Optional[TaskSpec] = None,
    ):
        self.name = name
        self.description = description
        self.instr_aliases = instrs_aliases
        self.data = data if data is not None else []  # Initialize if None
        self.exit_flag = Event()
        self.instruments: List[Optional[Instrument_Entry]] = []
        self.function = function
        self.custom_alias = custom_alias
        self._config = Config()
        self.custom_web_status = custom_web_status
        self.thread_handle: Optional[Thread] = None
        self.parameters: Dict[str, Any] = dict(parameters) if parameters is not None else {"merge_chart_files": "false"}
        self.spec = spec
        self.id = spec.id if spec else name
        self.running: bool = False
        self._rlock = RLock()

    @classmethod
    def from_spec(cls, spec: TaskSpec) -> "Task":
        return cls(name=spec.name, description=spec.description,
                   instrs_aliases=[], function=spec.run,
                   parameters=spec.parse_parameters({}), spec=spec)

    def resolve_instruments(self) -> dict:
        resolved = {}
        if self.spec:
            for role, driver_id in self.spec.instruments.items():
                entry = Connections().get_instrument_by_driver(driver_id)
                if entry is None:
                    raise ValueError(f"Missing instrument for {role}: {driver_id}")
                resolved[role] = entry.scpi_instrument
        return resolved

    def _execute(self, context, retained=()) -> None:
        try:
            self.function(context)
        except Exception:
            logger.exception("Task %s failed", self.name)
        finally:
            # self.function includes the task's finally/cleanup. Pins protect
            # only the connection lifetime; no I/O lock is held across the run.
            for io in reversed(retained):
                io.release()
            self.exit_flag.set()

    def start(self) -> None:
        """Starts the task's function in a new non-blocking thread if not already running."""
        with self._rlock:
            if not self.running and (self.thread_handle is None or not self.thread_handle.is_alive()):
                retained = []
                # Resolve and pin under the registry lock, closing the gap in
                # which a refresh could otherwise replace the selected entries.
                with Connections().instrument_selection() as connections:
                    context = self
                    if self.spec:
                        instruments = self.resolve_instruments()
                        self.instruments = [connections.get_instrument_by_driver(driver_id)
                                            for driver_id in self.spec.instruments.values()]
                        parameters = self.spec.parse_parameters(self.parameters)
                        self.parameters = parameters
                        context = TaskContext(instruments, parameters, self.data, self.exit_flag)
                    else:
                        self.instruments = [connections.get_instrument(alias)
                                            for alias in self.instr_aliases]
                    try:
                        for entry in self.instruments:
                            if entry is not None:
                                entry.io.retain()
                                retained.append(entry.io)
                    except Exception:
                        for io in reversed(retained):
                            io.release()
                        raise
                self.exit_flag.clear()
                self.running = True
                # Task thread
                self.thread_handle = Thread(
                    target=self._execute, args=(context, tuple(retained))
                )
                try:
                    self.thread_handle.start()
                except Exception:
                    for io in reversed(retained):
                        io.release()
                    self.thread_handle = None
                    self.running = False
                    self.exit_flag.set()
                    raise
                # Data processor thread
                from .DataProcessor import DataProcessor
                self.data_processor_obj: Optional[DataProcessor] = DataProcessor(self)
                self.data_processor = self.data_processor_obj.start()

                logger.info(f"Task {self.name} started.")
            else:
                logger.warning(f"Task {self.name} is already running.")

    def check(self) -> None:
        if self.exit_flag.is_set():
            logger.info(f"Task {self.name} has been signaled to stop.")
            self.stop()

    def stop(self) -> None:
        """Signals the task to stop and waits for the thread to finish."""
        with self._rlock:
            self.exit_flag.set()
            if self.thread_handle and self.thread_handle.is_alive():
                self.exit_flag.set()
                self.thread_handle.join()
                logger.info(f"Task {self.name} stopped.")
            processor = getattr(self, "data_processor", None)
            if processor and processor is not current_thread() and processor.is_alive():
                processor.join()
            if self.running:
                self.thread_handle = None
                self._save_chart_data()
                self.data.clear()
                self.running = False
        
    def _save_chart_data(self) -> None:
        """Saves collected chart data to files."""
        if self.custom_alias == "":
            self.custom_alias = "anonymous"
        try:
            os.makedirs(Config().get("data_charts_path"), exist_ok=True)
            if not str_to_bool(str(self.parameters.get("merge_chart_files", "false")).lower()):
                for chart in self.data:
                    file_name = f"{chart.name}_{self.custom_alias}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
                    file_path = os.path.join(Config().get("data_charts_path"), file_name)
                    chart.save_csv_atomic(file_path)
                    logger.info(f"Chart data saved to {file_path}.")
            else:
                metadata = {
                    "task_name": self.name,
                    "custom_alias": self.custom_alias,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                file_name = f"merged_charts_{self.custom_alias}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
                file_path = os.path.join(Config().get("data_charts_path"), file_name)
                save_charts_csv(self.data, file_path, metadata=metadata)
                logger.info(f"Merged chart data saved to {file_path}.")
        except Exception as e:
            logger.error(f"Failed to save merged chart data: {e}")


    def has_instruments(self) -> bool:
        """Checks if all associated instruments are available."""
        if self.spec:
            try:
                self.resolve_instruments()
                return True
            except ValueError:
                return False
        conn_obj = Connections()
        return all(
            conn_obj.get_instrument(alias) is not None for alias in self.instr_aliases
        )


class Tasks:
    """
    Singleton class to manage multiple Task instances.
    """

    _instance = None
    _lock = Lock()  # Add a lock for thread safety
    _atexit_register = None

    def __new__(cls):
        with cls._lock:  # Ensure thread-safe singleton creation
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._tasks_list: List[Task] = []
            self._is_running: Optional[Task] = None
            self._stopping = False
            self._tasks_init_list: List[Callable[[], None]] = []
            logger.info("Tasks manager instance created.")

    def load_specs(self, specs) -> None:
        """Register definitions once, preserving edited parameters on UI reruns."""
        for spec in specs:
            if not any(task.id == spec.id for task in self._tasks_list):
                self.add_task(Task.from_spec(spec))

    def add_init_task(self, task: Callable[[], None]) -> None:
        """Adds and initializes a task."""
        self._tasks_init_list.append(task)
        task()
        logger.info(f"Task initialization function {task.__name__} added and executed.")

    def init_tasks(self) -> None:
        """Initializes all tasks in the initialization list."""
        for init_task in self._tasks_init_list:
            init_task()

    def update_instruments(self, mode: int = 0) -> None:
        """Updates the instruments for all tasks."""
        with self._lock:
            if mode:
                Connections().fetch_all_instruments(Config().get("instr_aliases"))
            for tsk in self._tasks_list:
                tsk.instruments = []
                if tsk.spec:
                    try:
                        tsk.instruments = [Connections().get_instrument_by_driver(driver_id)
                                           for driver_id in tsk.spec.instruments.values()]
                    except ValueError:
                        logger.exception("Cannot resolve instruments for %s", tsk.name)
                    continue
                for instr_alias in tsk.instr_aliases:
                    conn_obj: Connections = Connections()
                    instr = conn_obj.get_instrument(instr_alias)
                    if instr is not None:
                        tsk.instruments.append(instr)

    def run_task(self, name: str) -> None:
        """Runs a task by its name if no other task is currently running."""
        with self._lock:
            if self._is_running is None and not self._stopping:
                for task in self._tasks_list:
                    if task.name == name and task.has_instruments():
                        try:
                            task.start()
                        except (ValueError, TypeError):
                            logger.exception("Cannot start task %s", task.name)
                            return
                        self._is_running = task
                        break
                else:
                    logger.warning(f"Task {name} not found or has no instruments.")
            else:
                logger.warning(
                    f"A task is already running or stopping. "
                    f"Aborting launch of task {name}."
                )

    def stop_task(self, expected: Optional[Task] = None) -> None:
        """Stop outside the manager lock so the watchdog can finish safely."""
        with self._lock:
            task = self._is_running
            if task is None or (expected is not None and task is not expected):
                return
            self._is_running = None
            self._stopping = True
        try:
            task.stop()
            logger.info("Task stopped.")
        finally:
            with self._lock:
                self._stopping = False

    def check(self) -> None:
        task = self._is_running
        if task is not None and task.exit_flag.is_set():
            self.stop_task(expected=task)

    def add_task(self, task: Task) -> None:
        """Adds a new task to the task list."""
        with self._lock:
            if any(t.name == task.name for t in self._tasks_list):
                logger.warning(f"Task {task.name} already exists in the task list.")
                return
            self._tasks_list.append(task)
            logger.info(f"Task {task.name} added to the task list.")

    def get_task(self, name: str) -> Optional[Task]:
        """Retrieves a task by its name."""
        with self._lock:
            return next((task for task in self._tasks_list if task.name == name), None)
