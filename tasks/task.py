from easy_scpi import Instrument
from config import Config
from typing import List, Callable, Dict, Any, Optional
from threading import Thread, Event, Lock
from instruments import Instrument_Entry
from .structures import ChartData
from connections import Connections
import json
import datetime


class Task:
    """
    Represents a single task that can be run in a separate thread.

    Attributes:
        name (str): The name of the task.
        description (str): A description of what the task does.
        instruments (List[Optional[Instrument_Entry]]): A list of associated instrument entries.
        function (Callable): The function to execute in the thread.
        data (Dict[str, Any]): Shared data dictionary for the task.
        exit_flag (Event): Event to signal the thread to stop.
        thread_handle (Optional[Thread]): Reference to the running thread.
        lock (Lock): A lock to ensure thread-safe operations on shared data.
    """

    def __init__(
        self,
        name: str,
        description: str,
        instrs_aliases: List[str],
        function: Callable[[List[ChartData], Event], None],
        data: List[ChartData] = [],
        exit_flag: Event = Event(),
        instruments: List[Optional[Instrument_Entry]] = [],
        custom_alias: str = "",
    ):
        """
        Initializes a Task instance.

        Args:
            name (str): The name of the task.
            description (str): A description of the task.
            instrs (List[Optional[Instrument_Entry]]): A list of instrument entries associated with the task.
            function (Callable): The function to execute in the thread. It should accept a data dictionary and an exit event.
        """
        self.name: str = name
        self.description: str = description
        self.instr_aliases: List[str] = instrs_aliases
        self.thread_handle: Optional[Thread] = None
        self.data: List[ChartData] = data
        self.exit_flag: Event = exit_flag
        self.instruments: List[Optional[Instrument_Entry]] = instruments
        self.function: Callable[[List[ChartData], Event], None] = function
        self.custom_alias: str = custom_alias
        self._config: Config = Config()

    def _spawn(self) -> None:
        """
        Starts the task's function in a new non-blocking thread.
        """

        self.exit_flag.clear()
        self.thread_handle = Thread(target=self._run, daemon=True)
        self.thread_handle.start()

    def _run(self) -> None:
        """
        Runs the task's function, passing the shared data and exit flag.
        """
        self.function(self.data, self.exit_flag)

    def _stop(self) -> None:
        """
        Signals the thread to stop and waits for it to finish.
        """
        if self.thread_handle and self.thread_handle.is_alive():
            self.exit_flag.set()
            self.thread_handle.join()
            self.thread_handle = None
        # Save chartdata to file(s)
        for chart in self.data:
            additional_file_name = f"{self.custom_alias}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
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
                open(
                    file=f"{self._config.get("data_charts_path")}\\{chart.name}_{additional_file_name}.json",
                    mode="w",
                ),
                skipkeys=True,
                ensure_ascii=False,
                indent=4,
            )
        self.data.clear()

    def has_instruments(self) -> bool:
        aliases: List[str] = self.instr_aliases
        for alias in aliases:
            conn_obj: Connections = Connections()
            instr = conn_obj.get_instrument(alias)
            if instr is None:
                return False
        return True


class Tasks:
    """
    Manages multiple Task instances.

    Attributes:
        tasks_list (List[Task]): A list of all available tasks.
        _is_running (Optional[Task]): The currently running task, if any.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tasks_list: List[Task] = []
            cls._is_running: Optional[Task] = None
            cls.tasks_init_list: List[Callable[[], None]] = []
        return cls._instance

    def add_init_task(self, task: Callable[[], None]) -> None:
        """
        Adds a task initialization function to the tasks init list.

        Args:
            task (Callable[[], None]): The task initialization function to add.
        """
        self.tasks_init_list.append(task)
        # Execute the task initialization function
        task()

    def init_tasks(self) -> None:
        for init_task in self.tasks_init_list:
            init_task()

    def is_running_get(self) -> Optional[Task]:
        """
        Retrieves the currently running task.

        Returns:
            Optional[Task]: The currently running task, or None if no task is running.
        """
        return self._is_running

    def is_running_set(self, task: Optional[Task]) -> None:
        """
        Sets the currently running task.

        Args:
            task (Optional[Task]): The task to set as running, or None to indicate no task is running.
        """
        self._is_running = task

    def update_instruments(self) -> None:
        for tsk in self._tasks_list:
            tsk.instruments = []
            for instr_alias in tsk.instr_aliases:
                conn_obj: Connections = Connections()
                instr = conn_obj.get_instrument(instr_alias)
                if instr is not None:
                    tsk.instruments.append(instr)

    def run_task(self, name: str) -> None:
        """
        Runs a task by its name if no other task is currently running.

        Args:
            name (str): The name of the task to run.
        """
        if self._is_running is None:
            for task in self._tasks_list:
                if task.name == name:
                    task._spawn()
                    self._is_running = task
                    break

    def kill_task(self) -> None:
        """
        Stops the currently running task, if any.
        """
        if self._is_running is not None:
            self._is_running._stop()
            self._is_running = None

    def add_task(self, task: Task) -> None:
        """
        Adds a new task to the tasks list.

        Args:
            task (Task): The task to add.
        """
        self._tasks_list.append(task)

    def get_task(self, name: str) -> Optional[Task]:
        """
        Retrieves a task by its name.

        Args:
            name (str): The name of the task to retrieve.

        Returns:
            Optional[Task]: The task with the given name, or None if not found.
        """
        for task in self._tasks_list:
            if task.name == name:
                return task
        return None
