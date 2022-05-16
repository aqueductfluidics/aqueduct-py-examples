"""
Usage - Copy this template when creating a new Recipe
protocol.

In DEV MODE, the template creates an
Aqueduct Object (with Prompt, Input, etc.. helpers),
Device Objects.

IN LAB MODE or SIM MODE (run through the Aqueduct Recipe
Runner), the Aqueduct and Device Objects are inherited
from the Python interpreters Globals() dict

The Data, Setpoints, Watchdog, and Process Objects are constructed
using the appropriate Aqueduct and Devices objects.
"""

import config
import local.lib.tff.helpers
import local.lib.tff.methods
import local.lib.tff.classes
from local.lib.tff.definitions import (
    SCALE1_INDEX, SCALE2_INDEX, SCALE3_INDEX, TXDCR1_INDEX, TXDCR2_INDEX, TXDCR3_INDEX, SCIP_INDEX,
    STATUS_OK, STATUS_TIMED_OUT, STATUS_TARGET_MASS_HIT
)

if not config.LAB_MODE_ENABLED:

    from aqueduct.aqueduct import Aqueduct

    aqueduct = Aqueduct('G', None, None, None)

    # make the Devices object
    devices = local.lib.tff.classes.Devices.generate_dev_devices()

else:

    # pass the aqueduct object
    aqueduct = globals().get('aqueduct')

    # pass the globals dictionary, which will have the
    # objects for the Devices already instantiated
    devices = local.lib.tff.classes.Devices(**globals())

# make the Data object, pass the new devices object
# and the aqueduct object
data = local.lib.tff.classes.Data(devices, aqueduct)

# make the Setpoints object, pass the aqueduct object
setpoints = local.lib.tff.classes.Setpoints(aqueduct)

# make the Watchdog object
watchdog = local.lib.tff.classes.Watchdog(
    data_obj=data,
    devices_obj=devices,
    aqueduct_obj=aqueduct)

# make the Process object
process = local.lib.tff.classes.Process(
    devices_obj=devices,
    aqueduct=aqueduct,
    data=data,
    setpoints=setpoints,
    watchdog=watchdog,
)

"""
Add code here
"""
