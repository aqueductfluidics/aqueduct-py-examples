import time
import typing

from aqueduct.devices.trcx.obj import TRCX

DELAY_S = 0.1


def set_valve_and_withdraw(pump: TRCX, pump_index: int, port: int,
                           withdraw_rate_ul_min: float, withdraw_volume_ul: float) -> None:
    """
    Set a single pump input to a specified `port` and withdraw a specified volume (uL) `withdraw_volume_ul`
    at a specified rate `withdraw_rate_ul_min`

    :return: None
    """
    # "construct" a Valve Command
    valve_command_t = pump.make_valve_command(position=port)

    # send the constructed valve command to the pumps
    pump.set_valves(**{f"pump{pump_index}": valve_command_t})

    """
    Above could also be written:
    
    pump_index_string: str = "pump" + str(pump_index)
    pump.set_valves(**{pump_index_string: valve_command_t})
    
    The ** is a keyword mapping of the dictionary {pump_index_string: valve_command_t}
    
    https://docs.python.org/3/reference/expressions.html#calls        
    """

    time.sleep(DELAY_S)

    # "construct" a Pump Command
    pump_command_t = pump.make_command(
        mode=pump.finite,  # pump.finite is a constant that belongs to the TRCX class
        direction=pump.withdraw,  # pump.withdraw is a constant that belongs to the TRCX class
        rate_units=pump.ul_min,  # pump.ul_min is a constant that belongs to the TRCX class
        rate_value=withdraw_rate_ul_min,  # set the rate value to the argument passed into this function
        finite_value=withdraw_volume_ul,  # set the volume to withdraw to the argument passed into this function
        finite_units=pump.ul,  # pump.ul is a constant that belongs to the TRCX class
    )

    # send the constructed pump command to the pumps
    pump.pump(wait_for_complete=False, **{f"pump{pump_index}": pump_command_t})

    time.sleep(DELAY_S)


def withdraw(
        pump: TRCX,
        pump_indices: typing.List[int],
        withdraw_rates_ul_min: typing.List[float],
        withdraw_volumes_ul: typing.List[float]) -> None:
    """
    Withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    # "construct" a list Pump Commands
    pump_commands_l: list = [pump.make_command(
        mode=pump.finite,  # pump.finite is a constant that belongs to the TRCX class
        direction=pump.withdraw,  # pump.withdraw is a constant that belongs to the TRCX class
        rate_units=pump.ul_min,  # pump.ul_min is a constant that belongs to the TRCX class
        rate_value=rate,  # set the rate value to the argument passed into this function
        finite_value=volume,  # set the volume to withdraw to the argument passed into this function
        finite_units=pump.ul,  # pump.ul is a constant that belongs to the TRCX class
    ) for rate, volume in zip(withdraw_rates_ul_min, withdraw_volumes_ul)]

    # send the constructed pump commands to the pumps
    pump.pump(
        wait_for_complete=False,
        **{f"pump{index}": command for index, command in zip(pump_indices, pump_commands_l)}
    )

    time.sleep(DELAY_S)


def set_valves_and_withdraw(
        pump: TRCX,
        pump_indices: typing.List[int],
        ports: typing.List[int],
        withdraw_rates_ul_min: typing.List[float],
        withdraw_volumes_ul: typing.List[float]) -> None:
    """
    Set multiple pump inputs to specified `ports` and withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    # "construct" a list of Valve Commands
    valve_commands_l: list = [pump.make_valve_command(position=p) for p in ports]

    # send the constructed valve commands to the pumps
    pump.set_valves(**{f"pump{index}": command for index, command in zip(pump_indices, valve_commands_l)})

    time.sleep(DELAY_S)

    # "construct" a list Pump Commands
    pump_commands_l: list = [pump.make_command(
        mode=pump.finite,  # pump.finite is a constant that belongs to the TRCX class
        direction=pump.withdraw,  # pump.withdraw is a constant that belongs to the TRCX class
        rate_units=pump.ul_min,  # pump.ul_min is a constant that belongs to the TRCX class
        rate_value=rate,  # set the rate value to the argument passed into this function
        finite_value=volume,  # set the volume to withdraw to the argument passed into this function
        finite_units=pump.ul,  # pump.ul is a constant that belongs to the TRCX class
    ) for rate, volume in zip(withdraw_rates_ul_min, withdraw_volumes_ul)]

    # send the constructed pump commands to the pumps
    pump.pump(
        wait_for_complete=False,
        **{f"pump{index}": command for index, command in zip(pump_indices, pump_commands_l)}
    )

    time.sleep(DELAY_S)


