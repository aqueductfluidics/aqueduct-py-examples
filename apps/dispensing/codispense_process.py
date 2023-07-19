import dispensing.classes
import dispensing.helpers
import dispensing.methods
import dispensing.processes.ProcessRunner
import dispensing.processes.CoDispense
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
    techsol_station = dispensing.processes.CoDispense.CoDispenseStation()
    techsol_station.chem2.input = i
    techsol_station.chem1.input = i + 6

    techsol_station.chem2.input_port = 1
    techsol_station.chem2.output_port = 2
    techsol_station.chem2.waste_port = 3

    techsol_station.chem2.output_tubing_volume_ul = 350.0
    techsol_station.chem2.priming_volume_ul = 151.0 + 300.0 + 200

    techsol_station.chem1.input_port = 1
    techsol_station.chem1.output_port = 2
    techsol_station.chem1.waste_port = 3

    techsol_station.chem1.output_tubing_volume_ul = 350.0
    techsol_station.chem1.priming_volume_ul = 151.0 + 300.0 + 200

    techsol_station.chem2.volume_to_dispense_ul = 36500
    techsol_station.chem2.dispense_rate_ul_min = 50.0
    techsol_station.chem2.priming_volume_ul = 151.0 + 300.0 + 200.0
    techsol_station.chem2.output_tubing_prime_volume_ul = 315.0
    techsol_station.chem2.output_tubing_prime_rate_ul_min = 2000.0
    techsol_station.chem2.withdraw_rate_ul_min = 325000.0

    techsol_station.chem1.volume_to_dispense_ul = 11600
    techsol_station.chem1.dispense_rate_ul_min = 15
    techsol_station.chem1.output_tubing_prime_volume_ul = 315.0
    techsol_station.chem1.output_tubing_prime_rate_ul_min = 2000.0
    techsol_station.chem1.withdraw_rate_ul_min = 325000.0

    process_runner.add_station(techsol_station)

process_runner.stations[0].chem1.dispense_time_min = [1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[0].chem1.dispense_rate_ul_min = [1301.5, 173.5, 43.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[0].chem2.dispense_time_min = [1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[0].chem2.dispense_rate_ul_min = [7601.3, 1013.5, 253.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

process_runner.stations[1].chem1.dispense_time_min = [2.8, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[1].chem1.dispense_rate_ul_min = [0.0, 1275.6, 170.1, 42.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[1].chem2.dispense_time_min = [2.8, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[1].chem2.dispense_rate_ul_min = [0.0, 7601.3, 1013.5, 253.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

process_runner.stations[2].chem1.dispense_time_min = [5.6, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[2].chem1.dispense_rate_ul_min = [0.0, 1301.5, 173.5, 43.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[2].chem2.dispense_time_min = [5.6, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[2].chem2.dispense_rate_ul_min = [0.0, 7601.3, 1013.5, 253.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

process_runner.stations[3].chem1.dispense_time_min = [8.4, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[3].chem1.dispense_rate_ul_min = [0.0, 1301.5, 173.5, 43.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[3].chem2.dispense_time_min = [8.4, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[3].chem2.dispense_rate_ul_min = [0.0, 6986.8, 931.6, 232.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

process_runner.stations[4].chem1.dispense_time_min = [11.2, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[4].chem1.dispense_rate_ul_min = [0.0, 1301.5, 173.5, 43.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[4].chem2.dispense_time_min = [11.2, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[4].chem2.dispense_rate_ul_min = [0.0, 7601.3, 1013.5, 253.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

process_runner.stations[5].chem1.dispense_time_min = [14.0, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[5].chem1.dispense_rate_ul_min = [0.0, 1301.5, 173.5, 43.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[5].chem2.dispense_time_min = [14.0, 1.0, 60.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
process_runner.stations[5].chem2.dispense_rate_ul_min = [0.0, 6986.8, 931.6, 232.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


for station in process_runner.stations:
    station.chem1.calculate_dispense_volumes()
    station.chem2.calculate_dispense_volumes()
    station.log_params()

process_runner.run()
