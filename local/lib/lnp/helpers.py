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

