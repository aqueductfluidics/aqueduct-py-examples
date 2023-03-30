import time
from typing import List, Union

from aqueduct.devices.pump import PeristalticPump

import local.lib.tff.helpers
import local.lib.tff.definitions


def pump_ramp(
        interval_s: int = 1,
        pump: "PeristalticPump" = None,
        pump_name: str = "PUMP",
        start_flowrate_ml_min: Union[float, int] = 10,
        end_flowrate_ml_min: Union[float, int] = 20,
        rate_change_interval_s: Union[float, int] = 10,
        rate_change_ml_min: Union[float, int] = 2,
        rate_change_pct: Union[float, None] = None,
        timeout_min: Union[float, int] = 10,
        adjust_pinch_valve: bool = True,
        scale3_target_mass_g: Union[float, int, None] = None,
        devices_obj: "local.lib.tff.classes.Devices" = None,
        data: "local.lib.tff.classes.Data" = None,
        watchdog: "local.lib.tff.classes.Watchdog" = None
) -> int:
    """
    Start and then ramp a pump's flowrate in incremented steps.

    :param interval_s: time, in seconds, of outer loop heartbeat
    :param pump_name: name of Pump to display
    :param pump: MFPP object
    :rtype pump: local.lib.tff.classes.PeristalticPump
    :param start_flowrate_ml_min: starting flowrate in mL/min
    :param end_flowrate_ml_min: ending flowrate in mL/min
    :param rate_change_interval_s: time, in seconds, between changing the flowrate
        of pump
    :param rate_change_ml_min: value, in mL/min, of each step increase in flowrate
    :param rate_change_pct: value, between 0 and 1, sets the pct increase of each step between
        the start and end flowrates
    :param timeout_min: time, in minutes, before returning early from method
        if `pump1_end_flowrate_ml_min` is not achieved
    :param adjust_pinch_valve: if True, will enable control of
        pinch valve during monitor method
    :param scale3_target_mass_g: target mass for SCALE3 in grams, if reading exceeds this value will break from the
        the loop early
    :param devices_obj:
    :rtype devices_obj: local.lib.tff.classes:Devices
    :param data:
    :rtype data: local.lib.tff.classes:Data
    :param watchdog:
    :rtype watchdog: local.lib.tff.classes.Watchdog
    :return: integer for a status code
        0, None = ramps completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    # start PUMP at start_flowrate_ml_min
    print("[RAMP] Starting {} at {:.2f} mL/min".format(pump_name, start_flowrate_ml_min))

    commands = pump.make_commands()
    command = PeristalticPump.make_start_command(
        mode=pump.MODE.Continuous,
        direction=pump.STATUS.Clockwise,
        rate_value=start_flowrate_ml_min,
        rate_units=pump.RATE_UNITS.MlMin,
    )
    pump.set_command(commands, 0, command)
    pump.start(commands)

    # save the starting time
    time_start: float = time.time()

    # find the timeout time to break from loop
    timeout: float = time_start + timeout_min * 60

    target_pump1_ml_min = pump.get_ml_min()[0]

    # if the rate_change_pct is set, calculate a new rate_change_ml_min
    if rate_change_pct is not None:
        rate_change_ml_min = round(
            (end_flowrate_ml_min - start_flowrate_ml_min) * rate_change_pct, 2)

    # while the flow rate of PUMP1 is less than the target, gradually increase the
    # rate in increments of 2 mL/min
    while target_pump1_ml_min < end_flowrate_ml_min:

        # check to see whether we've timed out
        if time.time() > timeout:
            print(f"[RAMP] Timed out during {pump_name} ramp up.")
            return local.lib.tff.definitions.STATUS_TIMED_OUT

        time_loop_start: float = time.time()

        # wait for rate_change_interval_s seconds before increasing pump1 rate
        # while waiting, call the monitor method to check pressures
        # there is an interval second heartbeat in the monitor method between data updates
        while time.time() < time_loop_start + rate_change_interval_s:
            # perform the monitoring method until it's time to increase the Pump's rate
            local.lib.tff.methods.monitor(
                interval_s=interval_s,
                adjust_pinch_valve=adjust_pinch_valve,
                devices_obj=devices_obj,
                data=data,
                watchdog=watchdog
            )

            if scale3_target_mass_g is not None:
                if data.W3 is not None and data.W3 >= scale3_target_mass_g:
                    print(
                        f"[RAMP] Scale 3 target mass of {scale3_target_mass_g} g hit during pump {pump_name} ramp.")
                    return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

        # increase the rate of PUMP by rate_change_ml_min mL/min, don't exceed the target flowrate
        target_pump1_ml_min = min(
            pump.get_ml_min()[0] + rate_change_ml_min, end_flowrate_ml_min)
        print(
            f"[RAMP] Adjusting {pump_name} rate to {target_pump1_ml_min:.2f} mL/min")

        commands = pump.make_commands()
        command = PeristalticPump.make_change_speed_command(
            rate_value=target_pump1_ml_min,
            rate_units=pump.RATE_UNITS.MlMin,
        )
        pump.set_command(commands, 0, command)
        pump.change_speed(commands)

    print(f"[RAMP] Completed {pump_name} ramp up.")

    return local.lib.tff.definitions.STATUS_OK


def pumps_2_and_3_ramp(
        interval_s: int = 1,
        pump2_start_flowrate_ml_min: Union[float, int] = 10,
        pump2_end_flowrate_ml_min: Union[float, int] = 20,
        pump3_start_flowrate_ml_min: Union[float, int] = 10,
        pump3_end_flowrate_ml_min: Union[float, int] = 20,
        rate_change_interval_s: Union[float, int] = 10,
        number_rate_changes: int = 6,
        timeout_min: Union[float, int] = 30,
        adjust_pinch_valve: bool = True,
        scale3_target_mass_g: Union[float, int, None] = None,
        devices_obj: "local.lib.tff.classes.Devices" = None,
        data: "local.lib.tff.classes.Data" = None,
        watchdog: "local.lib.tff.classes.Watchdog" = None
) -> int:
    """
    Start Pump 2 and Pump 3 at half of target flowrate
    Increase Pump 2, Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes

    :param interval_s: time, in seconds, or outer loop heartbeat
    :param pump2_start_flowrate_ml_min: starting flowrate for PUMP2, in mL/min
    :param pump2_end_flowrate_ml_min: ending flowrate for PUMP2, in mL/min
    :param pump3_start_flowrate_ml_min: starting flowrate for PUMP3, in mL/min
    :param pump3_end_flowrate_ml_min: ending flowrate for PUMP3, in mL/min
    :param rate_change_interval_s: time, in seconds, between changing the flowrate
        of Pump 1
    :param number_rate_changes: number of flowrate increases between start and finish rates
    :param timeout_min: time, in minutes, before returning early from method
        if `pump2_end_flowrate_ml_min` or `pump3_end_flowrate_ml_min` is not achieved
    :param adjust_pinch_valve: if True, will enable control of
        pinch valve during monitor method
    :param scale3_target_mass_g: target mass for SCALE3 in grams, if reading exceeds this value will break from the
        the loop early
    :param devices_obj:
    :rtype devices_obj: local.lib.tff.classes:Devices
    :param data:
    :rtype data: local.lib.tff.classes:Data
    :param watchdog:
    :rtype watchdog: local.lib.tff.classes.Watchdog
    :return: integer for a status code
        0, None = ramps completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    time_start: float = time.time()

    # find the timeout time to break from loop
    timeout: float = time_start + timeout_min * 60

    if isinstance(devices_obj.PUMP2, PeristalticPump):
        print(
            f"[DUAL RAMP] Starting PUMP2 at {pump2_start_flowrate_ml_min:.2f} mL/min")

        commands = devices_obj.PUMP2.make_commands()
        command = PeristalticPump.make_start_command(
            mode=devices_obj.PUMP2.MODE.Continuous,
            direction=devices_obj.PUMP2.STATUS.Clockwise,
            rate_value=pump2_start_flowrate_ml_min,
            rate_units=devices_obj.PUMP2.RATE_UNITS.MlMin,
        )
        devices_obj.PUMP2.set_command(commands, 0, command)
        devices_obj.PUMP2.start(commands, record=True)

    print(
        "[DUAL RAMP] Starting PUMP3 at {pump3_start_flowrate_ml_min:.2f} mL/min")

    commands = devices_obj.PUMP3.make_commands()
    command = PeristalticPump.make_start_command(
        mode=devices_obj.PUMP3.MODE.Continuous,
        direction=devices_obj.PUMP3.STATUS.Clockwise,
        rate_value=pump3_start_flowrate_ml_min,
        rate_units=devices_obj.PUMP3.RATE_UNITS.MlMin,
    )
    devices_obj.PUMP3.set_command(commands, 0, command)
    devices_obj.PUMP3.start(commands, record=True)

    pump2_rate_ml_min_range: List[float] = local.lib.tff.helpers.get_flowrate_range(
        start_flow_rate=pump2_start_flowrate_ml_min,
        end_flow_rate=pump2_end_flowrate_ml_min,
        steps=number_rate_changes)

    pump3_rate_ml_min_range: List[float] = local.lib.tff.helpers.get_flowrate_range(
        start_flow_rate=pump3_start_flowrate_ml_min,
        end_flow_rate=pump3_end_flowrate_ml_min,
        steps=number_rate_changes)

    for pump2_rate_ml_min, pump3_rate_ml_min in zip(pump2_rate_ml_min_range[1::], pump3_rate_ml_min_range[1::]):

        # check to see whether we've timed out
        if time.time() > timeout:
            print("[DUAL RAMP] Timed out stabilizing during pumps 2 and 3 ramp up.")
            return local.lib.tff.definitions.STATUS_TIMED_OUT

        time_loop_start: float = time.time()

        # wait for rate_change_interval_s seconds before increasing pumps 2 and 3 rates
        while time.time() < time_loop_start + rate_change_interval_s:
            # monitor P1, P3 and feedback on PV and PUMP1 if needed
            local.lib.tff.methods.monitor(
                interval_s=interval_s,
                adjust_pinch_valve=adjust_pinch_valve,
                pump_2_3_watch=True,
                devices_obj=devices_obj,
                data=data,
                watchdog=watchdog
            )
            if scale3_target_mass_g is not None:
                if data.W3 is not None and data.W3 >= scale3_target_mass_g:
                    print("[DUAL RAMP] Scale 3 target mass of {} g hit during pumps 2 and 3 ramp.".format(
                        scale3_target_mass_g)
                    )
                    return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

        if isinstance(devices_obj.PUMP2, PeristalticPump):
            # change the rate of PUMP2
            print(
                "[DUAL RAMP] Adjusting PUMP2 rate to {:.2f} mL/min".format(pump2_rate_ml_min))

            commands = devices_obj.PUMP2.make_commands()
            command = PeristalticPump.make_change_speed_command(
                rate_value=pump2_rate_ml_min,
                rate_units=devices_obj.PUMP2.RATE_UNITS.MlMin,
            )
            devices_obj.PUMP2.set_command(commands, 0, command)
            devices_obj.PUMP2.change_speed(commands)

        # change the rate of PUMP3
        print(
            f"[DUAL RAMP] Adjusting PUMP3 rate to {pump3_rate_ml_min:.2f} mL/min")

        commands = devices_obj.PUMP3.make_commands()
        command = PeristalticPump.make_change_speed_command(
            rate_value=pump3_rate_ml_min,
            rate_units=devices_obj.PUMP3.RATE_UNITS.MlMin,
        )
        devices_obj.PUMP3.set_command(commands, 0, command)
        devices_obj.PUMP3.change_speed(commands)

    # check all alarms
    if isinstance(watchdog, local.lib.tff.classes.Watchdog):
        watchdog.check_alarms()

    # heartbeat delay
    if isinstance(devices_obj.PUMP2, PeristalticPump):
        print("[DUAL RAMP] Completed Pumps 2 and 3 ramp up.")
    else:
        print("[DUAL RAMP] Completed Pump 3 ramp up.")

    return local.lib.tff.definitions.STATUS_OK


