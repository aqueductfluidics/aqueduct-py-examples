import datetime
import time

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
************************
    Initialize      
************************

All Pumps begin at 0% flow
Pinch Valve 30% open
Start reading SCIP and OHSA devices at 1 s interval
"""

print("Initializing Operation...")

print("Stopping all Pumps.")

devices.PUMP1.stop()
devices.PUMP2.stop()
devices.PUMP3.stop()

devices.PV.set_position(pct_open=process.pinch_valve_init_pct_open)

# start reading the outputs of the Parker SciLog
# at an interval of once per second
devices.SCIP.start(interval_s=1.)

# start reading the outputs of the OHSA balance device
# at an interval of once per second
devices.OHSA.start(interval_s=1.)

"""
************************
    User Interaction 
    for Product Pour 
    and Mass Input      
************************

User Input for log file name

Prompt User to place an empty vessel on Scale 1 (feed vessel)
Software tare Scale 1
Prompt User to pour product into feed vessel on Scale 1

Prompt User to place an empty vessel on Scale 2 (buffer vessel)
Software tare Scale 2
Prompt User to pour product into feed buffer on Scale 2

Prompt User to place an empty vessel on Scale 3 (permeate vessel)
Software tare Scale 3

User Input for mass in mg
User input for Concentration target in g/L
User Input for Init Conc Total Volume in mL
Calc permeate mass target in g
"""

if process.do_prompts:
    # Aqueduct input for the log file name
    ipt = aqueduct.input(
        message="Enter the desired log file name. Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=str.__name__,
    )

    process.log_file_name = ipt.get_value()

    # prompt operator to place empty vessel on feed scale
    aqueduct.prompt(
        message="Place empty vessel on Scale 1 (feed scale). Press <b>continue</b> to continue.",
        pause_recipe=True
    )

    # tare scale 1
    print("Taring SCALE1.")
    devices.OHSA.tare(SCALE1_INDEX)

    # prompt operator to pour product into feed vessel, press prompt to continue
    aqueduct.prompt(
        message="Pour product solution into vessel on Scale 1 (feed scale). Press <b>continue</b> to continue.",
        pause_recipe=True
    )

    # prompt operator to place empty vessel on buffer scale
    aqueduct.prompt(
        message="Place empty vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
        pause_recipe=True
    )

    # tare scale 2
    print("Taring SCALE2.")
    devices.OHSA.tare(SCALE2_INDEX)

    # prompt operator to pour product into buffer vessel, press prompt to continue
    aqueduct.prompt(
        message="Pour product solution into vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
        pause_recipe=True
    )

    # prompt operator to place empty vessel on permeate scale
    aqueduct.prompt(
        message="Place empty vessel on Scale 3 (permeate scale). Press <b>continue</b> to continue.",
        pause_recipe=True
    )

    # tare scale 3
    print("Taring SCALE3.")
    devices.OHSA.tare(SCALE3_INDEX)

    # Aqueduct input for the Polysaccharide mass
    ipt = aqueduct.input(
        message="Enter the mass of Polysaccharide in milligrams (mg). Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=float.__name__,
    )

    process.polysaccharide_mass_mg = ipt.get_value()

    # Aqueduct input for concentration target
    ipt = aqueduct.input(
        message="Enter the initial concentration target concentration in grams per liter (g/L). Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=float.__name__,
    )

    process.init_conc_target_g_l = ipt.get_value()

    # catch a zero init_conc_target_g_l
    while not process.init_conc_target_g_l or process.init_conc_target_g_l == 0.:
        # Aqueduct input for concentration target
        ipt = aqueduct.input(
            message="Error! Can't enter '0' for target concentration!"
                    "Re-enter the initial concentration target concentration in grams per liter (g/L). "
                    "Press <b>submit</b> to continue.",
            pause_recipe=True,
            dtype=float.__name__,
        )

        process.init_conc_target_g_l = ipt.get_value()

    # Aqueduct input for the initial product volume
    ipt = aqueduct.input(
        message="Enter the initial product volume in milliliters (mL). Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=float.__name__,
    )

    process.init_conc_volume_ml = ipt.get_value()

    # calculate the target mass (scale 3)
    # Initial product volume [2.a.x] - initial mass of product [2.a.viii] / initial concentration target [2.a.ix]
    process.init_conc_target_mass_g = local.lib.tff.helpers.calc_init_conc_target_mass_g(
        init_conc_volume_ml=process.init_conc_volume_ml,
        polysaccharide_mass_mg=process.polysaccharide_mass_mg,
        init_conc_target_g_l=process.init_conc_target_g_l
    )

    print("Initial Concentration target mass (g) for Scale 3 (permeate scale): {}".format(
        local.lib.tff.helpers.format_float(process.init_conc_target_mass_g, 2)
    ))

"""
************************
    Initial Concentration      
    Step 1: Pump 1 Ramp Up      
