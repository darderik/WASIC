from .task import Task, Tasks
from typing import List, Callable
from threading import Event, Thread
import time
from typing import Optional
import logging
import copy
import datetime
import os
from config import Config
logger = logging.getLogger(__name__)
sleep_time:float = Config().get("processor_sleep", 1.0)

class DataProcessor:
    def __init__(self,cur_task:Task) -> None:
        self.cur_task = cur_task
        self.data = cur_task.data
        self.exit_flag = cur_task.exit_flag
        self.watchdog_thread = Thread(target=self.__watchdog)
        self.last_backup_time = datetime.datetime.now()
        self.datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    def start(self) -> Thread:
        """Starts the data processor thread."""
        if not self.watchdog_thread.is_alive():
            self.watchdog_thread.start()
        return self.watchdog_thread
    
    def __watchdog(self) -> None:
        """Process chart data by applying mathematical formulas."""
        last_iteration: bool = False
        data = self.data
        exit_flag = self.exit_flag
        while True:
            if exit_flag.is_set():
                last_iteration = True
            try:
                for chart_data in data:
                    x = chart_data.x_series.processed
                    x_raw = chart_data.x_series.raw
                    y = chart_data.y_series.processed
                    y_raw = chart_data.y_series.raw
                    x_sample_points = chart_data.config.sample_points_x
                    y_sample_points = chart_data.config.sample_points_y

                    # If either axis exceeds its sample limit (and the limit is non-zero), signal exit
                    x_len = chart_data.get_length(0)
                    y_len = chart_data.get_length(1)

                    if (
                        (x_sample_points != 0 and x_len > x_sample_points)
                        or (y_sample_points != 0 and y_len > y_sample_points) 
                    ):
                        exit_flag.set()

                    # Apply formulas using the already-set local variables
                    if chart_data.math_formula_y is not None:
                        self.apply_formula(y, y_raw, chart_data.math_formula_y, chart_data.config.pop_raw,chart_data.config.refresh_all)

                    if chart_data.math_formula_x is not None:
                        self.apply_formula(x, x_raw, chart_data.math_formula_x, chart_data.config.pop_raw,chart_data.config.refresh_all)
            except Exception as e:
                logger.error(f"Error in data processing: {e}")
                continue
            if last_iteration:
                #self.cur_task.stop()
                Tasks().stop_task()
                break
            # Check if time to backup has elapsed
            backup_schedule = Config().get("backup_schedule", 60.0)
            if (datetime.datetime.now() - self.last_backup_time).total_seconds() >= backup_schedule:
                self.backup_saver()
                self.last_backup_time = datetime.datetime.now()
            time.sleep(sleep_time)




    def apply_formula(self, target: List[float], raw: List[float], formula: Callable[[float], float], pop: bool, refresh_all: bool = False) -> None:
        """Applies a mathematical formula to raw data and updates the target list."""
        
        cur_index = len(target)
        raw_len = len(raw)
        if refresh_all:
            target.clear()
            for value in raw:
                new_value = formula(value)
                target.append(new_value)
        elif cur_index < raw_len and not pop:
            for i in range(cur_index, raw_len):
                value = raw[i]
                new_value: float = formula(value)
                target.append(new_value)
        elif pop:
            for i in range(raw_len):
                value = raw[i]
                new_value = formula(value)
                target.append(new_value)
            for _ in range(raw_len):
                raw.pop(0)
    def backup_saver(self):
        try:
            # Flag check
            if not Config().get("backup_switch", True):
                return
            date: str = self.datetime
            backup_schedule: float = Config().get("backup_schedule", 60.0)
            file_path: str = (
                Config().get("data_charts_path")
                + "\\"
                + Config().get("data_charts_relative_bkps")
            )
            postfix: str = f"{date}.json"
            local_data = copy.copy(self.data)
            for chart in local_data:
                # Set a backup name
                backup_file_name: str = f"BKP_{chart.name}_{postfix}"
                full_path = os.path.join(
                    file_path,
                    backup_file_name,
                )
                chart.save_json_atomic(full_path)
        except Exception as e:
            logger.error(f"Error in backup saver: {e}")