def open_pinch_valve(
        target_pct_open: float = 0.3,
        increment_pct_open: float = 0.005,
        interval_s: int = 1,
        devices_obj: "local.lib.tff.classes.Devices" = None,
        data: "local.lib.tff.classes.Data" = None,
        watchdog: "local.lib.tff.classes.Watchdog" = None
) -> None:
    """
    Slowly open the pinch valve in increments of increment_pct_open
    and intervals of interval until the target_pct_open set point is hit.

    :param target_pct_open:
    :param increment_pct_open:
    :param interval_s:
    :param devices_obj:
    :param data:
    :param watchdog:
    :return:
    """
    target_pct_open = min(max(0., target_pct_open), 1.)
    while data.PV < target_pct_open:
        increment_target_pct_open = min(
            data.PV + increment_pct_open, target_pct_open)

        commands = devices_obj.PV.make_commands()
        command = devices_obj.PV.make_set_poisition_command(
            pct_open=increment_target_pct_open)
        devices_obj.PV.set_command(commands, 0, command)
        devices_obj.PV.set_position(commands, record=True)

        print("[OPEN] Adjusting pinch valve to {} open, final target {}".format(
            local.lib.tff.helpers.format_float(increment_target_pct_open, 4),
            local.lib.tff.helpers.format_float(target_pct_open, 4)
        ))
        time.sleep(interval_s)
        data.update_data()
        data.log_data_at_interval()
        if isinstance(watchdog, local.lib.tff.classes.Watchdog):
            watchdog.check_alarms()


