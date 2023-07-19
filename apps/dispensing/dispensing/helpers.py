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
        return (
            INVALID_CHAR
            if value is None
            else format(float(value), ".{}f".format(precision))
        )
    except ValueError:
        return INVALID_CHAR


def get_flowrate_range(
    start_flow_rate: float, end_flow_rate: float, steps: int
) -> list:
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


def calc_minimum_flowrate_ul_min(
    pump_series: int, syringe_volume_ul: float, resolution: int
) -> float:
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
            return syringe_volume_ul / 6000.0 * 60
        if resolution in (2,):
            return syringe_volume_ul / 48000.0 * 60
    elif pump_series == 3:
        if resolution in (0, 1):
            return syringe_volume_ul / 24000.0 * 60
        if resolution in (2,):
            return syringe_volume_ul / 192000.0 * 60
    return 0.0


def calc_maximum_flowrate_ul_min(
    pump_series: int, syringe_volume_ul: float, resolution: int
) -> float:
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
            return syringe_volume_ul / 6000.0 * 60 * 6000
        if resolution in (2,):
            return syringe_volume_ul / 48000.0 * 60 * 6000
    elif pump_series == 3:
        if resolution in (0, 1):
            return syringe_volume_ul / 24000.0 * 60 * 6000
        if resolution in (2,):
            return syringe_volume_ul / 192000.0 * 60 * 6000
    return 0.0


