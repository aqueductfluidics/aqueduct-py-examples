import argparse
import sys
from pathlib import Path

import aqueduct.core.aq

path = Path(__file__).parent.resolve().parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.ph_control.classes

parser = argparse.ArgumentParser()
parser.add_argument("-u", "--user_id", type=str, help="user_id (either int or 'L')", default="1")
parser.add_argument("-a", "--addr", type=str, help="IP address (no port, like 127.0.0.1)", default="127.0.0.1")
parser.add_argument("-p", "--port", type=int, help="port (like 59000)", default=59000)
parser.add_argument("-i", "--init", type=int, help="initialize (1 for true, 0 for false)", default=1)
args = parser.parse_args()

user_id = args.user_id
ip_address = args.addr
port = args.port
init = bool(args.init)

aq = aqueduct.core.aq.Aqueduct(user_id, ip_address, port)
aq.initialize(init)

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
