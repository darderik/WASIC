from tasks import Tasks
from .test_task import init_test_task
from .pid_pai.thermal_meas import init_thermal_tracking_task

# add init code
task_obj = Tasks()

task_obj.add_init_task(init_test_task)
task_obj.add_init_task(init_thermal_tracking_task)