************************
Start Pump 1
Monitor P1, P3
If P3 < 2 psi and P1 < 30 psi, increase Pinch Valve pressure
If P1 > 30 psi and P3 > 3, decrease Pinch Valve pressure
If P3 < 0 and  P1 > 30 psi, decrease Pump 1 flowrate 
Note: this condition is not typically met until startup is completed

Increase Pump 1 flowrate once per minute, reaching target flowrate after 5 minutes

"""
# log starting time for init conc
process.init_conc_start_time = datetime.datetime.now().isoformat()

print("Beginning Initial Concentration Step 1: PUMP1 Ramp Up.")
local.lib.tff.methods.pump_ramp(
    interval_s=1, pump=devices.PUMP1,
    pump_name="PUMP1",
    start_flowrate_ml_min=process.init_conc_pump_1_target_flowrate_ml_min / 2,
    end_flowrate_ml_min=process.init_conc_pump_1_target_flowrate_ml_min,
    rate_change_interval_s=process.init_conc_pump1_ramp_interval_s,
    rate_change_ml_min=process.init_conc_pump1_ramp_increment_ml_min,
    timeout_min=process.init_conc_pump1_ramp_timeout_min,
    devices_obj=devices,
    data=data,
    watchdog=watchdog)

"""
************************
    Initial Concentration
    Step 2: Pumps 2 and 3 Ramp Up      
************************
Start Pump 2 and Pump 3 at half of target flowrate 
Increase Pump 2, Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes
Will adjust pinch valve position during ramp to maintain setpoint bounds in `monitor` method
"""
print("Beginning Initial Concentration Step 2: Pump 2 and Pump 3 Ramp Up.")
status = local.lib.tff.methods.pumps_2_and_3_ramp(
    interval_s=1,
    pump2_start_flowrate_ml_min=process.init_conc_pump_2_target_flowrate_ml_min / 2,
    pump2_end_flowrate_ml_min=process.init_conc_pump_2_target_flowrate_ml_min,
    pump3_start_flowrate_ml_min=process.init_conc_pump_3_target_flowrate_ml_min / 2,
    pump3_end_flowrate_ml_min=process.init_conc_pump_3_target_flowrate_ml_min,
    rate_change_interval_s=process.init_conc_pumps_2_3_ramp_interval_s,
    number_rate_changes=process.init_conc_pumps_2_3_ramp_number_rate_changes,
    timeout_min=process.init_conc_pumps_2_3_ramp_timeout_min,
    scale3_target_mass_g=process.init_conc_target_mass_g,
    devices_obj=devices,
    data=data, watchdog=watchdog)

"""
************************
    Initial Concentration
    Step 3: Pinch Valve Lock In      
************************
"""
if status != STATUS_TARGET_MASS_HIT:
    print("Beginning Initial Concentration Step 3: Pinch Valve Lock-In.")
    local.lib.tff.methods.pinch_valve_lock_in(
        interval=1,
        target_p3_psi=process.target_p3_psi,
        timeout_min=process.pinch_valve_lock_in_min,
        devices_obj=devices,
        data=data)

"""
************************
    Initial Concentration
    Step 4: Wait for Target Mass on Scale 3    
************************
"""

print("Waiting for initial concentration SCALE3 target mass {:.2f} g".format(process.init_conc_target_mass_g))

# find the timeout time to break from loop
time_start = datetime.datetime.now()
timeout = time_start + datetime.timedelta(seconds=process.init_conc_timeout_min * 60)

# turn on the overpressure, underpressure, and vacuum condition alarms
watchdog.over_pressure_alarm.on()
watchdog.low_pressure_alarm.on()
watchdog.vacuum_condition_alarm.on()

# infinite loop until we meet a break condition
while True:

    # if the mass on SCALE3 is greater than or equal to the process.init_conc_target_mass_g,
    # break from the loop
    if data.W3 is not None:
        if data.W3 >= process.init_conc_target_mass_g:
            break

    # check to see whether we've timed out
    if datetime.datetime.now() > timeout:
        print("Timed out waiting for initial concentration SCALE3 target mass.")
        break

    local.lib.tff.methods.monitor(
        interval_s=1,
        adjust_pinch_valve=False,
        devices_obj=devices,
        data=data,
        watchdog=watchdog)

"""
************************
    Initial Concentration
    Complete!    
