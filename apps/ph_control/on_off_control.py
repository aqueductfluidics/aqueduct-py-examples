import ph_control.classes
from aqueduct.core.aq import Aqueduct
from aqueduct.core.aq import InitParams

params = InitParams.parse()
aq = Aqueduct(params.user_id, params.ip_address, params.port)
aq.initialize(params.init)

# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = ph_control.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = ph_control.classes.Data(devices, aq)


# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = ph_control.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = ph_control.classes.Data(devices, aq)

# make the Process object
process = ph_control.classes.ProcessHandler(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
)

"""
Continuous On/Off control
"""

process.on_off_control(
    pumps=(devices.PUMP0, devices.PUMP1, devices.PUMP2),
    pH_probe_indices=(0, 1, 2),
)
