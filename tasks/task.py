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
                    file=f"{Config.data_charts_path}\\{chart.name}_{additional_file_name}.json",
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
            instr = Connections.get_instrument(alias)
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

    tasks_list: List[Task] = []
    _is_running: Optional[Task] = None
    tasks_init_list: List[Callable] = []

    @classmethod
    def init_tasks(cls) -> None:
        for init_task in cls.tasks_init_list:
            init_task()

    @classmethod
    def is_running_get(cls) -> Optional[Task]:
        """
        Retrieves the currently running task.

        Returns:
            Optional[Task]: The currently running task, or None if no task is running.
        """
        return cls._is_running

    @classmethod
    def is_running_set(cls, task: Optional[Task]) -> None:
        """
        Sets the currently running task.

        Args:
            task (Optional[Task]): The task to set as running, or None to indicate no task is running.
        """
        cls._is_running = task

    @classmethod
    def update_instruments(cls) -> None:
        for tsk in cls.tasks_list:
            tsk.instruments = []
            for instr_alias in tsk.instr_aliases:
                instr = Connections.get_instrument(instr_alias)
                if instr is not None:
                    tsk.instruments.append(instr)

    @classmethod
    def run_task(cls, name: str) -> None:
        """
        Runs a task by its name if no other task is currently running.

        Args:
            name (str): The name of the task to run.
        """
        if cls._is_running is None:
            for task in cls.tasks_list:
                if task.name == name:
                    task._spawn()
                    cls._is_running = task
                    break

    @classmethod
    def kill_task(cls) -> None:
        """
        Stops the currently running task, if any.
        """
        if cls._is_running is not None:
            cls._is_running._stop()
            cls._is_running = None

    @classmethod
    def add_task(cls, task: Task) -> None:
        """
        Adds a new task to the tasks list.

        Args:
            task (Task): The task to add.
        """
        cls.tasks_list.append(task)

    @classmethod
    def get_task(cls, name: str) -> Optional[Task]:
        """
        Retrieves a task by its name.

        Args:
            name (str): The name of the task to retrieve.

        Returns:
            Optional[Task]: The task with the given name, or None if not found.
        """
        for task in cls.tasks_list:
            if task.name == name:
                return task
        return None