def set_valve_and_infuse(pump: TRCX, pump_index: int, port: int,
                         infuse_rate_ul_min: float, infuse_volume_ul: float) -> None:
    """
    Set a single pump input to a specified `port` and infuse a specified volume (uL) `infuse_volume_ul`
    at a specified rate `infuse_rate_ul_min`

    :return: None
    """

    # "construct" a Valve Command
    valve_command_t = pump.make_valve_command(position=port)

    # send the constructed valve command to the pumps
    pump.set_valves(**{f"pump{pump_index}": valve_command_t})

    time.sleep(DELAY_S)

    # "construct" a Pump Command
    pump_command_t = pump.make_command(
        mode=pump.finite,  # pump.finite is a constant that belongs to the TRCX class
        direction=pump.infuse,  # pump.infuse is a constant that belongs to the TRCX class
        rate_units=pump.ul_min,  # pump.ul_min is a constant that belongs to the TRCX class
        rate_value=infuse_rate_ul_min,  # set the rate value to the argument passed into this function
        finite_value=infuse_volume_ul,  # set the volume to infuse to the argument passed into this function
        finite_units=pump.ul,  # pump.ul is a constant that belongs to the TRCX class
    )

    # send the constructed pump command to the pumps
    pump.pump(wait_for_complete=False, **{f"pump{pump_index}": pump_command_t})

    time.sleep(DELAY_S)


def set_valves_and_infuse(
        pump: TRCX,
        pump_indices: typing.List[int],
        ports: typing.List[int],
        infuse_rates_ul_min: typing.List[float],
        infuse_volumes_ul: typing.List[float]) -> None:
    """
    Set multiple pump inputs to specified `ports` and infuse specified volumes (uL) `infuse_volumes_ul`
    at specified rates `infuse_rates_ul_min`

    :return: None
    """
    # "construct" a list of Valve Commands
    valve_commands_l: list = [pump.make_valve_command(position=p) for p in ports]

    # send the constructed valve commands to the pumps
    pump.set_valves(**{f"pump{index}": command for index, command in zip(pump_indices, valve_commands_l)})

    time.sleep(DELAY_S)

    # "construct" a list Pump Commands
    pump_commands_l: list = [pump.make_command(
        mode=pump.finite,  # pump.finite is a constant that belongs to the TRCX class
        direction=pump.infuse,  # pump.withdraw is a constant that belongs to the TRCX class
        rate_units=pump.ul_min,  # pump.ul_min is a constant that belongs to the TRCX class
        rate_value=rate,  # set the rate value to the argument passed into this function
        finite_value=volume,  # set the volume to withdraw to the argument passed into this function
        finite_units=pump.ul,  # pump.ul is a constant that belongs to the TRCX class
    ) for rate, volume in zip(infuse_rates_ul_min, infuse_volumes_ul)]

    # send the constructed pump commands to the pumps
    pump.pump(
        wait_for_complete=False,
        **{f"pump{index}": command for index, command in zip(pump_indices, pump_commands_l)}
    )

    time.sleep(DELAY_S)


def set_valves(
        pump: TRCX,
        pump_indices: typing.List[int],
        ports: typing.List[int]) -> None:
    """
    Set multiple pump inputs to specified `ports`

    :return: None
    """
    # "construct" a list of Valve Commands
    valve_commands_l: list = [pump.make_valve_command(position=p) for p in ports]

    # send the constructed valve commands to the pumps
    pump.set_valves(**{f"pump{index}": command for index, command in zip(pump_indices, valve_commands_l)})

    time.sleep(DELAY_S)


def stop_pumps(pump: TRCX, pump_indices: typing.List[int], ) -> None:
    """
    Stop one or more pumps.

    :return: None
    """
    pump.stop(**{f"pump{index}": True for index in pump_indices})

    time.sleep(DELAY_S)


