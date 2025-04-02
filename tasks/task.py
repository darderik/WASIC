from easy_scpi import Instrument
from config import Config
from typing import List, Callable, Dict, Any, Optional
from threading import Thread, Event, Lock
from instruments import Instrument_Entry
from .structures import ChartData
from connections import Connections
import json
import datetime
import os
import logging

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
        function: Callable[[List[ChartData], Event], None],
        data: Optional[List[ChartData]] = None,
        custom_alias: str = "",
        custom_web_status: Optional[Callable] = None,
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

    def start(self) -> None:
        """Starts the task's function in a new non-blocking thread if not already running."""
        if self.thread_handle is None or not self.thread_handle.is_alive():
            self.exit_flag.clear()
            self.thread_handle = Thread(
                target=self.function, args=(self.data, self.exit_flag), daemon=True
            )
            self.thread_handle.start()
            logger.info(f"Task {self.name} started.")
        else:
            logger.warning(f"Task {self.name} is already running.")

    def stop(self) -> None:
        """Signals the task to stop and waits for the thread to finish."""
        if self.thread_handle and self.thread_handle.is_alive():
            self.exit_flag.set()
            self.thread_handle.join()
            self.thread_handle = None
            logger.info(f"Task {self.name} stopped.")
            self._save_chart_data()
        self.data.clear()

    def _save_chart_data(self) -> None:
        """Saves collected chart data to files."""
        for chart in self.data:
            try:
                file_name = f"{chart.name}_{self.custom_alias}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
                file_path = os.path.join(
                    self._config.get("data_charts_path"), file_name
                )
                with open(file_path, mode="w") as file:
                    json.dump(
                        {
                            "x": chart.x,
                            "y": chart.y,
                            "raw_x": chart.raw_x,
                            "raw_y": chart.raw_y,
                            "x_label": chart.x_label,
                            "y_label": chart.y_label,
                            "info": chart.info,
                            "custom_name": chart.custom_name,
                        },
                        file,
                        skipkeys=True,
                        ensure_ascii=False,
                        indent=4,
                    )
                logger.info(f"Chart data saved to {file_path}.")
            except Exception as e:
                logger.error(f"Failed to save chart data for {chart.name}: {e}")

    def has_instruments(self) -> bool:
        """Checks if all associated instruments are available."""
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

    def __new__(cls):
        with cls._lock:  # Ensure thread-safe singleton creation
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._tasks_list: List[Task] = []
                cls._is_running: Optional[Task] = None
                cls._tasks_init_list: List[Callable[[], None]] = []
                logger.info("Tasks manager instance created.")
        return cls._instance

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
            for tsk in self._tasks_list:
                tsk.instruments = []
                if mode:
                    Connections().fetch_all_instruments(Config().get("instr_aliases"))
                for instr_alias in tsk.instr_aliases:
                    conn_obj: Connections = Connections()
                    instr = conn_obj.get_instrument(instr_alias)
                    if instr is not None:
                        tsk.instruments.append(instr)

    def run_task(self, name: str) -> None:
        """Runs a task by its name if no other task is currently running."""
        with self._lock:
            if self._is_running is None:
                for task in self._tasks_list:
                    if task.name == name and task.has_instruments():
                        task.start()
                        self._is_running = task
                        break
            else:
                logger.warning(
                    f"A task is already running ({self._is_running.name}). "
                    f"Aborting launch of task {name}."
                )

    def stop_task(self) -> None:
        """Stops the currently running task, if any."""
        with self._lock:
            if self._is_running is not None:
                self._is_running.stop()
                self._is_running = None
                logger.info("Task stopped.")

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
