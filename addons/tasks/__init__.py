from .r_cube.R_CUBE_SRSPA_SM2401 import init_meas_r_cube
from tasks import Tasks
from .test_task import init_test_task
from .rm_transient import init_rm_transient
from .r_cube.R_CUBE_SRSPA_K6221_K2000 import init_meas_r_cube_source_k6221_k2000
from .r_cube.R_CUBE_SRSPA_SM2401_K2000 import init_meas_r_cube_source_k2000_sm2401
# add init code
task_obj = Tasks()

task_obj.add_init_task(init_test_task)
task_obj.add_init_task(init_rm_transient)
task_obj.add_init_task(init_meas_r_cube)
task_obj.add_init_task(init_meas_r_cube_source_k2000_sm2401)
task_obj.add_init_task(init_meas_r_cube_source_k6221_k2000)