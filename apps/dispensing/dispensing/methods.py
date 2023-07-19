"""Dispensing Methods Module"""
# pylint: disable=pointless-string-statement
import time
import typing

from aqueduct.devices.pump import syringe
from aqueduct.devices.pump import SyringePump
from aqueduct.devices.pump.syringe import ResolutionMode
from aqueduct.devices.pump.syringe import tricontinent

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
            # pump.STATUS.Withdraw is a constant that belongs to the SyringePump class
            direction=direction,
            # pump.ul_min is a constant that belongs to the SyringePump class
            rate_units=pump.RATE_UNITS.UlMin,
            rate_value=rate,  # set the rate value to the argument passed into this function
            # set the volume to withdraw to the argument passed into this function
            finite_value=volume,
            # pump.ul is a constant that belongs to the SyringePump class
            finite_units=pump.FINITE_UNITS.Ul,
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
    # need a long valve delay to allow for actuation
    VALVE_DELAY = 1

    # "construct" a list of Valve Commands
    commands = pump.make_commands()
    for index, port in zip(pump_indices, ports):
        pump_command_t = pump.make_set_valve_command(port=port)
        pump.set_command(commands, index, pump_command_t)

    # send the constructed valve commands to the pumps
    pump.set_valves(commands=commands)

    time.sleep(VALVE_DELAY)

    # # send the constructed valve commands to the pumps
    # pump.set_valves(commands=commands)

    # time.sleep(VALVE_DELAY)


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


def get_current_position_ul(pump: SyringePump, index: int) -> float:
    """
    Calculate the current position, in uL, of the selected input.


    :param pump:
    :param index:
    :return: float
    """
    return pump.get_plunger_position_volume()[index]


def get_syringe_volume_ul(pump: SyringePump, index: int) -> float:
    """
    The the volume of the syringe (in uL) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.stat[index].syringe_volume_ul


def get_max_rate_ul_min(pump: SyringePump, index: int) -> float:
    """
    The the max rate (in uL/min) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.get_max_flow_rate_ul_min()[index]


def get_min_rate_ul_min(pump: SyringePump, index: int) -> float:
    """
    The the min rate (in uL/min) of one of the SyringePump's pump inputs.

    :param pump:
    :param index:
    :return: float
    """
    return pump.get_min_flow_rate_ul_min()[index]


def set_plunger_mode(
    pump: SyringePump,
    index: int,
    mode: ResolutionMode,
):
    """
    Helper method to change the plunger stepping mode of a given input.

    Will print the change of resolution to the screen and, if the ReactionStation's `logging_enabled`
    member is set to True, will log the change to the process log file.

    :param pump:
    :param mode:
    :param index:
    :return:
    """
    set_plunger_modes(pump, pump_indices=[index], modes=[mode])


def set_plunger_modes(
    pump: SyringePump,
    pump_indices: typing.List[int],
    modes: typing.List[ResolutionMode],
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
    commands = pump.make_commands()
    for index, mode in zip(pump_indices, modes):
        pump_command_t = pump.make_set_plunger_mode_command(mode=mode)
        pump.set_command(commands, index, pump_command_t)

    pump.set_plunger_mode(commands)
    time.sleep(DELAY_S)


class PumpError:
    """
    Represents an error in a pump.

    :param missing: Flag indicating if the pump is missing.
    :type missing: bool
    :param c_series_error: The error status of the pump.
    :type c_series_error: typing.Union[None, tricontinent.CSeriesError]
    """

    def __init__(
        self,
        missing: bool,
        c_series_error: typing.Union[None, tricontinent.CSeriesError],
    ):
        self.missing = missing
        self.c_series_error = c_series_error


def has_error(
    pump: SyringePump,
) -> typing.Tuple[PumpError]:
    """
    Check if the pump has any errors.

    :param pump: The SyringePump instance.
    :type pump: SyringePump

    :return: Tuple of error flags for each pump.
    :rtype: typing.Tuple[bool]
    """
    config = pump.config

    if config is not None:
        errors = []

        conf: tricontinent.TriContinentConfig
        for conf in config.get("config").get("data"):
            err = PumpError(conf.booted == 0, conf.c_series_error)
            errors.append(err)
        return tuple(errors)

    return tuple(pump.len * [PumpError(False, tricontinent.CSeriesError.NoError)])
