import time
from typing import List
from typing import Union

import aqueduct.devices.mfpp.obj
import aqueduct.devices.scip.obj
import lnp.classes
import lnp.data
import lnp.definitions
import lnp.devices
import lnp.helpers


def pump_ramp(
    interval_s: int = 1,
    pump: "aqueduct.devices.mfpp.obj.MFPP" = None,
    pump_name: str = "PUMP",
    start_flowrate_ml_min: Union[float, int] = 10,
    end_flowrate_ml_min: Union[float, int] = 20,
    rate_change_interval_s: Union[float, int] = 10,
    rate_change_ml_min: Union[float, int] = 2,
    rate_change_pct: Union[float, None] = None,
    timeout_min: Union[float, int] = 10,
    devices_obj: "lnp.devices.Devices" = None,
    data: "lnp.data.Data" = None,
    watchdog: "lnp.classes.Watchdog" = None,
) -> int:
    """
    Start and then ramp a pump's flowrate in incremented steps.

    :param interval_s: time, in seconds, of outer loop heartbeat
    :param pump_name: name of Pump to display
    :param pump: MFPP object
    :rtype pump: lnp.classes.aqueduct.devices.mfpp.obj.MFPP
    :param start_flowrate_ml_min: starting flowrate in mL/min
    :param end_flowrate_ml_min: ending flowrate in mL/min
    :param rate_change_interval_s: time, in seconds, between changing the flowrate
        of pump
    :param rate_change_ml_min: value, in mL/min, of each step increase in flowrate
    :param rate_change_pct: value, between 0 and 1, sets the pct increase of each step between
        the start and end flowrates
    :param timeout_min: time, in minutes, before returning early from method
        if `pump1_end_flowrate_ml_min` is not achieved
    :param devices_obj:
    :rtype devices_obj: lnp.classes:Devices
    :param data:
    :rtype data: lnp.classes:Data
    :param watchdog:
    :rtype watchdog: lnp.classes.Watchdog
    :return: integer for a status code
        0, None = ramps completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    # start PUMP at start_flowrate_ml_min
    print(
        "[RAMP] Starting {} at {:.2f} mL/min".format(pump_name, start_flowrate_ml_min)
    )
    pump.start(
        mode="continuous",
        direction="forward",
        rate_value=start_flowrate_ml_min,
        rate_units="ml_min",
        record=True,
    )

    # save the starting time
    time_start: float = time.time()

    # find the timeout time to break from loop
    timeout: float = time_start + timeout_min * 60

    target_pump1_ml_min = pump.get_flow_rate()

    # if the rate_change_pct is set, calculate a new rate_change_ml_min
    if rate_change_pct is not None:
        rate_change_ml_min = round(
            (end_flowrate_ml_min - start_flowrate_ml_min) * rate_change_pct, 2
        )

    # while the flow rate of PUMP1 is less than the target, gradually increase the
    # rate in increments of 2 mL/min
    while target_pump1_ml_min < end_flowrate_ml_min:

        # check to see whether we've timed out
        if time.time() > timeout:
            print("[RAMP] Timed out during {} ramp up.".format(pump_name))
            return lnp.definitions.STATUS_TIMED_OUT

        time_loop_start: float = time.time()

        # wait for rate_change_interval_s seconds before increasing pump1 rate
        # while waiting, call the monitor method to check pressures
        # there is an interval second heartbeat in the monitor method between data updates
        while time.time() < time_loop_start + rate_change_interval_s:
            # perform the monitoring method until it's time to increase the Pump's rate
            lnp.methods.monitor(
                interval_s=interval_s,
                devices_obj=devices_obj,
                data=data,
                watchdog=watchdog,
            )

        # increase the rate of PUMP by rate_change_ml_min mL/min, don't exceed the target flowrate
        target_pump1_ml_min = min(
            pump.get_flow_rate() + rate_change_ml_min, end_flowrate_ml_min
        )
        print(
            "[RAMP] Adjusting {} rate to {:.2f} mL/min".format(
                pump_name, target_pump1_ml_min
            )
        )
        pump.change_speed(target_pump1_ml_min)

    print("[RAMP] Completed {} ramp up.".format(pump_name))

    return lnp.definitions.STATUS_OK


def multi_pump_ramp(
    pumps: List[aqueduct.devices.mfpp.obj.MFPP],
    start_flow_rates_ml_min: Union[float, int],
    end_flow_rates_ml_min: Union[float, int],
    interval_s: int = 1,
    number_rate_changes: int = 6,
    rate_change_interval_s: Union[float, int] = 10,
    timeout_min: Union[float, int] = 30,
    devices_obj: "lnp.classes.Devices" = None,
    data: "lnp.classes.Data" = None,
    watchdog: "lnp.classes.Watchdog" = None,
) -> int:
    """ """
    time_start: float = time.time()

    # find the timeout time to break from loop
    timeout: float = time_start + timeout_min * 60

    # dimension = number of rate changes - 1 * number of pumps
    rate_changes: List[List[float]] = [
        len(pumps) * [0.0] for _ in range(number_rate_changes - 1)
    ]

    pump_index = 0
    for (pump, start_rate, end_rate) in zip(
        pumps, start_flow_rates_ml_min, end_flow_rates_ml_min
    ):
        pump: aqueduct.devices.mfpp.obj.MFPP
        print("[MULTI RAMP] Starting {} at {:.2f} mL/min".format(pump.name, start_rate))
        pump.start(
            mode="continuous",
            direction="forward",
            rate_value=start_rate,
            rate_units="ml_min",
            record=True,
        )

        rates = lnp.helpers.get_flowrate_range(
            start_flow_rate=start_rate,
            end_flow_rate=end_rate,
            steps=number_rate_changes,
        )
        for ii, r in enumerate(rates[1::]):
            rate_changes[ii][pump_index] = r

        pump_index += 1

    for r in rate_changes:

        # check to see whether we've timed out
        if time.time() > timeout:
            print("[DUAL RAMP] Timed out stabilizing during pumps 2 and 3 ramp up.")
            return lnp.definitions.STATUS_TIMED_OUT

        time_loop_start: float = time.time()

        # wait for rate_change_interval_s seconds before increasing pumps 2 and 3 rates
        while time.time() < time_loop_start + rate_change_interval_s:
            # monitor P1, P3 and feedback on PV and PUMP1 if needed
            monitor(
                interval_s=interval_s,
                devices_obj=devices_obj,
                data=data,
                watchdog=watchdog,
            )

        for (pump, rate) in zip(pumps, r):
            pump: aqueduct.devices.mfpp.obj.MFPP
            print("[MULTI RAMP] Adjusting {} to {:.2f} mL/min".format(pump.name, rate))
            pump.change_speed(
                rate_value=rate,
                rate_units="ml_min",
            )

    # check all alarms
    if isinstance(watchdog, lnp.classes.Watchdog):
        watchdog.check_alarms()

    # heartbeat delay
    print("[MULTI RAMP] Completed ramp up.")

    return lnp.definitions.STATUS_OK


def monitor(
    interval_s: float = 1,
    devices_obj: "lnp.devices.Devices" = None,
    data: "lnp.data.Data" = None,
    watchdog: "lnp.classes.Watchdog" = None,
    process: "lnp.classes.Process" = None,
) -> None:
    """
    Logging and Monitoring logic to:

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
    :param lnp.classes.Devices devices_obj:
    :param lnp.classes.Data data:
    :param lnp.classes.Watchdog watchdog:
    :param lnp.classes.Process process:
    :return: None
    """
    # update the data dictionary and
    # log the data
    data.update_data()
    data.log_data_at_interval(5)

    # check alarms if watchdog is not None
    if isinstance(watchdog, lnp.classes.Watchdog):
        watchdog.check_alarms()

    # heartbeat delay
    time.sleep(interval_s)


def pinch_valve_lock_in_pid(
    interval: float = 1,
    timeout_min: float = 2.0,
    scale3_target_mass_g: Union[float, None] = None,
    process: "lnp.classes.Process" = None,
) -> int:
    """
    Once all pumps for a given module are up to full speed, start a timer (use 2min until you hear otherwise from us)
    over which the pinch valve can reposition to target P3 of 5 psig (let us know if this is a difficult target).

    :param [int, float] timeout_min:
    :param [int, float] interval:
    :param [int, float, None] = scale3_target_mass_g:
    :param lnp.classes.Process process:
    :return: integer for a status code
        0, None = lock in completed
        1 = timed out
        2 = scale 3 hit target mass
    """
    # set a window around the target_p3_psi in which the valve will not adjust, the
    WINDOW_PSI: float = 0.5

    # time to sleep after valve adjustment
    VALVE_DELAY_S = 0.2

    # define a timer that counts time spent in loop
    time_tried_s: int = 0

    print(
        "[LOCK IN] beginning pinch valve lock-in to target P3 {} psi.".format(
            process.setpoints.aq_target_ml_min.value
        )
    )

    in_window_counter = 0

    process.pid.setpoint = process.setpoints.aq_target_ml_min.value
    process.pid.period_s = VALVE_DELAY_S

    while time_tried_s < timeout_min * 60:

        # update the data dictionary and
        # log the data
        process.data.update_data()
        process.data.log_data_at_interval(5)

        in_window_counter += 1

        if scale3_target_mass_g is not None:
            if process.data.W3 is not None and process.data.W3 >= scale3_target_mass_g:
                print(
                    "[LOCK IN] scale 3 target mass of {} g hit during pinch valve lock-in.".format(
                        scale3_target_mass_g
                    )
                )
                return lnp.definitions.STATUS_TARGET_MASS_HIT

        # try/catch for invalid pressure readings
        try:

            delta_pct_open = process.pid(process.data.P3)
            target_pct_open = process.data.PV - min(max(delta_pct_open, -0.001), 0.001)
            process.devices.PV.set_position(target_pct_open, record=True)
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
    return lnp.definitions.STATUS_OK