def monitor(
        interval_s: float = 1,
        adjust_pinch_valve: bool = True,
        pressure_bounds_1_psi: tuple = (1, 30),
        pressure_bounds_2_psi: tuple = (0, 30),
        pressure_bounds_3_psi: tuple = (0, 30),
        pressure_bounds_4_psi: tuple = (0, 15),
        loop_timeout_min: float = 10,
        pump_2_3_watch: bool = False,
        devices_obj: "local.lib.tff.classes.Devices" = None,
        data: "local.lib.tff.classes.Data" = None,
        watchdog: "local.lib.tff.classes.Watchdog" = None,
        process: "local.lib.tff.classes.Process" = None,
) -> None:
    """
    Logging and Monitoring logic to:

        1) Update Data
        2) Log Data to File
        3) Adjust Pinch Valve per logic below if adjust_pinch_valve is True
        4) Check Watchdog Alarms

    CONDITION 1: P3 < 1 psi and P1 < 30 psi
    CONDITION 2: P3 > 0 psi and P1 > 30 psi
    CONDITION 3: P3 < 0 psi and P1 > 30 psi

    pressure_bounds_1_psi:
        P3 upper bound and P1 lower bound for CONDITION 1, (P3_upper_bound, P1_lower_bound), (2, 30)

    pressure_bounds_2_psi:
        P3 lower bound and P1 upper bound for CONDITION 2, (P3_lower_bound, P1_upper_bound), (0, 30)

    pressure_bounds_3_psi:
        P3 upper bound and P1 upper bound for CONDITION 3, (P3_upper_bound, P1_upper_bound), (0, 30)

    pressure_bounds_4_psi:
        P3 lower bound and P1 lower bound for CONDITION 3, (P3_lower_bound, P1_lower_bound), (0, 15)

    Logic:
        If adjust_pinch_valve
            if CONDITION 1, close pinch valve by 0.25%
            if CONDITION 2, open pinch valve by 0.25%
            if CONDITION 3, decrease Pump 1 flowrate by 0.1 mL/min

    :param int interval_s: heartbeat delay in between updating data and
        checking logic
    :param adjust_pinch_valve: turns on control of pinch valve based
        on logic above
    :param tuple pressure_bounds_1_psi:
    :param tuple pressure_bounds_2_psi:
    :param tuple pressure_bounds_3_psi:
    :param tuple pressure_bounds_4_psi:
    :param loop_timeout_min:
    :param pump_2_3_watch:
    :param local.lib.tff.classes.Devices devices_obj:
    :param local.lib.tff.classes.Data data:
    :param local.lib.tff.classes.Watchdog watchdog:
    :param local.lib.tff.classes.Process process:
    :return: None
    """
    # update the data dictionary and
    # log the data
    data.update_data()
    data.log_data_at_interval(5)

    def set_position(pct_open):
        commands = devices_obj.PV.make_commands()
        command = devices_obj.PV.make_set_poisition_command(
            pct_open=pct_open)
        devices_obj.PV.set_command(commands, 0, command)
        devices_obj.PV.set_position(commands, record=True)

    # if the pinch valve control is turned on
    if adjust_pinch_valve:

        # check to see if the pressures are within the desired bounds
        # adjust the Pinch Valve or PUMP1 flowrate if not

        # try/catch for invalid pressure readings
        try:

            # If we're ramping pumps 2 and 3, initiate the following response: If P3 < 0psi and P1 < 15psi,
            # pinch more to avoid under-pressure condition during pump 2,3 ramp-up
            if pump_2_3_watch and data.P3 < pressure_bounds_4_psi[0] and data.P1 < pressure_bounds_4_psi[1]:
                print(
                    "[MONITOR] watching pressures to avoid underpressure alarm during ramp-up.")
                print("[MONITOR] decreasing pinch valve setting by 0.01 until P3 > 0, down to a minimum PV setting of "
                      "0.3")
                while data.P3 < pressure_bounds_4_psi[0] and data.P1 < pressure_bounds_4_psi[1]:
                    # if process._aqueduct.__user_id__ == "L":
                    #     # don't pinch below 30%
                    #     target_pct_open: float = max(data.PV - 0.01, 0.3)
                    # else:
                    # don't pinch below 10%
                    target_pct_open: float = max(data.PV - 0.005, 0.0)
                    set_position(target_pct_open)
                    print("[MONITOR (PUMP 2&3 WATCH)] adjusting pinch valve to {} open".format(
                        local.lib.tff.helpers.format_float(
                            target_pct_open, 4)))
                    # wait for 2 seconds to allow time for measurable response
                    time.sleep(.2)
                    data.update_data()
                    data.log_data_at_interval(1)

            # If P3 < pressure_bounds_1_psi[0] (2 psi default) and P1 < pressure_bounds_1_psi[1] (30 psi default),
            # close the Pinch Valve by 0.025%
            elif data.P3 < pressure_bounds_1_psi[0] and data.P1 < pressure_bounds_1_psi[1]:
                time_start: float = time.monotonic()
                timeout: float = time_start + loop_timeout_min * 60.
                while data.P3 < pressure_bounds_1_psi[0] and data.P1 < pressure_bounds_1_psi[1]:
                    if time.monotonic() > timeout:
                        print("[MONITOR] Timed out during CONDITION 1 control.")
                        break

                    error: float = abs(data.P3 - pressure_bounds_1_psi[0])
                    if error > 5:
                        adj = 0.02
                    elif error > 2:
                        adj = 0.001
                    elif error > 1:
                        adj = 0.0005
                    else:
                        adj = 0.0002

                    target_pct_open: float = max(data.PV - adj, 0.)
                    devices_obj.PV.set_position(target_pct_open, record=True)
                    print("[MONITOR (CONDITION 1)] Adjusting pinch valve to {} open".format(
                        local.lib.tff.helpers.format_float(
                            target_pct_open, 4)))
                    # wait for 2 seconds to allow time for measurable response
                    time.sleep(.2)
                    data.update_data()
                    data.log_data_at_interval(5)
                    if isinstance(watchdog, local.lib.tff.classes.Watchdog):
                        watchdog.check_alarms()

            # If P3 > pressure_bounds_2_psi[0] (0 psi default) and P1 > pressure_bounds_2_psi[1] (30 psi default),
            # open the Pinch Valve by 0.025%
            elif data.P3 > pressure_bounds_2_psi[1] and data.P1 > pressure_bounds_2_psi[1]:
                time_start: float = time.monotonic()
                timeout: float = time_start + loop_timeout_min * 60.
                while data.P3 > pressure_bounds_2_psi[0] and data.P1 > pressure_bounds_2_psi[1]:
                    if time.monotonic() > timeout:
                        print("[MONITOR] Timed out during CONDITION 2 control.")
                        break
                    target_pct_open: float = min(data.PV + 0.0005, 1.)
                    print("[MONITOR (CONDITION 2)] Adjusting pinch valve to {} open".format(
                        local.lib.tff.helpers.format_float(
                            target_pct_open, 4)))
                    set_position(target_pct_open)
                    # wait for 2 seconds to allow time for measurable response
                    time.sleep(.2)
                    data.update_data()
                    data.log_data_at_interval(5)
                    if isinstance(watchdog, local.lib.tff.classes.Watchdog):
                        watchdog.check_alarms()

            # If P3 < pressure_bounds_3_psi[0] (0 psi default) and P1 > pressure_bounds_3_psi[1] (30 psi default),
            # decrease PUMP1 flowrate by 0.1 mL/min
            elif data.P3 < pressure_bounds_3_psi[0] and data.P1 > pressure_bounds_3_psi[1]:
                time_start: float = time.monotonic()
                timeout: float = time_start + loop_timeout_min * 60.
                while data.P3 < pressure_bounds_3_psi[0] and data.P1 > pressure_bounds_3_psi[1]:
                    if time.monotonic() > timeout:
                        print("[MONITOR] Timed out during CONDITION 3 control.")
                        break
                    target_pump1_ml_min: float = max(data.R1 - 0.1, 0.1)

                    commands = devices_obj.PUMP1.make_commands()
                    command = PeristalticPump.make_change_speed_command(
                        rate_value=target_pump1_ml_min,
                        rate_units=devices_obj.PUMP1.RATE_UNITS.MlMin,
                    )
                    devices_obj.PUMP1.set_command(commands, 0, command)
                    devices_obj.PUMP1.change_speed(commands)

                    print("[MONITOR (CONDITION 3)] Adjusting PUMP1 rate to {} mL/min".format(
                        local.lib.tff.helpers.format_float(
                            target_pump1_ml_min, 2)))
                    # wait for 2 seconds to allow time for measurable response
                    time.sleep(.2)
                    data.update_data()
                    data.log_data_at_interval(5)
                    if isinstance(watchdog, local.lib.tff.classes.Watchdog):
                        watchdog.check_alarms()

        except TypeError:
            pass

    # check alarms if watchdog is not None
    if isinstance(watchdog, local.lib.tff.classes.Watchdog):
        watchdog.check_alarms()

    # heartbeat delay
    time.sleep(interval_s)


