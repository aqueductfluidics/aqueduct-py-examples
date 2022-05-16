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


def calc_product_target_mass_g(input_mass: float, concentration: float, product_density: float = 1000.) -> float:
    """
    Calculate the target product mass, in grams, based on the input mass, in MILLIgrams, and the
    desired concentration, in g/L.

    Ex.

    500 mg input_mass
    10 g/L concentration

    target_mass = 500 mg * ( 1 g / 1000 mg) / ( 10 g/L ) * 1000 g / L = 50 g

    :param product_density: grams / L, default 1000
    :param input_mass: MILLIgrams
    :param concentration: grams / L
    :return: target_mass, grams
    :rtype: float
    """
    return input_mass / 1000. / concentration * product_density


def calc_init_conc_target_mass_g(init_conc_volume_ml: float, polysaccharide_mass_mg: float,
                                 init_conc_target_g_l: float) -> float:
    """
    Calculate the initial concentration target mass in grams.

    Ex.

    300 mL init_conc_volume_ml
    500 mg polysaccharide_mass_mg
    10 g/L init_conc_target_g_l

    init_conc_target_mass_g = 300 mL * 1 L / 1000 mL - ( 1 g / 1000 mg * 500 mg / ( 10 g/L ) ) * 1 g / mL =  250 g

    :param init_conc_volume_ml: mL
    :param polysaccharide_mass_mg: MILLIgrams
    :param init_conc_target_g_l: grams / L
    :return: init_conc_target_mass_g, grams
    :rtype: float
    """
    return init_conc_volume_ml - (polysaccharide_mass_mg / init_conc_target_g_l)


def calc_diafilt_target_mass_g(number_diafiltrations: float, polysaccharide_mass_mg: float,
                               init_conc_target_g_l: float) -> float:
    """
    Calculate the diafiltration target mass in grams.

    Ex.

    6 number_diafiltrations
    500 mg polysaccharide_mass_mg
    10 g/L init_conc_target_g_l

    diafilt_target_mass_g =
        number_diafiltrations * 1 L / 1000 mL * ( 1 g / 1000 mg * 500 mg / ( 10 g/L ) ) * 1 g / mL = 300 g

    :param number_diafiltrations: float, int (unitless?)
    :param polysaccharide_mass_mg: MILLIgrams
    :param init_conc_target_g_l: grams / L
    :return: diafilt_target_mass_g, grams
    :rtype: float
    """
    return number_diafiltrations * (polysaccharide_mass_mg / init_conc_target_g_l)


def calc_final_conc_target_mass_g(polysaccharide_mass_mg: float, init_conc_target_g_l: float,
                                  final_conc_target_g_l: float) -> float:
    """
    Calculate the final concentration target mass in grams.

    Ex.

    500 mg polysaccharide_mass_mg
    5 g/L final_conc_target_g_l
    10 g/L init_conc_target_g_l

    final_conc_target_mass_g =
        ( 1 g / 1000 mg * 500 mg / ( 10 g/L ) ) - ( 1 g / 1000 mg * 500 mg / ( 5 g/L ) ) * 1 g / mL * 1 L / 1000 mL = 300 g

    :param polysaccharide_mass_mg: MILLIgrams
    :param final_conc_target_g_l: grams / L
    :param init_conc_target_g_l: grams / L
    :return: final_conc_target_mass_g, grams
    :rtype: float
    """
    return (polysaccharide_mass_mg/init_conc_target_g_l) - (polysaccharide_mass_mg/final_conc_target_g_l)
