import aqueduct.core.aq

import sys
from pathlib import Path

path = Path(__file__).parent.resolve().parent.resolve().parent.resolve().parent.resolve()
sys.path.extend([str(path)])

import local.lib.dispensing.helpers
import local.lib.dispensing.methods
import local.lib.dispensing.classes
import local.lib.dispensing.processes.ProcessRunner
import local.lib.dispensing.processes.CoDispense

# aq = aqueduct.core.aq.Aqueduct(1, "169.254.211.104", 59001)
# aq.initialize(False)
aq = aqueduct.core.aq.Aqueduct(1)
aq.initialize(True)

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
    
    station.pump0_volume_to_dispense_ul = 36500
    station.pump0_dispense_rate_ul_min = 5000.
    station.pump0_priming_volume_ul = 151. + 300. + 200.
    station.pump0_output_tubing_prime_volume_ul = 315.
    station.pump0_output_tubing_prime_rate_ul_min = 2000.
    station.pump0_withdraw_rate_ul_min = 25000.

    station.pump1_volume_to_dispense_ul = 11600
    station.pump1_dispense_rate_ul_min = 1500
    station.pump1_output_tubing_prime_volume_ul = 315.
    station.pump1_output_tubing_prime_rate_ul_min = 2000.
    station.pump1_withdraw_rate_ul_min = 25000.

    process_runner.add_station(station)

process_runner.run()