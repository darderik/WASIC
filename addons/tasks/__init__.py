from tasks import Tasks
from .test_task import init_test_task
from .rm_transient import init_rm_transient

# add init code
task_obj = Tasks()

task_obj.add_init_task(init_test_task)
task_obj.add_init_task(init_rm_transient)
