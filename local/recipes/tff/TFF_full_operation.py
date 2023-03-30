import sys
from pathlib import Path

from aqueduct.core.aq import Aqueduct, InitParams

path = Path(__file__).parent.resolve(
).parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.tff.data
import local.lib.tff.classes
import local.lib.tff.helpers

params = InitParams.parse()
aq = Aqueduct(params.user_id, params.ip_address, params.port)
aq.initialize(params.init)

# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = local.lib.tff.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = local.lib.tff.data.Data(devices, aq)

# make the Setpoints object, pass the aqueduct object
setpoints = local.lib.tff.classes.Setpoints(aq)

# make the Watchdog object
watchdog = local.lib.tff.classes.Watchdog(
    data_obj=data,
    devices_obj=devices,
    aqueduct_obj=aq)

# make the Process object
process = local.lib.tff.classes.Process(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
    setpoints=setpoints,
    watchdog=watchdog,
)


process.set_quick_run_params(speed="fast")

# process.two_pump_config = True

process.pump_1_target_flowrate_ml_min = 217.6
process.pump_2_target_flowrate_ml_min = 31.6
process.pump_3_target_flowrate_ml_min = 31.6
process.assign_process_flowrates()

process.pinch_valve_init_pct_open = 0.30
process.do_prompts = False
process.initial_transfer_volume = 10
process.init_conc_target_mass_g = 300
process.diafilt_target_mass_g = 300
process.final_conc_target_mass_g = 100
process.pinch_valve_lock_in_min = 2

process.do_tff_protocol()
