from typing import Union

from aqueduct.core.aq import Aqueduct
from aqueduct.devices.pump import SyringePump
from dispensing.definitions import PUMP_NAME


class Devices:
    """
    Class with members to contain each Aqueduct Device
    Object in the dispensing Setup.

    PUMP is the TriContinent C(X) series of pumps with up to 12 inputs

    In DEV MODE, we create `SyringePump` for easy access to
    the methods for each device type.

    In LAB MODE, we associate each Device with the Name for the device
    that is saved on its firmware.
    """

    PUMP: SyringePump = None

    def __init__(self, aq: Aqueduct):
        self.PUMP = aq.devices.get(PUMP_NAME)


class Data:
    """
    Class to help with logging and updating data for the dosing setup.
    """

    W1: Union[float, None] = None  # weight on the SCALE, in grams

    timestamp: Union[float, None] = None
    # timestamp of last write to log file
    log_timestamp: Union[float, None] = None
    _logging_interval_s: Union[
        int, float
    ] = 5  # interval in seconds between writes to log file

    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object

    def __init__(self, devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param devices_obj:
        :param aqueduct_obj:
        """
        self._devices = devices_obj
        self._aqueduct = aqueduct_obj

        if isinstance(aqueduct_obj, Aqueduct):
            self._is_lab_mode = aqueduct_obj.is_lab_mode()
        else:
            self._is_lab_mode = False