************************
Stop Pumps 2 and 3, Pump 1 continues at same Rate
record scale 3 mass as process.init_conc_actual_mass_g
"""

print("Initial Concentration Step complete.")

# Set PUMP2 and PUMP3 to no flow. Pump 1 will continue to operate at
# target flowrate between Concentration and Diafiltration
print("Stopping PUMP2 and PUMP3.")
devices.PUMP2.stop()
devices.PUMP3.stop()

# time delay to allow for pumps to decelerate to a stop before
# recording init conc mass
print("Waiting for SCALE3 to stabilize...")
time.sleep(process.record_mass_time_delay_s)
data.update_data()
data.log_data_at_interval(5)
process.init_conc_actual_mass_g = data.W3

print("End Initial Concentration SCALE3 mass: {}g".format(process.init_conc_actual_mass_g))

# log log end time for init conc
process.init_conc_end_time = datetime.datetime.now().isoformat()

"""
************************
    Initial Concentration to
    Diafiltration Transition
************************
tare scale 3 in software
prompt to place an empty bottle on buffer scale
tare buffer scale
prompt to confirm liquid added to buffer scale bottle
input to enter number of diafiltrations required for Diafilt 1
"""

# tare scale 3
print("Taring SCALE3.")
devices.OHSA.tare(SCALE3_INDEX)

if process.do_prompts:

    # prompt operator to place an empty bottle on buffer scale
    p = aqueduct.prompt(
        message="Place empty vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
        pause_recipe=False
    )

    # while the prompt hasn't been executed, log data and monitor alarms
    while p:
        local.lib.tff.methods.monitor(interval_s=1, adjust_pinch_valve=False,
                                      devices_obj=devices, data=data, watchdog=watchdog)

    # tare scale 2 after empty vessel is placed on it
    devices.OHSA.tare(SCALE2_INDEX)

    # prompt operator to pour liquid into vessel, press prompt to continue
    p = aqueduct.prompt(
        message="Pour buffer solution into vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
        pause_recipe=False
    )

    # while the prompt hasn't been executed, log data and monitor alarms
    while p:
        local.lib.tff.methods.monitor(interval_s=1, adjust_pinch_valve=False,
                                      devices_obj=devices, data=data, watchdog=watchdog)

    # Aqueduct input for the the number of diafiltrations required for Diafilt 1
    ipt = aqueduct.input(
        message="Enter the number of diavolumes required for Diafiltration 1. Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=int.__name__,
    )

    process.number_diafiltrations = ipt.get_value()

    # calculate diafiltration target mass for scale 3 in grams
    process.diafilt_target_mass_g = local.lib.tff.helpers.calc_diafilt_target_mass_g(
        number_diafiltrations=process.number_diafiltrations,
        polysaccharide_mass_mg=process.polysaccharide_mass_mg,
        init_conc_target_g_l=process.init_conc_target_g_l,
    )

    print("Diafiltration 1 target mass (g) for SCALE3: {}".format(
        local.lib.tff.helpers.format_float(process.diafilt_target_mass_g, 2)
    ))

"""
************************
    Diafiltration
    Step 1: Pump 2 and Pump 3 ramp up      
************************
Start Pump 2 and Pump 3 at half of target flowrate 
Increase Pump 2, Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes
"""
# log start time for diafilt
process.diafilt_start_time = datetime.datetime.now().isoformat()

# turn off the underpressure alarm during ramp and lock in
watchdog.low_pressure_alarm.off()

print("Beginning Diafiltration Step 1: PUMP2 and PUMP3 Ramp Up.")
status = local.lib.tff.methods.pumps_2_and_3_ramp(
    interval_s=1,
    pump2_start_flowrate_ml_min=process.diafilt_pump_2_target_flowrate_ml_min / 2,
    pump2_end_flowrate_ml_min=process.diafilt_pump_2_target_flowrate_ml_min,
    pump3_start_flowrate_ml_min=process.diafilt_pump_3_target_flowrate_ml_min / 2,
    pump3_end_flowrate_ml_min=process.diafilt_pump_3_target_flowrate_ml_min,
    rate_change_interval_s=process.diafilt_pumps_2_3_ramp_interval_s,
    number_rate_changes=process.diafilt_pumps_2_3_ramp_number_rate_changes,
    timeout_min=process.diafilt_pumps_2_3_ramp_timeout_min,
    scale3_target_mass_g=process.diafilt_target_mass_g,
    devices_obj=devices,
    data=data, watchdog=watchdog)

"""
************************
    Diafiltration
    Step 2: Pinch Valve Lock In      
