from tasks import Tasks
from .fw_measurement_k2000_RM import init_4w_vdp as init_4w_vdp_0
from .fw_measurement_SM2401_NV import init_4w_vdp as init_4w_vdp_1


# Init code
Tasks.tasks_init_list.append(init_4w_vdp_1)
Tasks.tasks_init_list.append(init_4w_vdp_0)