def is_active(pump: TRCX, pump_indices: typing.List[int], ) -> bool:
    """
    Stop one or more pumps.

    :return: None
    """
    return pump.is_active(**{f"pump{index}": 1 for index in pump_indices})


def prime_and_fill_tubing(pump: TRCX):
    """
    Combine the `set_valve_and_withdraw` and `set_valve_and_infuse` methods to do
    the first two steps of priming:

    1) priming the input tubing line
    2) expelling waste air/liquid to a waste port

    Any of the below parameters (priming_rate_ul_min, priming_volume_ul, etc.) could be
    added as arguments to this function to make it more flexible.

    :param pump:
    :return:
    """

    pump_index = 0

    input_port = 1
    waste_port = 2

    priming_rate_ul_min = 1000
    priming_volume_ul = 400

    purging_rate_ul_min = 1000
    purging_volume_ul = 5000

    # set the valve to the input port and prime the tubing & some of the syringe
    set_valve_and_withdraw(
        pump=pump,
        pump_index=pump_index,
        port=input_port,
        withdraw_rate_ul_min=priming_rate_ul_min,
        withdraw_volume_ul=priming_volume_ul
    )

    time.sleep(DELAY_S)

    # we have to wait for the plunger to finish moving, so we wait for this pump input to become inactive

    while pump.is_active(**{f"pump{pump_index}": True}):
        time.sleep(DELAY_S)
        # print an update if you want...
        # print(f"Pump {pump_index} withdrawing...")

    # now expel to waste
    set_valve_and_infuse(
        pump=pump,
        pump_index=pump_index,
        port=waste_port,
        infuse_rate_ul_min=purging_rate_ul_min,
        infuse_volume_ul=purging_volume_ul
    )


def get_current_position_ul(pump: TRCX, index: int, plunger_position: int, plunger_resolution: int) -> float:
    """
    Calculate the current position, in uL, of the selected input.

    :param plunger_resolution:
    :param plunger_position:
    :param pump:
    :param index:
    :return: float
    """
    return pump.calc_current_ul(
        index=index,
        plunger_position=plunger_position,
        plunger_resolution=plunger_resolution,
    )


def get_syringe_volume_ul(pump: TRCX, index: int) -> float:
    """
    The the volume of the syringe (in uL) of one of the TRCX's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.config[index].syringe_vol_ul


def get_max_rate_ul_min(pump: TRCX, index: int) -> float:
    """
    The the max rate (in uL/min) of one of the TRCX's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.get_max_rate_ul_min(index)


def get_min_rate_ul_min(pump: TRCX, index: int) -> float:
    """
    The the min rate (in uL/min) of one of the TRCX's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.get_min_rate_ul_min(index)


def set_plunger_mode(pump: TRCX, index: int, target_mode: int, force: bool = False):
    """
    Helper method to change the plunger stepping mode of a given input.

    Will print the change of resolution to the screen and, if the ReactionStation's `logging_enabled`
    member is set to True, will log the change to the process log file.

    :param pump:
    :param target_mode:
    :param index:
    :param force:
    :return:
    """
    if int(pump.config[index].plgr_mode) != int(target_mode) or force is True:
        pump.set_plunger_resolution(**{f"pump{index}": target_mode})
        pump.config[index].plgr_mode = target_mode
        time.sleep(DELAY_S)


def set_plunger_modes(pump: TRCX, pump_indices: typing.List[int], target_modes: typing.List[int],
                      force_pumps: typing.List[bool] = [False, False]) -> None:
    """
    Helper method to change the plunger stepping modes of the given inputs.

    Will print the change of resolutions to the screen and, if the ReactionStation's `logging_enabled`
    member is set to True, will log the change to the process log file.

    :param pump:
    :param pump_indices:
    :param target_modes:
    :param force:
    :return:
    """
    for index, target_mode, force in zip(pump_indices, target_modes, force_pumps):
        if int(pump.config[index].plgr_mode) != int(target_mode) or force is True:
            pump.set_plunger_resolution(**{f"pump{index}": target_mode})
            pump.config[index].plgr_mode = target_mode
            time.sleep(DELAY_S)