************************
"""
if status != STATUS_TARGET_MASS_HIT:
    print("Beginning Diafiltration Step 2: Pinch Valve Lock-In.")
    local.lib.tff.methods.pinch_valve_lock_in(
        interval=1,
        target_p3_psi=process.target_p3_psi,
        timeout_min=process.pinch_valve_lock_in_min,
        devices_obj=devices,
        data=data)

"""
************************
    Diafiltration
    Step 3: Wait for Target Mass on Scale 3    
************************
"""

print("Waiting for diafiltration SCALE3 target mass {:.2f}g".format(process.diafilt_target_mass_g))

# turn on the overpressure, underpressure alarms
watchdog.over_pressure_alarm.on()
watchdog.low_pressure_alarm.on()

# find the timeout time to break from loop
time_start = datetime.datetime.now()
timeout = time_start + datetime.timedelta(seconds=process.diafilt_timeout_min * 60)

# infinite loop until we meet a break condition
while True:

    # if the mass on SCALE3 is greater than or equal to the process.diafilt_target_mass_g,
    # break from the loop
    if data.W3 is not None:
        if data.W3 >= process.diafilt_target_mass_g:
            break

    # check to see whether we've timed out
    if datetime.datetime.now() > timeout:
        print("Timed out waiting for diafiltration SCALE3 target mass.")
        break

    local.lib.tff.methods.monitor(
        interval_s=1,
        adjust_pinch_valve=False,
        devices_obj=devices,
        data=data,
        watchdog=watchdog)

"""
************************
    Diafiltration 
    Complete!
************************
shut off Pump 2 and Pump 3 (buffer and permeate)
Pump 1 continues at rate from end of Diafilt 
Record Diafilt mass on Scale 3
"""

print("Diafiltration Step complete.")

# Set PUMP2 and PUMP3 to no flow. Pump 1 will continue to operate at
# target flowrate between Diafiltration and Final Conc.
print("Stopping PUMP2 and PUMP3.")
devices.PUMP2.stop()
devices.PUMP3.stop()

# time delay to allow for pumps to decelerate to a stop before
# recording diafiltration mass
print("Waiting for SCALE3 to stabilize...")
time.sleep(process.record_mass_time_delay_s)
data.update_data()
data.log_data_at_interval(5)
process.diafilt_actual_mass_g = data.W3

print("End Diafiltration SCALE3 mass: {}g".format(process.diafilt_actual_mass_g))

# log end time for diafilt
process.diafilt_end_time = datetime.datetime.now().isoformat()

"""
************************
    Diafilt to Final Conc.
    Transition
************************
tare permeate scale in software 
input for final concentration in g/L
calculate final concentration target mass
"""

# tare permeate scale
print("Taring SCALE3 (permeate scale).")
devices.OHSA.tare(SCALE3_INDEX)

if process.do_prompts:
    # Aqueduct input for final concentration target
    ipt = aqueduct.input(
        message="Enter the final concentration target in grams per liter (g/L). Press <b>submit</b> to continue.",
        pause_recipe=True,
        dtype=float.__name__,
    )

    process.final_conc_target_g_l = ipt.get_value()

    # catch a zero final_conc_target_g_l
    while not process.final_conc_target_g_l or process.final_conc_target_g_l == 0.:
        # Aqueduct input for concentration target
        ipt = aqueduct.input(
            message="Error! Can't enter '0' for target concentration!"
                    "Re-enter the final concentration target concentration in grams per liter (g/L). "
                    "Press <b>submit</b> to continue.",
            pause_recipe=True,
            dtype=float.__name__,
        )

        process.final_conc_target_g_l = ipt.get_value()

"""
Target mass (scale 3) = 
initial mass of product [2.a.viii] / initial concentration target [2.a.ix] - 
initial mass of product [2.a.viii] / final concentration target [5.d.i]
"""
process.final_conc_target_mass_g = local.lib.tff.helpers.calc_final_conc_target_mass_g(
    polysaccharide_mass_mg=process.polysaccharide_mass_mg,
    init_conc_target_g_l=process.init_conc_target_g_l,
    final_conc_target_g_l=process.final_conc_target_g_l
)

print("Final Concentration target mass (g) for SCALE3: {}".format(
    local.lib.tff.helpers.format_float(process.final_conc_target_mass_g, 2)
))

"""
************************
    Final Concentration
    Step 1: Pump 3 ramp up      
