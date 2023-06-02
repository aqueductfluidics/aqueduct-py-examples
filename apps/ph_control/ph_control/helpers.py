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
            else float(format(float(value), ".{}f".format(precision)))
        )
    except ValueError:
        return INVALID_CHAR
