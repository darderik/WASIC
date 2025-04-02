from tasks import Tasks
from .fw_measurement_k2000_RM import init_4w_vdp as init_4w_vdp_0
from .fw_measurement_SM2401_NV import init_4w_vdp as init_4w_vdp_1
from .examples.template import init_mytask_1

# add init code
task_obj = Tasks()
task_obj.add_init_task(init_4w_vdp_1)
task_obj.add_init_task(init_4w_vdp_0)
task_obj.add_init_task(init_mytask_1)