************************
Start Pump 3 at half of target flowrate 
Increase Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes
"""
# log start time for final conc
process.final_conc_start_time = datetime.datetime.now().isoformat()

# turn off the underpressure alarms
watchdog.low_pressure_alarm.active = False

print("Beginning Final Concentration Step 1: PUMP3 Ramp Up.")
status = local.lib.tff.methods.pump_ramp(
    interval_s=1,
    pump=devices.PUMP3,
    pump_name="PUMP3",
    start_flowrate_ml_min=process.final_conc_pump_3_target_flowrate_ml_min / 2,
    end_flowrate_ml_min=process.final_conc_pump_3_target_flowrate_ml_min,
    rate_change_interval_s=process.final_conc_pump3_ramp_interval_s,
    rate_change_ml_min=process.final_conc_pump3_ramp_increment_ml_min,
    timeout_min=process.final_conc_pump3_ramp_timeout_min,
    scale3_target_mass_g=process.final_conc_target_mass_g,
    devices_obj=devices,
    data=data,
    watchdog=watchdog)

"""
************************
    Final Concentration
    Step 2: Pinch Valve Lock In      
************************
"""
if status != STATUS_TARGET_MASS_HIT:
    print("Beginning Final Concentration Step 2: Pinch Valve Lock-In.")
    local.lib.tff.methods.pinch_valve_lock_in(
        interval=1,
        target_p3_psi=process.target_p3_psi,
        timeout_min=process.pinch_valve_lock_in_min,
        devices_obj=devices,
        data=data)

"""
************************
    Final Concentration
    Step 3: Wait for Target Mass on Scale 3    
************************
"""

# TODO check calculation / input for Diafilt Target Mass

print("Waiting for final concentration SCALE3 target mass {:.2f}g".format(process.final_conc_target_mass_g))

# turn on the overpressure, underpressure alarms
watchdog.over_pressure_alarm.on()
watchdog.low_pressure_alarm.on()

# find the timeout time to break from loop
time_start = datetime.datetime.now()
timeout = time_start + datetime.timedelta(seconds=process.final_conc_timeout_min * 60)

# infinite loop until we meet a break condition
while True:

    # if the mass on SCALE3 is greater than or equal to the process.final_conc_target_mass_g,
    # break from the loop
    if data.W3 is not None:
        if data.W3 >= process.final_conc_target_mass_g:
            break

    # check to see whether we've timed out
    if datetime.datetime.now() > timeout:
        print("Timed out waiting for final concentration SCALE3 target mass.")
        break

    local.lib.tff.methods.monitor(
        interval_s=1,
        adjust_pinch_valve=False,
        devices_obj=devices,
        data=data,
        watchdog=watchdog)

"""
************************
    Final Concentration
    Complete!
************************
Stop Pumps 2 and 3
Record Final Concentration mass
"""

print("Final Concentration Step complete.")

# stop Pumps 2 and 3
print("Stopping PUMP2 and PUMP3.")
devices.PUMP2.stop()
devices.PUMP3.stop()

# time delay to allow for pumps to decelerate to a stop before
# recording final conc mass
print("Waiting for SCALE3 to stabilize...")
time.sleep(process.record_mass_time_delay_s)
data.update_data()
data.log_data_at_interval(5)
process.final_conc_actual_mass_g = data.W3

print("End Final Concentration SCALE3 mass: {}g".format(process.final_conc_actual_mass_g))

# log end time for final conc
process.final_conc_end_time = datetime.datetime.now().isoformat()

"""
************************
    Final Concentration
    Clean Up
************************
slowly open pinch valve to 30%
User Prompt to confirm that the retentate line is blown down (wait here)
Stop Pump 1
"""
# save log file
process.add_process_info_to_log()
aqueduct.save_log_file(process.log_file_name, timestamp=True)

# slowly open pinch valve to the process's init pct open
local.lib.tff.methods.open_pinch_valve(
    target_pct_open=process.pinch_valve_init_pct_open,
    increment_pct_open=0.005,
    interval_s=1,
    devices_obj=devices,
    data=data,
    watchdog=watchdog)

# prompt operator to confirm that the retentate line is blown down (wait here)
p = aqueduct.prompt(
    message="Confirm that the retentate line is blown down. Press <b>continue</b> to continue.",
    pause_recipe=True
)

# stop Pump 1
print("Stopping PUMP1.")
devices.PUMP1.stop()

# stop balance and pressure A/D
devices.OHSA.stop()
devices.SCIP.stop()

print("TFF Full Operation complete!")
