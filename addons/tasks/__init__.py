from tasks import Tasks
from .four_wire import init_4w_vdp_NV_K2000, init_4w_vdp_k2000, init_4w_vdp_34420A
from .examples.template import init_mytask_1
from .rm_transient import init_rm_transient_2012_C, init_rm_transient_1052
from .test_task import init_test_task

# add init code
task_obj = Tasks()
task_obj.add_init_task(init_mytask_1)
task_obj.add_init_task(init_4w_vdp_34420A)
task_obj.add_init_task(init_rm_transient_2012_C)
task_obj.add_init_task(init_test_task)
task_obj.add_init_task(init_rm_transient_1052)
