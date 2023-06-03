import lnp.classes
import lnp.data
import lnp.devices
import lnp.helpers
from aqueduct.core.aq import Aqueduct
from aqueduct.core.aq import InitParams

params = InitParams.parse()
aq = Aqueduct(params.user_id, params.ip_address, params.port)
aq.initialize(params.init)

# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = lnp.devices.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = lnp.data.Data(devices, aq)

# make the Setpoints object, pass the aqueduct object
setpoints = lnp.classes.Setpoints(aq)

# make the Watchdog object
watchdog = lnp.classes.Watchdog(data_obj=data, devices_obj=devices, aqueduct_obj=aq)

# make the Process object
process = lnp.classes.Process(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
    setpoints=setpoints,
    watchdog=watchdog,
)

process.do_lnp_protocol()
