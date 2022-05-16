import aqueduct.core.aq

import sys
from pathlib import Path

path = Path(__file__).parent.resolve().parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.ph_control.classes

aq = aqueduct.core.aq.Aqueduct(1)
aq.initialize()

# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = local.lib.ph_control.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = local.lib.ph_control.classes.Data(devices, aq)

# make the Process object
process = local.lib.ph_control.classes.ProcessHandler(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
)

"""
Continuous PID Control
"""

process.pid_control(
    initial_rate_rpm=1,
    pumps=(devices.PUMP0, devices.PUMP1, devices.PUMP2),
    pH_probe_indices=(0, 1, 2),
)
