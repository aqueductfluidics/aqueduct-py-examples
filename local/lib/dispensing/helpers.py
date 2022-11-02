from typing import Union

INVALID_CHAR = "~"


def format_float(value: Union[float, int, str], precision: int = 2) -> str:
    """
    Helper method to format a value as a float with
    precision and handle possible None values.

    :param value:
    :param precision:
    :return:
    """
    try:
        return INVALID_CHAR if value is None else format(float(value), '.{}f'.format(precision))
    except ValueError:
        return INVALID_CHAR


def get_flowrate_range(start_flow_rate: float, end_flow_rate: float, steps: int) -> list:
    """
    Return a list of flowrates starting at `start_flow_rate` and ending at
    `end_flow_rate` of length steps with equal intervals between them.

    Rounded to precision of 2 decimals.

    :param start_flow_rate:
    :param end_flow_rate:
    :param steps:
    :return:
    """

    interval = (end_flow_rate - start_flow_rate) / (steps - 1)
    return [round(start_flow_rate + i * interval, 2) for i in range(0, steps)]


def calc_tubing_volume_ul(length_mm: float, inner_diameter_mm: float) -> float:
    """
    Calculates the total volume in mL of a connection.

    :param inner_diameter_mm:
    :param length_mm:
    :return: volume_ml
    :rtype: float
    """
    return 3.14159 * (inner_diameter_mm / 2) ** 2 * length_mm / 1000000


def calc_minimum_flowrate_ul_min(pump_series: int, syringe_volume_ul: float, resolution: int) -> float:
    """
    Calculates the minimum flowrate achievable for a given pump series, syringe volume, and step resolution.

    CX6000 = 0,
    CX48000 = 1,
    C3000 = 2,
    C24000 = 3

    N0 = 0,
    N1 = 1,
    N2 = 2,

    Manual Page 140:

    Examples
    • 1 mL syringe on C3000 in N0 or N1 mode at velocity [V] of 6000 increments/sec:
        flow rate = (1000 µL/6000) * 6000 = 1000 µL/sec (see note
    below)
    • 1 mL syringe on C3000 in N2 mode at velocity [V] of 6000 increments/
    sec: flow rate = (1000 µL/48000) * 6000 = 125 µL/sec
    • 1 mL syringe on C24000 in N0 or N1 mode at velocity [V] of 6000 increments/sec:
        flow rate = (1000 µL /24000) * 6000 = 250 µL/sec
    • 1 mL syringe on C24000 in N2 mode at velocity [V] of 6000 increments/
    sec: flow rate = (1000 µL/192000) * 6000 = 31.25 µL /sec

    :param pump_series:
    :param syringe_volume_ul:
    :param resolution:
    :return:
    """
    if pump_series == 2:
        if resolution in (0, 1):
            return syringe_volume_ul / 6000. * 60
        if resolution in (2,):
            return syringe_volume_ul / 48000. * 60
    elif pump_series == 3:
        if resolution in (0, 1):
            return syringe_volume_ul / 24000. * 60
        if resolution in (2,):
            return syringe_volume_ul / 192000. * 60
    return 0.