def pinch_valve_lock_in(
        interval: int = 1,
        target_p3_psi: float = 5.,
        timeout_min: float = 2.,
        scale3_target_mass_g: Union[float, None] = None,
        devices_obj: "local.lib.tff.classes.Devices" = None,
        data: "local.lib.tff.classes.Data" = None
) -> int:
    """
    Once all pumps for a given module are up to full speed, start a timer (use 2min until you hear otherwise from us)
    over which the pinch valve can reposition to target P3 of 5 psig (let us know if this is a difficult target).

    :param [int, float] timeout_min:
    :param [int, float] target_p3_psi:
    :param [int, float] interval:
    :param [int, float, None] = scale3_target_mass_g:
    :param local.lib.tff.classes.Devices devices_obj:
    :param local.lib.tff.classes.Data data:
    :return: integer for a status code
        0, None = lock in completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    # set a window around the target_p3_psi in which the valve will not adjust, the
    WINDOW_PSI: float = .5

    # time to sleep after valve adjustment
    VALVE_DELAY_S = .2

    # define a timer that counts time spent in loop
    time_tried_s: int = 0

    print("[LOCK IN] beginning pinch valve lock-in to target P3 {} psi.".format(target_p3_psi))

    in_window_counter = 0

    while time_tried_s < timeout_min * 60:

        # update the data dictionary and
        # log the data
        data.update_data()
        data.log_data_at_interval(5)

        in_window_counter += 1

        if scale3_target_mass_g is not None:
            if data.W3 is not None and data.W3 >= scale3_target_mass_g:
                print("[LOCK IN] scale 3 target mass of {} g hit during pinch valve lock-in.".format(
                    scale3_target_mass_g))
                return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

        # try/catch for invalid pressure readings
        try:

            # If P3 < target_p3_psi - WINDOW_PSI and error > 1, close the Pinch Valve by 0.002
            # If P3 < target_p3_psi - WINDOW_PSI and error <= 1, close the Pinch Valve by 0.001
            while data.P3 < target_p3_psi - WINDOW_PSI and time_tried_s < timeout_min * 60:

                if scale3_target_mass_g is not None:
                    if data.W3 is not None and data.W3 >= scale3_target_mass_g:
                        print("[LOCK IN] scale 3 target mass of {} g hit during pinch valve lock-in.".format(
                            scale3_target_mass_g))
                        return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

                error: float = abs(data.P3 - target_p3_psi)
                if error > 5:
                    adj = 0.0005
                elif error > 1:
                    adj = 0.00025
                else:
                    adj = 0.0001

                target_pct_open: float = data.PV - adj
                devices_obj.PV.set_position(target_pct_open, record=True)
                print("[LOCK IN] adjusting pinch valve to {} open".format(
                    local.lib.tff.helpers.format_float(target_pct_open, 4))
                )
                # delay to allow response in pressure
                time.sleep(VALVE_DELAY_S)
                time_tried_s += VALVE_DELAY_S
                data.update_data()
                data.log_data_at_interval(5)

                in_window_counter = 0

            # If P3 > target_p3_psi + WINDOW_PSI and error > 1, open the Pinch Valve by 0.002
            # If P3 > target_p3_psi + WINDOW_PSI and error <= 1, open the Pinch Valve by 0.001
            while data.P3 > target_p3_psi + WINDOW_PSI and time_tried_s < timeout_min * 60:

                if scale3_target_mass_g is not None:
                    if data.W3 is not None and data.W3 >= scale3_target_mass_g:
                        print(
                            f"[LOCK IN] scale 3 target mass of {scale3_target_mass_g} g hit during pinch valve lock-in.")
                        return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

                error: float = abs(data.P3 - target_p3_psi)
                if error > 5:
                    adj = 0.0005
                elif error > 1:
                    adj = 0.00025
                else:
                    adj = 0.0001

                target_pct_open: float = data.PV + adj
                devices_obj.PV.set_position(target_pct_open, record=True)
                print(
                    f"[LOCK IN] adjusting pinch valve to {target_pct_open:.4f} open")
                # delay to allow response in pressure
                time.sleep(VALVE_DELAY_S)
                time_tried_s += VALVE_DELAY_S
                data.update_data()
                data.log_data_at_interval(5)

                in_window_counter = 0

            if in_window_counter > 10:
                print("[LOCK IN] Stabilized...")
                break

        except TypeError:
            pass

        # heartbeat delay
        time.sleep(interval)
        time_tried_s += interval

    print("[LOCK IN] completed pinch valve lock-in.")
    return local.lib.tff.definitions.STATUS_OK


def pinch_valve_lock_in_pid(
        interval: float = 1,
        timeout_min: float = 2.,
        scale3_target_mass_g: Union[float, None] = None,
        process: "local.lib.tff.classes.Process" = None,
) -> int:
    """
    Once all pumps for a given module are up to full speed, start a timer (use 2min until you hear otherwise from us)
    over which the pinch valve can reposition to target P3 of 5 psig (let us know if this is a difficult target).

    :param [int, float] timeout_min:
    :param [int, float] interval:
    :param [int, float, None] = scale3_target_mass_g:
    :param local.lib.tff.classes.Process process:
    :return: integer for a status code
        0, None = lock in completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    # set a window around the target_p3_psi in which the valve will not adjust, the
    WINDOW_PSI: float = .5

    # time to sleep after valve adjustment
    VALVE_DELAY_S = .2

    def set_position(pct_open):
        commands = process.devices.PV.make_commands()
        command = process.devices.PV.make_set_poisition_command(
            pct_open=pct_open)
        process.devices.PV.set_command(commands, 0, command)
        process.devices.PV.set_position(commands, record=True)

    # define a timer that counts time spent in loop
    time_tried_s: int = 0

    print(
        f"[LOCK IN] beginning pinch valve lock-in to target P3 {process.setpoints.P3_target_pressure.value:.2f} psi.")

    in_window_counter = 0

    process.pid.setpoint = process.setpoints.P3_target_pressure.value
    process.pid.period_s = VALVE_DELAY_S

    while time_tried_s < timeout_min * 60:

        # update the data dictionary and
        # log the data
        process.data.update_data()
        process.data.log_data_at_interval(5)

        in_window_counter += 1

        if scale3_target_mass_g is not None:
            if process.data.W3 is not None and process.data.W3 >= scale3_target_mass_g:
                print("[LOCK IN] scale 3 target mass of {} g hit during pinch valve lock-in.".format(
                    scale3_target_mass_g))
                return local.lib.tff.definitions.STATUS_TARGET_MASS_HIT

        # try/catch for invalid pressure readings
        try:

            delta_pct_open = process.pid(process.data.P3)
            target_pct_open = process.data.PV - \
                min(max(delta_pct_open, -0.001), 0.001)

            set_position(target_pct_open)
            time.sleep(VALVE_DELAY_S)
            time_tried_s += VALVE_DELAY_S
            process.data.update_data()
            process.data.log_data_at_interval(5)

        except TypeError:
            pass

        # heartbeat delay
        time.sleep(interval)
        time_tried_s += interval

    print("[LOCK IN] completed pinch valve lock-in.")
    return local.lib.tff.definitions.STATUS_OK
