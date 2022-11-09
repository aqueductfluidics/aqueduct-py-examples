import argparse
import sys
from pathlib import Path

import aqueduct.core.aq

path = Path(__file__).parent.resolve().parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.dispensing.helpers
import local.lib.dispensing.classes
import local.lib.dispensing.processes.ProcessRunner
import local.lib.dispensing.processes.CoDispense

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
devices = local.lib.dispensing.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = local.lib.dispensing.classes.Data(devices, aq)

# make the Process object
process_runner = local.lib.dispensing.processes.ProcessRunner.ProcessRunner(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
)

# make the upper bound of the range the number of stations (2 pumps per station)
# you want to run
for i in range(0, 6):
    station = local.lib.dispensing.processes.CoDispense.CoDispenseStation()
    station.pump0_input = i * 2
    station.pump1_input = i * 2 + 1
    
    station.pump0_input_port = 1
    station.pump0_output_port = 2
    station.pump0_waste_port = 3
    
    station.pump0_output_tubing_volume_ul = 350.
    station.pump0_priming_volume_ul = 151. + 300. + 200
    
    station.pump1_input_port = 1
    station.pump1_output_port = 2
    station.pump1_waste_port = 3

    station.pump1_output_tubing_volume_ul = 350.
    station.pump1_priming_volume_ul = 151. + 300. + 200
    
    station.pump0_volume_to_dispense_ul = 365000
    station.pump0_dispense_rate_ul_min = 50.
    station.pump0_priming_volume_ul = 151. + 300. + 200.
    station.pump0_output_tubing_prime_volume_ul = 315.
    station.pump0_output_tubing_prime_rate_ul_min = 2000.
    station.pump0_withdraw_rate_ul_min = 25000.

    station.pump1_volume_to_dispense_ul = 116000
    station.pump1_dispense_rate_ul_min = 15.
    station.pump1_output_tubing_prime_volume_ul = 315.
    station.pump1_output_tubing_prime_rate_ul_min = 2000.
    station.pump1_withdraw_rate_ul_min = 25000.

    process_runner.add_station(station)

process_runner.run()
