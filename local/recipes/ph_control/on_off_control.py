import config
# local imports
import local.lib.ph_control.classes

if not config.LAB_MODE_ENABLED:

    from aqueduct.aqueduct import Aqueduct

    aqueduct = Aqueduct('G', None, None, None)

    # make the Devices object
    devices = local.lib.ph_control.classes.Devices.generate_dev_devices()

else:

    # pass the aqueduct object
    aqueduct = globals().get('aqueduct')

    # pass the globals dictionary, which will have the
    # objects for the Devices already instantiated
    devices = local.lib.ph_control.classes.Devices(**globals())

# make the Data object, pass the new devices object
# and the aqueduct object
data = local.lib.ph_control.classes.Data(devices, aqueduct)

# make the Process object
process = local.lib.ph_control.classes.ProcessHandler(
    devices_obj=devices,
    aqueduct=aqueduct,
    data=data,
)

"""
Continuous On/Off control
"""

process.on_off_control()