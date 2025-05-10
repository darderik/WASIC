from tasks import Tasks
from .fw_measurement_k2000_RM import init_4w_vdp as init_4w_vdp_0
from .examples.template import init_mytask_1
from .fw_measurement_34420A import init_4w_vdp_34420A
from .rm_transient_2012c import init_rm_transient
from .test_task import init_test_task

# add init code
task_obj = Tasks()
task_obj.add_init_task(init_4w_vdp_0)
task_obj.add_init_task(init_mytask_1)
task_obj.add_init_task(init_4w_vdp_34420A)
task_obj.add_init_task(init_rm_transient)
task_obj.add_init_task(init_test_task)
