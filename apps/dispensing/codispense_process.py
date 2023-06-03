import dispensing.classes
import dispensing.helpers
import dispensing.processes.CoDispense
import dispensing.processes.ProcessRunner
from aqueduct.core.aq import Aqueduct
from aqueduct.core.aq import InitParams

params = InitParams.parse()
aq = Aqueduct(params.user_id, params.ip_address, params.port)
aq.initialize(params.init)

# pass the globals dictionary, which will have the
# objects for the Devices already instantiated
devices = dispensing.classes.Devices(aq)

# make the Data object, pass the new devices object
# and the aqueduct object
data = dispensing.classes.Data(devices, aq)

# make the Process object
process_runner = dispensing.processes.ProcessRunner.ProcessRunner(
    devices_obj=devices,
    aqueduct=aq,
    data=data,
)

# make the upper bound of the range the number of stations (2 pumps per station)
# you want to run
for i in range(0, 6):
    station = dispensing.processes.CoDispense.CoDispenseStation()
    station.pump0_input = i * 2
    station.pump1_input = i * 2 + 1

    station.pump0_input_port = 1
    station.pump0_output_port = 2
    station.pump0_waste_port = 3

    station.pump0_output_tubing_volume_ul = 350.0
    station.pump0_priming_volume_ul = 151.0 + 300.0 + 200

    station.pump1_input_port = 1
    station.pump1_output_port = 2
    station.pump1_waste_port = 3

    station.pump1_output_tubing_volume_ul = 350.0
    station.pump1_priming_volume_ul = 151.0 + 300.0 + 200

    station.pump0_volume_to_dispense_ul = 365000
    station.pump0_dispense_rate_ul_min = 50.0
    station.pump0_priming_volume_ul = 151.0 + 300.0 + 200.0
    station.pump0_output_tubing_prime_volume_ul = 315.0
    station.pump0_output_tubing_prime_rate_ul_min = 2000.0
    station.pump0_withdraw_rate_ul_min = 25000.0

    station.pump1_volume_to_dispense_ul = 116000
    station.pump1_dispense_rate_ul_min = 15.0
    station.pump1_output_tubing_prime_volume_ul = 315.0
    station.pump1_output_tubing_prime_rate_ul_min = 2000.0
    station.pump1_withdraw_rate_ul_min = 25000.0

    process_runner.add_station(station)

process_runner.run()