def calc_maximum_flowrate_ul_min(pump_series: int, syringe_volume_ul: float, resolution: int) -> float:
    """
    Calculates the maximum flowrate achievable for a given pump series, syringe volume, and step resolution.

    CX6000 = 0,
    CX48000 = 1,
    C3000 = 2,
    C24000 = 3

    N0 = 0,
    N1 = 1,
    N2 = 2,

    Manual Page 140:

    Examples
    • 1 mL syringe on C3000 in N0 or N1 mode at velocity [V] of 6000 increments/sec:
        flow rate = (1000 µL/6000) * 6000 = 1000 µL/sec (see note
    below)
    • 1 mL syringe on C3000 in N2 mode at velocity [V] of 6000 increments/
    sec: flow rate = (1000 µL/48000) * 6000 = 125 µL/sec
    • 1 mL syringe on C24000 in N0 or N1 mode at velocity [V] of 6000 increments/sec:
        flow rate = (1000 µL /24000) * 6000 = 250 µL/sec
    • 1 mL syringe on C24000 in N2 mode at velocity [V] of 6000 increments/
    sec: flow rate = (1000 µL/192000) * 6000 = 31.25 µL /sec

    :param pump_series:
    :param syringe_volume_ul:
    :param resolution:
    :return:
    """
    if pump_series == 2:
        if resolution in (0, 1):
            return syringe_volume_ul / 6000. * 60
        if resolution in (2,):
            return syringe_volume_ul / 48000. * 60
    elif pump_series == 3:
        if resolution in (0, 1):
            return syringe_volume_ul / 24000. * 60
        if resolution in (2,):
            return syringe_volume_ul / 192000. * 60
    return 0.


def optimize_flowrates_to_target_ratio(target_ratio: float, target_combined_rate_ul_min: float, pump_1_volume_ul: float,
                                       pump_1_series: int, pump_2_volume_ul: int, pump_2_series: int,
                                       print_results: bool = True, limit: int = 10) -> tuple:
    """
    Target ratio == pump 1 / pump 2.

    Find pump 1 rate for ideal ratio and target rate.

    Pick attainable values within 10 increments either way of the nearest attainable.

    Calc

    :param limit:
    :param print_results:
    :param target_ratio:
    :param target_combined_rate_ul_min:
    :param pump_1_volume_ul:
    :param pump_1_series:
    :param pump_2_volume_ul:
    :param pump_2_series:
    :return:
    """
    ideal_pump_1_flowrate_ul_min = target_combined_rate_ul_min - (target_combined_rate_ul_min / (target_ratio + 1.))
    ideal_pump_2_flowrate_ul_min = target_combined_rate_ul_min - ideal_pump_1_flowrate_ul_min

    pump_1_rate_step_ul_min = calc_minimum_flowrate_ul_min(
        pump_series=pump_1_series,
        syringe_volume_ul=pump_1_volume_ul,
        resolution=2
    )

    pump_2_rate_step_ul_min = calc_minimum_flowrate_ul_min(
        pump_series=pump_2_series,
        syringe_volume_ul=pump_2_volume_ul,
        resolution=2
    )

    nearest_attainable_pump_1_flowrate_ul_min = (int(ideal_pump_1_flowrate_ul_min / pump_1_rate_step_ul_min) *
                                                 pump_1_rate_step_ul_min)

    nearest_attainable_pump_2_flowrate_ul_min = (int(ideal_pump_2_flowrate_ul_min / pump_2_rate_step_ul_min) *
                                                 pump_2_rate_step_ul_min)

    pump_1_flowrate_range_ul_min = tuple(
        nearest_attainable_pump_1_flowrate_ul_min + i * pump_1_rate_step_ul_min for i in range(-10, 10)
    )

    pump_2_flowrate_range_ul_min = tuple(
        nearest_attainable_pump_2_flowrate_ul_min + i * pump_2_rate_step_ul_min for i in range(-10, 10)
    )

    results = []

    for r1 in pump_1_flowrate_range_ul_min:
        for r2 in pump_2_flowrate_range_ul_min:
            try:
                result = dict(
                    combined_rate_ul=round(r1 + r2, 5),
                    ratio=round(r1 / r2, 5),
                    ratio_dev=abs(round(target_ratio - r1 / r2, 5)),
                    pump_1_rate_ul_min=round(r1, 5),
                    pump_2_rate_ul_min=round(r2, 5),
                    rate_dev=round(target_combined_rate_ul_min - r1 - r2, 5),
                )
                results.append(result)
            except ZeroDivisionError:
                continue

    results = sorted(results, key=lambda k: k['ratio_dev'])[0:limit]

    if print_results is True:
        import pprint
        pprint.pprint(results)

    return tuple(results)
