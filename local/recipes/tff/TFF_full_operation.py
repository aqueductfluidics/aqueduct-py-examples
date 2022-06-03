import aqueduct.core.aq

import sys
from pathlib import Path

path = Path(__file__).parent.resolve().parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.tff.helpers
import local.lib.tff.methods
import local.lib.tff.classes
import local.lib.tff.data
from local.lib.tff.definitions import (
    SCALE1_INDEX, SCALE2_INDEX, SCALE3_INDEX, TXDCR1_INDEX, TXDCR2_INDEX, TXDCR3_INDEX, SCIP_INDEX,
    STATUS_OK, STATUS_TIMED_OUT, STATUS_TARGET_MASS_HIT
)

aq = aqueduct.core.aq.Aqueduct(1)
aq.initialize()

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

# NOTE: Watch out for spaces as you're uncommenting

"""
Uncomment the following line to enable 
accelerated params useful for simulating. 

Set speed="medium" or speed="fast" to control
rate of accel.
"""
# process.set_quick_run_params(speed="medium")



"""
Uncomment the following line to define which setup is
being used: 2pump or 3pump, default = 3pump
"""
# process.two_pump_config = True

"""
Uncomment the following lines to adjust the target 
flowrates for each phase of the TFF protocol.
"""
# process.pump_1_target_flowrate_ml_min = 17.6
# process.pump_2_target_flowrate_ml_min = 1.6
# process.pump_3_target_flowrate_ml_min = 1.6
# process.assign_process_flowrates()


"""
Uncomment the following line to set the pinch valve to 
start at 40% open, which works well with the mini cartridge.

30% is the default opening percentage
"""
# process.pinch_valve_init_pct_open = 0.4


"""
Uncomment the following line to disable
user prompts. 

You should set target masses 
directly when user prompts are disabled.
"""
# process.do_prompts = False
# process.init_conc_target_mass_g = 10
# process.diafilt_target_mass_g = 10
# process.final_conc_target_mass_g = 10

process.do_tff_protocol()
