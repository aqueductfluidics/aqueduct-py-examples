"""Dispensing Methods Module"""
# pylint: disable=pointless-string-statement
import time
import typing

from aqueduct.devices.pump import syringe
from aqueduct.devices.pump import SyringePump

DELAY_S = 0.01


def set_valve_and_withdraw(
    pump: SyringePump,
    pump_index: int,
    port: int,
    withdraw_rate_ul_min: float,
    withdraw_volume_ul: float,
) -> None:
    """
    Set a single pump input to a specified `port` and withdraw a specified volume (uL) `withdraw_volume_ul`
    at a specified rate `withdraw_rate_ul_min`

    :return: None
    """
    set_valves_and_withdraw(
        pump,
        pump_indices=[pump_index],
        ports=[port],
        withdraw_rates_ul_min=[withdraw_rate_ul_min],
        withdraw_volumes_ul=[withdraw_volume_ul],
    )


def pump_finite(
    pump: SyringePump,
    pump_indices: typing.List[int],
    withdraw_rates_ul_min: typing.List[float],
    withdraw_volumes_ul: typing.List[float],
    direction: syringe.Status,
) -> None:
    """
    Withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    # "construct" a list Pump Commands
    commands = pump.make_commands()
    for index, rate, volume in zip(
        pump_indices, withdraw_rates_ul_min, withdraw_volumes_ul
    ):
        pump_command_t = pump.make_start_command(
            mode=pump.MODE.Finite,  # pump.finite is a constant that belongs to the SyringePump class
            direction=direction,  # pump.STATUS.Withdraw is a constant that belongs to the SyringePump class
            rate_units=pump.RATE_UNITS.UlMin,  # pump.ul_min is a constant that belongs to the SyringePump class
            rate_value=rate,  # set the rate value to the argument passed into this function
            finite_value=volume,  # set the volume to withdraw to the argument passed into this function
            finite_units=pump.FINITE_UNITS.Ul,  # pump.ul is a constant that belongs to the SyringePump class
        )
        pump.set_command(commands, index, pump_command_t)

    # send the constructed pump commands to the pumps
    pump.start(commands)

    time.sleep(DELAY_S)


def withdraw(
    pump: SyringePump,
    pump_indices: typing.List[int],
    withdraw_rates_ul_min: typing.List[float],
    withdraw_volumes_ul: typing.List[float],
) -> None:
    """
    Withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    pump_finite(
        pump,
        pump_indices,
        withdraw_rates_ul_min,
        withdraw_volumes_ul,
        syringe.Status.Withdrawing,
    )


def infuse(
    pump: SyringePump,
    pump_indices: typing.List[int],
    infuse_rates_ul_min: typing.List[float],
    infuse_volumes_ul: typing.List[float],
) -> None:
    """
    Withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    pump_finite(
        pump,
        pump_indices,
        infuse_rates_ul_min,
        infuse_volumes_ul,
        syringe.Status.Infusing,
    )


def set_valves(
    pump: SyringePump,
    pump_indices: typing.List[int],
    ports: typing.List[int],
) -> None:
    """
    Set multiple pump inputs to specified `ports` and withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    # "construct" a list of Valve Commands
    commands = pump.make_commands()
    for index, port in zip(pump_indices, ports):
        pump_command_t = pump.make_set_valve_command(port=port)
        pump.set_command(commands, index, pump_command_t)

    # send the constructed valve commands to the pumps
    pump.set_valves(commands=commands)

    time.sleep(DELAY_S)


def set_valves_and_withdraw(
    pump: SyringePump,
    pump_indices: typing.List[int],
    ports: typing.List[int],
    withdraw_rates_ul_min: typing.List[float],
    withdraw_volumes_ul: typing.List[float],
) -> None:
    """
    Set multiple pump inputs to specified `ports` and withdraw specified volumes (uL) `withdraw_volumes_ul`
    at specified rates `withdraw_rates_ul_min`

    :return: None
    """
    set_valves(pump, pump_indices, ports)

    withdraw(pump, pump_indices, withdraw_rates_ul_min, withdraw_volumes_ul)


def set_valve_and_infuse(
    pump: SyringePump,
    pump_index: int,
    port: int,
    infuse_rate_ul_min: float,
    infuse_volume_ul: float,
) -> None:
    """
    Set a single pump input to a specified `port` and infuse a specified volume (uL) `infuse_volume_ul`
    at a specified rate `infuse_rate_ul_min`

    :return: None
    """
    set_valves_and_infuse(
        pump,
        pump_indices=[pump_index],
        ports=[port],
        infuse_rates_ul_min=[infuse_rate_ul_min],
        infuse_volumes_ul=[infuse_volume_ul],
    )


def set_valves_and_infuse(
    pump: SyringePump,
    pump_indices: typing.List[int],
    ports: typing.List[int],
    infuse_rates_ul_min: typing.List[float],
    infuse_volumes_ul: typing.List[float],
) -> None:
    """
    Set multiple pump inputs to specified `ports` and infuse specified volumes (uL) `infuse_volumes_ul`
    at specified rates `infuse_rates_ul_min`

    :return: None
    """
    set_valves(pump, pump_indices, ports)

    infuse(pump, pump_indices, infuse_rates_ul_min, infuse_volumes_ul)


def stop_pumps(
    pump: SyringePump,
    pump_indices: typing.List[int],
) -> None:
    """
    Stop one or more pumps.

    :return: None
    """
    commands = pump.make_commands()
    for index in pump_indices:
        pump_command_t = pump.make_stop_command()
        pump.set_command(commands, index, pump_command_t)

    pump.stop(commands)

    time.sleep(DELAY_S)


def is_active(
    pump: SyringePump,
    pump_indices: typing.List[int],
) -> bool:
    """
    Stop one or more pumps.

    :return: None
    """
    status = pump.get_status()
    return all([status[v] for v in pump_indices])


def prime_and_fill_tubing(pump: SyringePump):
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
        withdraw_volume_ul=priming_volume_ul,
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
        infuse_volume_ul=purging_volume_ul,
    )


def get_current_position_ul(
    pump: SyringePump, index: int, plunger_position: int, plunger_resolution: int
) -> float:
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


def get_syringe_volume_ul(pump: SyringePump, index: int) -> float:
    """
    The the volume of the syringe (in uL) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    # return pump.config[index].syringe_vol_ul
    return 5000


def get_max_rate_ul_min(pump: SyringePump, index: int) -> float:
    """
    The the max rate (in uL/min) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    # return pump.get_max_rate_ul_min(index)
    return 50000


def get_min_rate_ul_min(pump: SyringePump, index: int) -> float:
    """
    The the min rate (in uL/min) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    # return pump.get_min_rate_ul_min(index)
    return 5


def set_plunger_mode(
    pump: SyringePump, index: int, target_mode: int, force: bool = False
):
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
    # if int(pump.config[index].plgr_mode) != int(target_mode) or force is True:
    #     pump.set_plunger_resolution(**{f"pump{index}": target_mode})
    #     pump.config[index].plgr_mode = target_mode
    #     time.sleep(DELAY_S)
    None


def set_plunger_modes(
    pump: SyringePump,
    pump_indices: typing.List[int],
    target_modes: typing.List[int],
    force_pumps: typing.List[bool] = [False, False],
) -> None:
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
    # for index, target_mode, force in zip(pump_indices, target_modes, force_pumps):
    #     if int(pump.config[index].plgr_mode) != int(target_mode) or force is True:
    #         pump.set_plunger_resolution(**{f"pump{index}": target_mode})
    #         pump.config[index].plgr_mode = target_mode
    #         time.sleep(DELAY_S)
    None