def optimize_flowrates_to_target_ratio(
    target_ratio: float,
    target_combined_rate_ul_min: float,
    pump_1_volume_ul: float,
    pump_1_series: int,
    pump_2_volume_ul: int,
    pump_2_series: int,
    print_results: bool = True,
    limit: int = 10,
) -> tuple:
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
    ideal_pump_1_flowrate_ul_min = target_combined_rate_ul_min - (
        target_combined_rate_ul_min / (target_ratio + 1.0)
    )
    ideal_pump_2_flowrate_ul_min = (
        target_combined_rate_ul_min - ideal_pump_1_flowrate_ul_min
    )

    pump_1_rate_step_ul_min = calc_minimum_flowrate_ul_min(
        pump_series=pump_1_series, syringe_volume_ul=pump_1_volume_ul, resolution=2
    )

    pump_2_rate_step_ul_min = calc_minimum_flowrate_ul_min(
        pump_series=pump_2_series, syringe_volume_ul=pump_2_volume_ul, resolution=2
    )

    nearest_attainable_pump_1_flowrate_ul_min = (
        int(ideal_pump_1_flowrate_ul_min / pump_1_rate_step_ul_min)
        * pump_1_rate_step_ul_min
    )

    nearest_attainable_pump_2_flowrate_ul_min = (
        int(ideal_pump_2_flowrate_ul_min / pump_2_rate_step_ul_min)
        * pump_2_rate_step_ul_min
    )

    pump_1_flowrate_range_ul_min = tuple(
        nearest_attainable_pump_1_flowrate_ul_min + i * pump_1_rate_step_ul_min
        for i in range(-10, 10)
    )

    pump_2_flowrate_range_ul_min = tuple(
        nearest_attainable_pump_2_flowrate_ul_min + i * pump_2_rate_step_ul_min
        for i in range(-10, 10)
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

    results = sorted(results, key=lambda k: k["ratio_dev"])[0:limit]

    if print_results is True:
        import pprint

        pprint.pprint(results)

    return tuple(results)


class DataRow:
    """
    Represents a data row with information about total volume, pump index, and chemical name.

    :param total_volume_ml: The total volume in milliliters.
    :type total_volume_ml: float
    :param pump_index: The pump index.
    :type pump_index: int
    :param chemical_name: The name of the chemical.
    :type chemical_name: str
    """

    total_volume_ml: float
    pump_index: int
    chemical_name: str

    def __init__(self, total_volume_ml: float, pump_index: int, chemical_name: str):
        self.total_volume_ml = total_volume_ml
        self.pump_index = pump_index
        self.chemical_name = chemical_name


class TimeAndRate:
    """
    Represents time and rate information.

    :param minutes: The time in minutes.
    :type minutes: float
    :param ul_min: The rate in microliters per minute.
    :type ul_min: float
    """

    minutes: float
    ul_min: float

    def __init__(self, minutes: float, ul_min: float):
        self.minutes = minutes
        self.ul_min = ul_min


def extract_total_volume_and_pump_index(
    data: list,
    station: int,
    chem: int,
) -> DataRow:
    """
    Extract
        - the total volume (in mL)
        - pump index (an integer)
        - chemical name

    from the template CSV for the timed dispense protocol.

    The function expects
      :param: data: List[List[dict]]
        - [
            [
                ...
                {'value': 'MonomerA', 'name': 'Chem2', 'index': 30},
                {'value': '0', 'name': 'Pump_Chem2', 'index': 31},
                {'value': '12.5', 'name': 'Syringe_Chem2(mL)', 'index': 32},
                {'value': '40', 'name': 'Chem2(mL)', 'index': 33},
                {'value': '1', 'name': 'Chem2_time1(min)', 'index': 34},
                {'value': '4000', 'name': 'Chem2_rate1(uL/min)', 'index': 35},
                ...
            ]
            ,
        ]

        :param: station: int - the station index (0-5, for up to six stations) to extract
        :param: chem: int - the chemical (1 or 2) to extract
    """
    volume_key = f"Chem{chem}(mL)"
    pump_key = f"Pump_Chem{chem}"

    if chem == 1:
        name_key = 'Chem1 "initiator"'
    else:
        name_key = 'Chem2 "monomer"'

    index = next(
        (
            index
            for (index, d) in enumerate(data[station])
            if d.get("name") == volume_key
        ),
        None,
    )
    volume_ml = float(data[station][index].get("value"))

    index = next(
        (index for (index, d) in enumerate(data[station]) if d.get("name") == pump_key),
        None,
    )
    pump_index = int(data[station][index].get("value"))

    index = next(
        (index for (index, d) in enumerate(data[station]) if d.get("name") == name_key),
        None,
    )
    name = data[station][index].get("value")

    return DataRow(volume_ml, pump_index, name)


def extract_time_and_rate(
    data: list, station: int, chem: int, slot: int
) -> TimeAndRate:
    """
    Extract the time (in minutes) and rate (in uL/min) from the template CSV for the
    timed dispense protocol.

    The function expects
      :param: data: List[List[dict]]
        - [
            [
                {'value': 'R1-A', 'name': 'ELN', 'index': 0},
                {'value': '1', 'name': 'Reactor', 'index': 1},
                {'value': '80', 'name': 'Temp(C)', 'index': 2},
                {'value': '2', 'name': 'time_polym(h)', 'index': 3},
                {'value': '5', 'name': 'Heel_Chem(g)', 'index': 4},
                {'value': '25', 'name': 'Heel_Water(mL)', 'index': 5},
                {'value': 'Initiator1', 'name': 'Chem1', 'index': 6},
                {'value': '6', 'name': 'Pump_Chem1', 'index': 7},
                {'value': '12.5', 'name': 'Syringe_Chem1(mL)', 'index': 8},
                {'value': '6', 'name': 'Chem1(mL)', 'index': 9},
                {'value': '1', 'name': 'Chem1_time1(min)', 'index': 10},
                {'value': '600', 'name': 'Chem1_rate1(uL/min)', 'index': 11},
                {'value': '60', 'name': 'Chem1_time2(min)', 'index': 12},
                {'value': '80', 'name': 'Chem1_rate2(uL/min)', 'index': 13},
                {'value': '30', 'name': 'Chem1_time3(min)', 'index': 14},
                {'value': '20', 'name': 'Chem1_rate3(uL/min)', 'index': 15},
                {'value': '1', 'name': 'Chem1_time4(min)', 'index': 16},
                {'value': '600', 'name': 'Chem1_rate4(uL/min)', 'index': 17},
                {'value': '60', 'name': 'Chem1_time5(min)', 'index': 18},
                {'value': '80', 'name': 'Chem1_rate5(uL/min)', 'index': 19},
                {'value': '30', 'name': 'Chem1_time6(min)', 'index': 20},
                {'value': '20', 'name': 'Chem1_rate6(uL/min)', 'index': 21},
                {'value': '1', 'name': 'Chem1_time7(min)', 'index': 22},
                {'value': '600', 'name': 'Chem1_rate7(uL/min)', 'index': 23},
                {'value': '60', 'name': 'Chem1_time8(min)', 'index': 24},
                {'value': '80', 'name': 'Chem1_rate8(uL/min)', 'index': 25},
                {'value': '30', 'name': 'Chem1_time9(min)', 'index': 26},
                {'value': '20', 'name': 'Chem1_rate9(uL/min)', 'index': 27},
                {'value': '30', 'name': 'Chem1_time10(min)', 'index': 28},
                {'value': '20', 'name': 'Chem1_rate10(uL/min)', 'index': 29},
                {'value': 'MonomerA', 'name': 'Chem2', 'index': 30},
                {'value': '0', 'name': 'Pump_Chem2', 'index': 31},
                {'value': '12.5', 'name': 'Syringe_Chem2(mL)', 'index': 32},
                {'value': '40', 'name': 'Chem2(mL)', 'index': 33},
                {'value': '1', 'name': 'Chem2_time1(min)', 'index': 34},
                {'value': '4000', 'name': 'Chem2_rate1(uL/min)', 'index': 35},
                ...
            ]
            ,
        ]

        :param: station: int - the station index (0-5, for up to six stations) to extract
        :param: chem: int - the chemical (1 or 2) to extract
        :param: slot: int - (1-10) for the time slot, !!! don't use 0 !!!
    """
    time_key = f"Chem{chem}_time{slot}(min)"
    rate_key = f"Chem{chem}_rate{slot}(uL/min)"

    index = next(
        (index for (index, d) in enumerate(data[station]) if d.get("name") == time_key),
        None,
    )
    minutes = float(data[station][index].get("value"))

    index = next(
        (index for (index, d) in enumerate(data[station]) if d.get("name") == rate_key),
        None,
    )
    ul_min = float(data[station][index].get("value"))

    return TimeAndRate(minutes, ul_min)
