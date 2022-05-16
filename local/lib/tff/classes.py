import datetime
import time
import pprint
import inspect

import local.lib.tff.helpers
import local.lib.tff.methods
import local.lib.tff.models
from local.lib.tff.definitions import *

from aqueduct.aqueduct import Aqueduct, Setpoint
import devices.aqueduct.mfpp.obj
import devices.aqueduct.ohsa.obj
import devices.aqueduct.scip.obj
import devices.aqueduct.pv.obj
import devices.aqueduct.mfpp.constants
import devices.aqueduct.scip.constants
import devices.aqueduct.pv.constants
import devices.aqueduct.ohsa.constants

from typing import List, Union


class Devices(object):
    """
    Class with members to contain each Aqueduct Device
    Object in the TFF Setup.

    PUMP1 is the MasterFlex pump between scale 1 and the TFF cartridge input, feed pump

    PUMP2 is the MasterFlex pump between scale 2 and scale 1, buffer pump
    ** CAN BE NONE IN 2 PUMP CONFIG **

    PUMP3 is the MasterFlex pump between the TFF outlet and scale 3, retentate pump

    PV is the pinch valve that controls the backpressure across the
        TFF membrane

    OHSA is the Aqueduct Device that interfaces with 3 Ohaus Adventurer
        balances

    SCIP is the Aqueduct Device that interfaces with 3 Parker SciLog
        SciPres transducers

    In DEV MODE, we create `devices.aqueduct.mfpp.obj` for easy access to
    the methods for each device type.

    In LAB MODE, we associate each Device with the Name for the device
    that is saved on its firmware.

    """
    PUMP1: devices.aqueduct.mfpp.obj.MFPP = None
    PUMP2: devices.aqueduct.mfpp.obj.MFPP = None
    PUMP3: devices.aqueduct.mfpp.obj.MFPP = None
    SCIP: devices.aqueduct.scip.obj.SCIP = None
    OHSA: devices.aqueduct.ohsa.obj.OHSA = None
    PV: devices.aqueduct.pv.obj.PV = None

    def __init__(self, **kwargs):
        self.PUMP1 = kwargs.get(PUMP1_NAME)
        self.PUMP2 = kwargs.get(PUMP2_NAME)
        self.PUMP3 = kwargs.get(PUMP3_NAME)
        self.OHSA = kwargs.get(OHSA_NAME)
        self.SCIP = kwargs.get(SCIP_NAME)
        self.PV = kwargs.get(PV_NAME)

    @classmethod
    def generate_dev_devices(cls):
        dev = Devices()
        dev.PUMP1 = devices.aqueduct.mfpp.obj.MFPP(**devices.aqueduct.mfpp.constants.BASE)
        dev.PUMP2 = devices.aqueduct.mfpp.obj.MFPP(**devices.aqueduct.mfpp.constants.BASE)
        dev.PUMP3 = devices.aqueduct.mfpp.obj.MFPP(**devices.aqueduct.mfpp.constants.BASE)
        dev.PV = devices.aqueduct.pv.obj.PV(**devices.aqueduct.pv.constants.BASE)
        dev.OHSA = devices.aqueduct.ohsa.obj.OHSA(**devices.aqueduct.ohsa.constants.BASE)
        dev.SCIP = devices.aqueduct.scip.obj.SCIP(**devices.aqueduct.scip.constants.BASE)

        return dev


class TrailingRates(object):
    """
    Class used to format trailing rate-of-change values for the
    balances and pump rates.
    """
    R1_ml_min: Union[float, None]
    W1_ml_min: Union[float, None]
    R2_ml_min: Union[float, None]
    W2_ml_min: Union[float, None]
    R3_ml_min: Union[float, None]
    W3_ml_min: Union[float, None]

    def __init__(self, R1_ml_min: float, W1_ml_min: float, R2_ml_min: float,
                 W2_ml_min: float, R3_ml_min: float, W3_ml_min: float):
        """

        :param R1_ml_min:
        :param W1_ml_min:
        :param R2_ml_min:
        :param W2_ml_min:
        :param R3_ml_min:
        :param W3_ml_min:
        """
        self.R1_ml_min = R1_ml_min
        self.W1_ml_min = W1_ml_min
        self.R2_ml_min = R2_ml_min
        self.W2_ml_min = W2_ml_min
        self.R3_ml_min = R3_ml_min
        self.W3_ml_min = W3_ml_min

    def print(self):
        print("W1: {} mL/min, R1: {} mL/min, W2: {} mL/min, R2: {} mL/min, W3: {} mL/min, R3: {} mL/min".format(
            local.lib.tff.helpers.format_float(self.W1_ml_min, 3),
            local.lib.tff.helpers.format_float(self.R1_ml_min, 2),
            local.lib.tff.helpers.format_float(self.W2_ml_min, 3),
            local.lib.tff.helpers.format_float(self.R2_ml_min, 2),
            local.lib.tff.helpers.format_float(self.W3_ml_min, 3),
            local.lib.tff.helpers.format_float(self.R3_ml_min, 2),
        ))


class DataCacheItem(object):
    """
    A class to structure cached data. Mirrors the structure of the
    Data class.
    """
    P1: Union[float, None] = None  # transducer 1 pressure reading, psi
    P2: Union[float, None] = None  # transducer 2 pressure reading, psi
    P3: Union[float, None] = None  # transducer 3 pressure reading, psi
    W1: Union[float, None] = None  # scale 1 weight, grams
    W2: Union[float, None] = None  # scale 2 weight, grams
    W3: Union[float, None] = None  # scale 3 weight, grams
    R1: Union[float, None] = None  # PUMP1 flowrate, mL/min
    R2: Union[float, None] = None  # PUMP2 flowrate, mL/min
    R3: Union[float, None] = None  # PUMP3 flowrate, mL/min
    PV: Union[float, None] = None  # pinch valve percent open, 1. == fully open, 0. == fully closed
    timestamp: Union[float, None] = None  # timestamp of last update

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


class DataCache(object):
    """
    A Class to store cached data.
    """
    # a cache of the the previous data objects, should be cleared after
    # ramps to begin calculating from steady state
    # newest value last
    _cache: List[DataCacheItem] = []

    # number of items to keep in _cache list
    _length: int = 20

    # the time that the last value was added to the Cache
    _timestamp: float = None

    # the time when the next item should be added to the list
    _scheduled_time: float = None

    # the period in seconds of addition to the list
    _interval_s: float = 5.

    # ref to Devices
    _devices: Devices = None

    def __init__(self, devices_obj: Devices):
        self._devices = devices_obj

    # enclose the Data close in quotes
    # necessary because the Data class is declared after this point
    # in the code
    def cache(self, data: "Data") -> None:
        """
        Pass the Data class object to cache pressures, rates, weights, and PV position
        at a point in time.

        :param data: Data
        :return: None
        """

        # if the current time is less than the schedules time to cache the data,
        # add the data
        if self._scheduled_time is None or self._scheduled_time < data.timestamp:
            item = DataCacheItem(**data.__dict__)
            # convert the timestamp to a float
            item.timestamp = data.timestamp

            # append the latest Item to the cache's list
            self._cache.append(item)

            # trim cache length if it exceeds the set length
            self._cache = self._cache[-1 * self._length:]

            # schedule the next recording time
            self._scheduled_time = self._interval_s + data.timestamp

    def clear_cache(self):
        self._cache = []

    def calc_trailing_accumulation_rates(self) -> Union[TrailingRates, None]:
        """
        Calculate the trailing accumulation rates on the balances.

        Returns None in case of calculation error.

        Returns a tuple of format:

            (dBALANCE1/dt, <PUMP1 rate>, dBALANCE2/dt, <PUMP2 rate>, dBALANCE3/dt, <PUMP3 rate>)

        Units are:

            (mL/min, mL/min, ...)

        :return:
        """

        try:

            balance_accumulation_list_g_min = [[], [], []]
            pump_nominal_rate_list_ml_min = [[], [], []]

            balance_accumulation_mean_g_min = [0, 0, 0]
            pump_nominal_rate_mean_ml_min = [0, 0, 0]

            counts = 0

            delta_t_interval_s = 0
            delta_t_interval_tolerance_s = 1

            if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):
                enum_keys = (('W1', 'R1'), ('W2', 'R2'), ('W3', 'R3'))
            else:
                # have to use R3 in lieu of R2 when PUMP2 is absent
                enum_keys = (('W1', 'R1'), ('W2', 'R3'), ('W3', 'R3'))

            # loop through the cache in reverse
            for i in range(1, len(self._cache) - 1):

                # calculate the time interval between the cache timestamps
                _dt = self._cache[-i].timestamp - self._cache[-(i + 1)].timestamp

                # if we're on loop iteration greater than 1
                if i > 1:
                    # check for aperiodicity in logging interval, break if the interval is outside the last interval
                    # +/- delta_t_interval_tolerance_s
                    if not (delta_t_interval_s - delta_t_interval_tolerance_s < _dt <
                            delta_t_interval_s + delta_t_interval_tolerance_s):
                        break

                # update the interval
                delta_t_interval_s = _dt

                for jj, k in enumerate(enum_keys):
                    # calculate the rate of change in mL/min on the balances
                    balance_delta_mass_g_delta_t_s = (
                            (getattr(self._cache[-i], k[0]) - getattr(self._cache[-(i + 1)], k[0])) / _dt
                    )

                    # multiply by 60 to convert to g/min
                    balance_accumulation_list_g_min[jj].append(balance_delta_mass_g_delta_t_s * 60.)

                    pump_nominal_rate_ml_min = (getattr(self._cache[-i], k[1]) + getattr(self._cache[-(i + 1)],
                                                                                         k[1])) / 2.

                    pump_nominal_rate_list_ml_min[jj].append(pump_nominal_rate_ml_min)

                counts += 1

            # remove outliers from the the balance_accumulation_list_g_min
            for i, rate_list in enumerate(balance_accumulation_list_g_min):
                rate_sum = sum(rate_list)
                rate_mean = rate_sum / len(rate_list)
                # threshold deviation for determining an outlier
                threshold_ml_min = 5
                good_rates = [r for r in rate_list if (rate_mean - threshold_ml_min < r < rate_mean + threshold_ml_min)]
                # set the mean with the good values
                balance_accumulation_mean_g_min[i] = sum(good_rates) / len(good_rates)

            # remove outliers from the the pump_nominal_rate_list_ml_min
            for i, rate_list in enumerate(pump_nominal_rate_list_ml_min):
                rate_sum = sum(rate_list)
                rate_mean = rate_sum / len(rate_list)
                # threshold deviation for determining an outlier
                threshold_ml_min = 5
                good_rates = [r for r in rate_list if (rate_mean - threshold_ml_min < r < rate_mean + threshold_ml_min)]
                # set the mean with the good values
                pump_nominal_rate_mean_ml_min[i] = sum(good_rates) / len(good_rates)

            if counts > 0:
                if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):
                    R2_ml_min = round(pump_nominal_rate_mean_ml_min[1], 4)
                else:
                    R2_ml_min = None

                rates = TrailingRates(
                    W1_ml_min=round(balance_accumulation_mean_g_min[0], 4),
                    R1_ml_min=round(pump_nominal_rate_mean_ml_min[0], 4),
                    W2_ml_min=round(balance_accumulation_mean_g_min[1], 4),
                    R2_ml_min=R2_ml_min,
                    W3_ml_min=round(balance_accumulation_mean_g_min[2], 4),
                    R3_ml_min=round(pump_nominal_rate_mean_ml_min[2], 4),
                )

                return rates

            return None

        except BaseException as e:
            # ***UPDATE 1/30/2021: remove printing of zero division errors which
            # occurs on the first calculation of the trailing rates
            if not isinstance(e, ZeroDivisionError):
                print("Trailing calc exception: {}".format(e))
            return None


class Data(object):
    """
    Class to help with logging and updating data for the
    TFF setup.
    """
    P1: Union[float, None] = None  # transducer 1 pressure reading, psi
    P2: Union[float, None] = None  # transducer 2 pressure reading, psi
    P3: Union[float, None] = None  # transducer 3 pressure reading, psi
    W1: Union[float, None] = None  # scale 1 weight, grams
    W2: Union[float, None] = None  # scale 2 weight, grams
    W3: Union[float, None] = None  # scale 3 weight, grams
    R1: Union[float, None] = None  # PUMP1 flowrate, mL/min
    R2: Union[float, None] = None  # PUMP2 flowrate, mL/min
    R3: Union[float, None] = None  # PUMP3 flowrate, mL/min
    PV: Union[float, None] = None  # pinch valve percent open, 1. == fully open, 0. == fully closed
    timestamp: Union[float, None] = None  # timestamp of last update
    log_timestamp: Union[float, None] = None  # timestamp of last write to log file
    _logging_interval_s: Union[int, float] = 5  # interval in seconds between writes to log file

    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process = None  # pointer to Process object
    _model = None  # pointer to Model object

    # V 1.01 updates to allow simulating volume accumulation
    _cache: DataCache = None

    # errors to simulate mismatch between nominal flow rates and
    # measured values
    _scale1_sim_error_pct = 0.0025
    _scale2_sim_error_pct = -0.0032
    _scale3_sim_error_pct = 0.018

    _extrapolation_timestamp: float = None

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

        self._cache: DataCache = DataCache(self._devices)

        self.init_sim_values()

    def update_data(
            self,
            retries: int = 5,
            debug: bool = False,
            pause_on_error: bool = False
    ) -> None:
        """
        Method to update the global data dictionary.

        Uses the specific Device Object methods to get the
        data from memory.

        :param pause_on_error: bool, if True, will pause the recipe if there is an error with a
            weight reading after the max retries have been attempted
        :param retries: number of times to retry update_data if there is an error with a balance reading
        :param debug: bool, if True will print out error info
        :return:
        """
        pressures = self._devices.SCIP.get_all_pressures()
        weights = self._devices.OHSA.get_all_weights()
        self.P1 = pressures[TXDCR1_INDEX]
        self.P2 = pressures[TXDCR2_INDEX]
        self.P3 = pressures[TXDCR3_INDEX]
        self.W1 = weights[SCALE1_INDEX]
        self.W2 = weights[SCALE2_INDEX]
        self.W3 = weights[SCALE3_INDEX]

        if any(isinstance(w, type(None)) for w in (self.W1, self.W2, self.W3)):
            if retries == 0:

                if pause_on_error is True:
                    # prompt operator to place empty vessel on feed scale
                    self._aqueduct.prompt(
                        message="Error updating balance weight reading. Ensure all balances are connected."
                                " Press <b>continue</b> to resume recipe.",
                        pause_recipe=True
                    )
                return

            else:
                # add a little time delay before refreshing
                if debug is True:
                    print(f"Invalid weight reading...retries left {retries - 1}")
                time.sleep(0.5)
                self.update_data(retries=retries - 1)

        self.R1 = self._devices.PUMP1.get_flow_rate()
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):
            self.R2 = self._devices.PUMP2.get_flow_rate()
        self.R3 = self._devices.PUMP3.get_flow_rate()
        self.PV = self._devices.PV.position()
        self.timestamp = time.time()

        if not self._is_lab_mode:
            balance_rocs = [0, 0, 0, 0]
            # if PUMP2 is present, use this to drive sim value balance
            if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):
                balance_rocs[SCALE2_INDEX] = (-1 * self.R2) * (1. + self._scale2_sim_error_pct)
            # else, use PUMP3 to drive it
            else:
                balance_rocs[SCALE2_INDEX] = (-1 * self.R3) * (1. + self._scale2_sim_error_pct)
            balance_rocs[SCALE3_INDEX] = self.R3 * (1. + self._scale3_sim_error_pct)
            balance_rocs[SCALE1_INDEX] = -1 * (balance_rocs[SCALE2_INDEX] + balance_rocs[SCALE3_INDEX])
            # mL/min to mL/s
            balance_rocs = [r / 60. for r in balance_rocs]
            self._devices.OHSA.set_sim_rates_of_change(balance_rocs)
            self._model.calc_pressures()

        # save the data to the cache
        self._cache.cache(data=self)

    def log_data(self) -> None:
        """
        Method to log:

            P1, P2, P3 (in PSI),
            W1, W2, W3 (in grams)
            R1, R2, R3 (in mL/min)
            PV (in pct_open)

        at a given time.

        :return: None
        """
        self._aqueduct.log(
            "P1: {0}, "
            "P2: {1}, "
            "P3: {2}, "
            "W1: {3}, "
            "W2: {4}, "
            "W3: {5}, "
            "R1: {6}, "
            "R2: {7}, "
            "R3: {8}, "
            "PV: {9}".format(
                local.lib.tff.helpers.format_float(self.P1, 3),
                local.lib.tff.helpers.format_float(self.P2, 3),
                local.lib.tff.helpers.format_float(self.P3, 3),
                local.lib.tff.helpers.format_float(self.W1, 3),
                local.lib.tff.helpers.format_float(self.W2, 3),
                local.lib.tff.helpers.format_float(self.W3, 3),
                local.lib.tff.helpers.format_float(self.R1, 3),
                local.lib.tff.helpers.format_float(self.R2, 3),
                local.lib.tff.helpers.format_float(self.R3, 3),
                local.lib.tff.helpers.format_float(self.PV, 4)
            ))

    def as_dict(self) -> dict:
        """
        Converts the DataPoint to a dictionary for easy JSON serialization
        and transfer over HTTP.

        :return: dictionary
        """
        keys = [
            ('P1', 3),
            ('P2', 3),
            ('P3', 3),
            ('W1', 3),
            ('W2', 3),
            ('W3', 3),
            ('R1', 3),
            ('R2', 3),
            ('R3', 3),
            ('PV', 4),
            ('timestamp',),
        ]
        d = {}
        for k in keys:
            if k[0] == 'timestamp':
                d.update({k[0]: getattr(self, k[0], None).strftime('%Y-%m-%dT%H:%M:%S.%f')})
            else:
                d.update({k[0]: local.lib.tff.helpers.format_float(getattr(self, k[0], None), k[1])})
        return d

    def log_data_at_interval(self, interval_s: float = None) -> None:
        """
        Method to log the data dictionary at a specified interval in seconds.

        Checks to see whether the interval between the
        last log timestamp and the current time exceeds the _log_interval_s
        attribute, saves the data if it does.

        :param interval_s:
        :return:
        """
        if not interval_s:
            interval_s = self._logging_interval_s

        t_now = time.time()
        if self.log_timestamp:
            if t_now > (self.log_timestamp + interval_s):
                self.log_data()
                self.log_timestamp = t_now
        else:
            self.log_data()
            self.log_timestamp = t_now

    def extrapolate_balance_values(self) -> tuple:
        """
        Extrapolate the new value of the balances based on the nominal flow rates.

        :return:
        """
        try:
            if self._extrapolation_timestamp is not None:
                scale3_delta_m_g = self.R3 / 60. * (self.timestamp - self._extrapolation_timestamp)

                scale3_mass_g = self.W3 + scale3_delta_m_g * (1. + self._scale3_sim_error_pct)

                # BUFFER pump, debit this value
                # if PUMP2 is present, drive with PUMP2
                if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):
                    scale2_delta_m_g = self.R2 / 60. * (self.timestamp - self._extrapolation_timestamp)
                    scale2_mass_g = self.W2 - scale2_delta_m_g * (1. + self._scale2_sim_error_pct)

                else:
                    scale2_delta_m_g = self.R3 / 60. * (self.timestamp - self._extrapolation_timestamp)
                    scale2_mass_g = self.W2 - scale2_delta_m_g * (1. + self._scale2_sim_error_pct)

                # FEED pump, adding from BUFFER, debiting from PERMEATE
                scale1_mass_g = self.W1 + (scale2_delta_m_g - scale3_delta_m_g) * (1. + self._scale1_sim_error_pct)

                self._devices.OHSA.set_sim_weights({
                    SCALE1_INDEX: scale1_mass_g,
                    SCALE2_INDEX: scale2_mass_g,
                    SCALE3_INDEX: scale3_mass_g
                })

                self._extrapolation_timestamp = self.timestamp

                return scale1_mass_g, scale2_mass_g, scale3_mass_g

            else:
                self._extrapolation_timestamp = self.timestamp

        except BaseException as e:
            print("Extrapolation error: {}".format(e))

    def init_sim_values(self):

        if not self._is_lab_mode:
            if isinstance(self._devices.OHSA, devices.aqueduct.ohsa.obj.OHSA):
                self._devices.OHSA.set_sim_noise(0)
                self._devices.OHSA.set_sim_weights(values=(0, 0, 0, 0))

            if isinstance(self._devices.SCIP, devices.aqueduct.scip.obj.SCIP):
                self._devices.SCIP.set_sim_pressures(values=((5., 5., 5.,) + 9 * (0,)))
                self._devices.SCIP.set_sim_noise(values=((0.1, 0.1, 0.1,) + 9 * (0,)))


class Setpoints(object):
    """
    Class that will contain all Aqueduct Setpoints
    for the TFF setup.

    Setpoints will display as User Params on the
    Recipe Editor screen and can be edited
    by a user.

    """
    pinch_valve_control_active: Setpoint = None
    P3_target_pressure: Setpoint = None

    _aqueduct: Aqueduct = None

    def __init__(self, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param aqueduct_obj:
        """
        self._aqueduct = aqueduct_obj

        self.pinch_valve_control_active = self._aqueduct.setpoint(
            "pinch_valve_control_active",
            False,
            bool.__name__
        )

        self.P3_target_pressure = self._aqueduct.setpoint(
            "P3_target_pressure",
            5,
            float.__name__
        )


"""
ALARM & WATCHDOG CLASSES
"""


class Alarm(object):
    """
    Class to assist with checking on alarm conditions and
    responding appropriately.

    """
    active: bool = False
    _data: Data = None  # pointer to Data object
    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process = None  # pointer to Process object

    def __init__(self, data_obj: Data, devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: Data = data_obj
        self._devices: Devices = devices_obj
        self._aqueduct: Aqueduct = aqueduct_obj
        return

    def check(self):
        """
        Method common to all Alarms that

        1) checks to see if the active flag is set
        2) if active, check the condition method to see whether there is an alarm condition
        3) if there is an alarm condition, handle the alarm (e-stop, etc)
        4) once the alarm has been handled, a method to restart operation

        :return:
        """
        if self.active:
            if self.condition():
                # this should pause the recipe
                self.handle()
                # this should restart the recipe
                self.restart()

    def condition(self) -> bool:
        """
        Method that checks a condition like:

        P3 < 0.3 psi

        and returns True or False
        :return: True if alarm condition is met, False if no alarm condition
        """
        return False

    def handle(self) -> None:
        """
        Method to handle the alarm in case the alarm condition is met.

        Ex.
            e-stop
            throw user prompt
            log data while waiting

        :return:
        """
        return None

    def restart(self) -> None:
        """
        Method to restart operation after the alarm has been handled.

        Ex.
            ramp all pumps back up to previous rates at specified interval

        :return:
        """
        return None

    def on(self) -> None:
        """
        Turns an alarm on.

        :return:
        """
        self.active = True

    def off(self) -> None:
        """
        Turns an alarm off.

        :return:
        """
        self.active = False

    def get_target_mass(self) -> Union[float, int, None]:
        """
        Returns the Scale 3 target mass for the current phase of the process.
        :return:
        """
        if self._process.current_phase == Process.INITIAL_CONC_PHASE:
            return self._process.init_conc_target_mass_g
        elif self._process.current_phase == Process.DIAFILT_PHASE:
            return self._process.diafilt_target_mass_g
        elif self._process.current_phase == Process.FINAL_CONC_PHASE:
            return self._process.final_conc_target_mass_g
        return None


class OverPressureAlarm(Alarm):
    """
    Condition: any P1/P2/P3 > 35 psig

    Handle:

        E-stop, no delay
        Show user prompt with info
        log data while prompt has not been dismissed

    Restart:

        ramp pump 1 from 50% of cached rate back to 100% of cached rate
        ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

    """

    max_pressure_psi: float = 35.

    cached_pump1_rate_ml_min: float = 0.
    cached_pump2_rate_ml_min: float = 0.
    cached_pump3_rate_ml_min: float = 0.

    _pump_1_rate_change_interval_s: float = 30
    _pump_1_rate_change_increment_ml_min: float = 2
    _pump_1_rate_change_pct_inc: float = 0.2
    _pump_1_rate_change_timeout_min: float = 30

    _pumps_2_3_ramp_interval_s: float = 30
    _pumps_2_3_ramp_number_rate_changes: int = 6
    _pumps_2_3_ramp_timeout_min: float = 60

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If P1 > max_pressure_psi || P2 > max_pressure_psi || P3 > max_pressure_psi, raise alarm

        :return:
        """

        if (self._data.P1 > self.max_pressure_psi or
                self._data.P2 > self.max_pressure_psi or
                self._data.P3 > self.max_pressure_psi):
            return True
        else:
            return False

    def handle(self):
        """
        Handle an Overpressure Alarm:

            1) cache all pump rates
            2) stop all pumps
            3) Show user prompt with Alarm info
            4) While prompt has not been dismissed, wait in a loop and log data

        :return:
        """

        print("***Overpressure alarm raised! Stopping all pumps. Dismiss prompt to continue.***")
        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Overpressure! Press <b>continue</b> to resume operation. 
                        Upon resume: 
                            1) Pump 1 will ramp back to 100% previous rate
                            2) Pumps 2 and 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )
        else:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Overpressure! Press <b>continue</b> to resume operation. 
                Upon resume: 
                    1) Pump 1 will ramp back to 100% previous rate
                    2) Pump 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )

        # we will be locked in this loop until the prompt is dismissed
        while prompt:
            self._data.update_data()
            self._data.log_data_at_interval(10)
            time.sleep(2)

    def restart(self):
        """
        Restart the recipe by:

            1) ramp pump 1 from 50% of cached rate back to 90% of cached rate
            2) ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

        :return:
        """

        local.lib.tff.methods.pump_ramp(
            interval_s=1,
            pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.cached_pump1_rate_ml_min / 2,
            end_flowrate_ml_min=self.cached_pump1_rate_ml_min * 0.9,
            rate_change_interval_s=self._pump_1_rate_change_interval_s,
            rate_change_pct=self._pump_1_rate_change_pct_inc,
            timeout_min=self._pump_1_rate_change_timeout_min,
            adjust_pinch_valve=False,
            devices_obj=self._devices, data=self._data)

        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.cached_pump2_rate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.cached_pump2_rate_ml_min,
            pump3_start_flowrate_ml_min=self.cached_pump3_rate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.cached_pump3_rate_ml_min,
            rate_change_interval_s=self._pumps_2_3_ramp_interval_s,
            number_rate_changes=self._pumps_2_3_ramp_number_rate_changes,
            timeout_min=self._pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=False,
            scale3_target_mass_g=self.get_target_mass(),
            devices_obj=self._devices, data=self._data
        )


class LowP3PressureAlarm(Alarm):
    """
    Condition: if P3 < 0.3 psig && P3 >= -3.0

    Handle: Stop PUMP2/PUMP3

    Restart:

        decrease R2 and R3 targets by 10%, then restart pumps 2/3 from 50% speed
        time between rate increases for R2 and R3 after restart

    """

    # minimum P3 pressure, pressures below this will trigger alarm
    min_p3_pressure_psi: float = 0.3
    vacuum_pressure_psi: float = -3.0

    cached_pump1_rate_ml_min: float = 0.
    cached_pump2_rate_ml_min: float = 0.
    cached_pump3_rate_ml_min: float = 0.

    # parameters for ramp of Pumps 2 and 3 after restart
    _pumps_2_3_ramp_interval_s: float = 30
    _pumps_2_3_ramp_number_rate_changes: int = 6
    _pumps_2_3_ramp_timeout_min: float = 60

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If P3 < min_pressure_psi and P3 >= vacuum_pressure_psi, raise alarm

        :return:
        """

        if self.min_p3_pressure_psi > self._data.P3 >= self.vacuum_pressure_psi:
            return True
        else:
            return False

    def handle(self):
        """
        Handle an Low P3 Pressure Alarm:

            1) cache all pump rates
            2) stop pumps 2 (if present) and 3 and wait 5 sec
            2) ramp pumps 2 (if present) and 3 from 50% of cached rate back to 90% of cached rate

        :return:
        """

        print("***Underpressure P3 alarm raised!***")
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            print("Stopping Pumps 2 and 3.")
        else:
            print("Stopping Pump 3.")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        # small time delay
        time.sleep(5)

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            print("Ramping Pumps 2 and 3 to 90% of previous rates.")
        else:
            print("Ramping Pump 3 to 90% of previous rates.")

        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.cached_pump2_rate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.cached_pump2_rate_ml_min * 0.9,
            pump3_start_flowrate_ml_min=self.cached_pump3_rate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.cached_pump3_rate_ml_min * 0.9,
            rate_change_interval_s=self._pumps_2_3_ramp_interval_s,
            number_rate_changes=self._pumps_2_3_ramp_number_rate_changes,
            timeout_min=self._pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=False,
            scale3_target_mass_g=self.get_target_mass(),
            devices_obj=self._devices, data=self._data
        )

    def restart(self):
        """
        No action.

        :return:
        """


class VacuumConditionAlarm(Alarm):
    """
    Condition: any P1/P2/P3 < -3.0 psig

    Handle:

        E-stop, no delay
        prompt to warn user

    Restart:

        ramp pump 1 from 50% of cached rate back to 100% of cached rate
        ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

    """

    # minimum pressure, pressures below this will trigger alarm
    vacuum_pressure_psi: float = -3.0

    cached_pump1_rate_ml_min: float = 0.
    cached_pump2_rate_ml_min: float = 0.
    cached_pump3_rate_ml_min: float = 0.

    # parameters for ramp of Pump 1 after restart
    _pump_1_rate_change_interval_s: float = 30
    _pump_1_rate_change_increment_ml_min: float = 2
    _pump_1_rate_change_pct_inc: float = 0.2
    _pump_1_rate_change_timeout_min: float = 30

    # parameters for ramp of Pumps 2 and 3 after restart
    _pumps_2_3_ramp_interval_s: float = 30
    _pumps_2_3_ramp_number_rate_changes: int = 6
    _pumps_2_3_ramp_timeout_min: float = 60

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If P1 < vacuum_pressure_psi || P2 < vacuum_pressure_psi || P3 < vacuum_pressure_psi, raise alarm

        :return:
        """

        if (self._data.P1 < self.vacuum_pressure_psi or
                self._data.P2 < self.vacuum_pressure_psi or
                self._data.P3 < self.vacuum_pressure_psi):
            return True
        else:
            return False

    def handle(self):
        """
        Handle a Vacuum Condition Alarm:

            1) cache all pump rates
            2) stop all pumps
            3) Show user prompt with Alarm info
            4) While prompt has not been dismissed, wait in a loop and log data

        :return:
        """

        print("***Vacuum Condition Alarm raised! Stopping all pumps. Dismiss prompt to continue.***")
        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Vacuum Condition! Ensure proper vessels contain liquid and 
                feed tubes are submerged. Press <b>continue</b> to resume operation. 
                Upon resume: 
                    1) Pump 1 will ramp back to 100% previous rate
                    2) Pumps 2 and 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )
        else:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Vacuum Condition! Ensure proper vessels contain liquid and 
                            feed tubes are submerged. Press <b>continue</b> to resume operation. 
                            Upon resume: 
                                1) Pump 1 will ramp back to 100% previous rate
                                2) Pump 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )

        # we will be locked in this loop until the prompt is dismissed
        while prompt:
            self._data.update_data()
            self._data.log_data_at_interval(10)
            time.sleep(2)

    def restart(self):
        """
        Restart the recipe by:

            1) ramp pump 1 from 50% of cached rate back to 100% of cached rate
            2) ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

        :return:
        """

        local.lib.tff.methods.pump_ramp(
            interval_s=1,
            pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.cached_pump1_rate_ml_min / 2,
            end_flowrate_ml_min=self.cached_pump1_rate_ml_min,
            rate_change_interval_s=self._pump_1_rate_change_interval_s,
            rate_change_pct=self._pump_1_rate_change_pct_inc,
            timeout_min=self._pump_1_rate_change_timeout_min,
            adjust_pinch_valve=False,
            devices_obj=self._devices, data=self._data)

        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.cached_pump2_rate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.cached_pump2_rate_ml_min,
            pump3_start_flowrate_ml_min=self.cached_pump3_rate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.cached_pump3_rate_ml_min,
            rate_change_interval_s=self._pumps_2_3_ramp_interval_s,
            number_rate_changes=self._pumps_2_3_ramp_number_rate_changes,
            timeout_min=self._pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=False,
            scale3_target_mass_g=self.get_target_mass(),
            devices_obj=self._devices, data=self._data
        )


class BufferVesselEmptyAlarm(Alarm):
    """
    Condition: if W2 < min_buffer_liquid_mass_g

    Handle: Stop R2/R3

    Restart: TODO

        restart pumps 2/3 from 50% speed
        time between rate increases for R2 and R3 after restart

    """

    min_buffer_liquid_mass_g: float = 5.

    cached_pump1_rate_ml_min: float = 0.
    cached_pump2_rate_ml_min: float = 0.
    cached_pump3_rate_ml_min: float = 0.

    # parameters for ramp of Pumps 2 and 3 after restart
    _pumps_2_3_ramp_interval_s: float = 30
    _pumps_2_3_ramp_number_rate_changes: int = 6
    _pumps_2_3_ramp_timeout_min: float = 60

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If W2 < min_buffer_liquid_mass_g, raise alarm

        :return:
        """

        if isinstance(self._data.W2, float) and self._data.W2 < self.min_buffer_liquid_mass_g:
            return True
        else:
            return False

    def handle(self):
        """
        Handle an Overpressure Alarm:

            1) cache all pump rates
            2) stop pumps 2 and 3
            3) throw user prompt with error message
            4) log data while waiting for operator to dismiss message

        :return:
        """
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            print("""***Low Buffer Vessel Mass alarm raised! 
            Stopping Pumps 2 and 3.***""")
        else:
            print("""***Low Buffer Vessel Mass alarm raised! 
            Stopping Pump 3.***""")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Low Buffer Vessel Mass! Refill vessel. Press <b>continue</b> to resume operation. 
                        Upon resume: 
                            1) Pumps 2 and 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )
        else:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Low Buffer Vessel Mass! Refill vessel. Press <b>continue</b> to resume operation. 
                        Upon resume: 
                            1) Pump 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )

        # we will be locked in this loop until the prompt is dismissed
        while prompt:
            self._data.update_data()
            self._data.log_data_at_interval(10)
            time.sleep(2)

    def restart(self):
        """
        Restart the recipe by:

            1) ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

        :return:
        """

        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.cached_pump2_rate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.cached_pump2_rate_ml_min,
            pump3_start_flowrate_ml_min=self.cached_pump3_rate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.cached_pump3_rate_ml_min,
            rate_change_interval_s=self._pumps_2_3_ramp_interval_s,
            number_rate_changes=self._pumps_2_3_ramp_number_rate_changes,
            timeout_min=self._pumps_2_3_ramp_timeout_min, adjust_pinch_valve=False,
            scale3_target_mass_g=self.get_target_mass(),
            devices_obj=self._devices, data=self._data
        )


class RetentateVesselLowAlarm(Alarm):
    """
    Condition: if W1 < end_expected_retentate_mass_g - threshold_g g

    Handle: Stop R1/R2/R3

    Restart: 

        restart pump from 50% speed
        ramp to 100% speed
        restart pumps 2/3 from 50% speed
        time between rate increases for R2 and R3 after restart

    """

    end_expected_retentate_mass_g: float = None
    threshold_g: float = 5

    cached_pump1_rate_ml_min: float = 0.
    cached_pump2_rate_ml_min: float = 0.
    cached_pump3_rate_ml_min: float = 0.

    # parameters for ramp of Pump 1 after restart
    _pump_1_rate_change_interval_s: float = 30
    _pump_1_rate_change_increment_ml_min: float = 2
    _pump_1_rate_change_pct_inc: float = 0.2
    _pump_1_rate_change_timeout_min: float = 30

    # parameters for ramp of Pumps 2 and 3 after restart
    _pumps_2_3_ramp_interval_s: float = 30
    _pumps_2_3_ramp_number_rate_changes: int = 6
    _pumps_2_3_ramp_timeout_min: float = 60

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If W2 < min_buffer_liquid_mass_g, raise alarm

        :return:
        """

        if isinstance(self._data.W2, float) and 2 < self.end_expected_retentate_mass_g - self.threshold_g:
            return True
        else:
            return False

    def handle(self):
        """
        Handle a Retentate Vessel Low Alarm:

            1) cache all pump rates
            2) stop all pumps
            3) Show user prompt with Alarm info
            4) While prompt has not been dismissed, wait in a loop and log data

        :return:
        """
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            print("""***Retentate Vessel Mass alarm raised! 
            Stopping Pumps 1, 2, and 3.***""")

        else:
            print("""***Retentate Vessel Mass alarm raised! 
            Stopping Pumps 1 and 3.***""")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self._process.two_pump_config is False:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Low Retentate Vessel Mass! Press <b>continue</b> to resume operation. 
                        Upon resume: 
                            1) Pump 1 will ramp back to 100% of previous rate
                            2) Pumps 2 and 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )
        else:
            prompt = self._aqueduct.prompt(
                message="""ALARM: Low Retentate Vessel Mass! Press <b>continue</b> to resume operation. 
                                    Upon resume: 
                                        1) Pump 1 will ramp back to 100% of previous rate
                                        2) Pump 3 will ramp back to 100% of previous rate""",
                pause_recipe=False,
            )

        # we will be locked in this loop until the prompt is dismissed
        while prompt:
            self._data.update_data()
            self._data.log_data_at_interval(10)
            time.sleep(2)

    def restart(self):
        """
        Restart the recipe by:

            1) ramp pump 1 from 50% of cached rate back to 100% of cached rate
            2) ramp pumps 2 (if present) and 3 from 50% of cached rate back to 100% of cached rate

        :return:
        """

        local.lib.tff.methods.pump_ramp(
            interval_s=1,
            pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.cached_pump1_rate_ml_min / 2,
            end_flowrate_ml_min=self.cached_pump1_rate_ml_min,
            rate_change_interval_s=self._pump_1_rate_change_interval_s,
            rate_change_pct=self._pump_1_rate_change_pct_inc,
            timeout_min=self._pump_1_rate_change_timeout_min,
            adjust_pinch_valve=False,
            devices_obj=self._devices,
            data=self._data)

        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.cached_pump2_rate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.cached_pump2_rate_ml_min,
            pump3_start_flowrate_ml_min=self.cached_pump3_rate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.cached_pump3_rate_ml_min,
            rate_change_interval_s=self._pumps_2_3_ramp_interval_s,
            number_rate_changes=self._pumps_2_3_ramp_number_rate_changes,
            timeout_min=self._pumps_2_3_ramp_timeout_min, adjust_pinch_valve=False,
            scale3_target_mass_g=self.get_target_mass(),
            devices_obj=self._devices, data=self._data
        )


class VolumeAccumulationAlarm(Alarm):
    """
    Condition:

        1) if mL/min accum rate of Scale 3 out of tolerance with
        set R3, adjust R3

        2) if mL/min accum rate of Scale 2 out of tolerance with
        set R2, adjust R2

    Handle: Adjust R2 and/or R3 according to logic below

    Restart: None

    """

    # interval at which to check rate deviations
    check_interval_s: float = 30
    last_time_check: float = None

    # maximum dW2/dt deviation from pump 2 setpoint, in mL/min, before throwing
    # an error and stopping the pumps
    pump2_max_deviation_ml_min = 10

    # maximum pump2 adjustment, in pct
    max_pump2_adjustment_pct: float = 0.05

    # floor pump2 adjustment, in mL/min
    # if the maximum pump2 adjustment is less than this value,
    # this value will take precedence, ie. if max_pump2_adjustment_pct = 0.05 results
    # in a max change of 0.2 mL/min, this value will override it if it's greater
    floor_pump2_adjustment_ml_min: float = 2

    # MODE 1 params

    # maximum allowable rate of change on scale 1 (in mL/min)
    # before adjusting pump
    max_scale1_ml_min_change: float = 0.1

    # MODE 2 params

    # target mass on scale 1
    scale1_target_ml: Union[float, None] = None

    # maximum deviation (in mL) on scale 1 from
    # scale1_target_ml before adjusting pump 2 rate
    max_scale1_ml_dev: float = 0.3

    # target time to hit mass setpoint from pump2 rate adjustment
    scale1_target_time_min: float = 1

    # mode
    # 1 == adjust buffer pump to force delta_m/delta_t on feed balance to 0
    # 2 == adjust buffer pump to force m on feed balance to setpoint at specified rate
    mode = 2

    def __init__(self, data_obj, devices_obj, aqueduct_obj):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        super().__init__(data_obj, devices_obj, aqueduct_obj)

    def condition(self) -> bool:
        """
        If time > last_time + interval

        :return:
        """
        if self.last_time_check is None:
            self.last_time_check = time.time()

        # if the scheduled time to check is less than the current time, check
        # the trailing rates
        elif self.last_time_check + self.check_interval_s < time.time():
            return True

        return False

    def handle(self):
        """

        :return:
        """

        # check thresholds, this is wrapped in a Try/Except so it will not
        # cause a run time error
        rates = self._data._cache.calc_trailing_accumulation_rates()

        if isinstance(rates, TrailingRates):
            rates.print()

            # if PUMP2 is present, try to handle the vol. accum
            if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP):

                try:

                    # check maximum deviation
                    self.check_max_deviation(rates)

                    if self.mode == 1:
                        self.handle_mode1(rates)

                    if self.mode == 2:
                        self.handle_mode2(rates)

                except BaseException as e:
                    pass

        self.last_time_check = time.time()

    def restart(self):
        """
        Restart the recipe by:

            1) ramp pump 1 from 50% of cached rate back to 100% of cached rate
            2) ramp pumps 2 and 3 from 50% of cached rate back to 100% of cached rate

        :return:
        """

    def on(self) -> None:
        """
        Turns an alarm on.

        ***UPDATE 1/30/2021 - remove default caching of the `scale1_target_ml`
        param when the alarm is turned on so we can set the target value
        to the mass prior to pump 2 and 3 ramps

        :return:
        """
        self.active = True

    def off(self) -> None:
        """
        Turns an alarm off.

        :return:
        """
        self.active = False
        self.scale1_target_ml = None

    def set_scale1_target_mass(self) -> None:
        """
        ***UPDATE 1/30/2021 - breaks out the storing of the target mass
        value into a separate, callable method

        We'll make sure the value W1 is not None (as could be the case for
        an invalid balance reading, like 'Ok!'), and if it is ok, update the
        data

        Otherwise, loop 5 times to get valid data

        Currently, this method prints a line but can be turned off if it's unwanted.

        :return:
        """
        n = 0
        while n < 5:
            if self._data.W1 is not None:
                print("Setting SCALE1 setpoint volume to: {} mL".format(self._data.W1))
                self.scale1_target_ml = self._data.W1
                return
            time.sleep(1)
            self._data.update_data()
            n += 1

    def check_max_deviation(self, rates: TrailingRates) -> None:
        if abs(abs(rates.W2_ml_min) - abs(rates.R2_ml_min)) > self.pump2_max_deviation_ml_min:
            print("""Deviation between PUMP2 rate: {} mL/min, 
            and buffer removal rate, {} mL/min, 
            exceeds maximum allowable value of {} mL/min.""".format(
                rates.R2_ml_min, rates.W2_ml_min, self.pump2_max_deviation_ml_min)
            )

    def handle_mode1(self, rates: TrailingRates):
        """
        Handler to adjust buffer pump rate to drive delta_m/delta_t on feed balance to 0
        """

        clear_cache = False

        W1_ml_min_bounds = [
            -1 * self.max_scale1_ml_min_change,
            1 * self.max_scale1_ml_min_change,
        ]

        sign = None

        # if the measured mass removal rate is less than the target,
        # increase speed by the % deviation
        if rates.W1_ml_min < W1_ml_min_bounds[0]:
            # we need to increase the rate
            sign = 1

        elif rates.W1_ml_min > W1_ml_min_bounds[1]:
            # we need to reduce the rate
            sign = -1

        if sign is not None:

            pump2_new_rate = (sign * abs(rates.W1_ml_min)) + self._data.R2
            max_adjustment_ml_min = max(self._data.R2 * self.max_pump2_adjustment_pct,
                                        self.floor_pump2_adjustment_ml_min)
            pump2_new_rate = min(pump2_new_rate, self._data.R2 + max_adjustment_ml_min)
            pump2_new_rate = max(pump2_new_rate, self._data.R2 - max_adjustment_ml_min)
            pump2_new_rate = round(pump2_new_rate, 2)

            if pump2_new_rate is not None and pump2_new_rate > 0:
                print("Mode {} control: changing PUMP2 rate to {} mL/min".format(
                    self.mode,
                    local.lib.tff.helpers.format_float(pump2_new_rate, 2)))
                self._devices.PUMP2.change_speed(pump2_new_rate)
                clear_cache = True

        if clear_cache is True:
            self._data._cache.clear_cache()
            self._data._cache._scheduled_time = time.time() + self.check_interval_s

    def handle_mode2(self, rates: TrailingRates):
        """
        Handler to adjust buffer pump rate to drive feed balance mass to setpoint
        in specified amount of time
        """

        clear_cache = False

        W1_ml_bounds = [
            self.scale1_target_ml - self.max_scale1_ml_dev,
            self.scale1_target_ml + self.max_scale1_ml_dev,
        ]

        sign = None

        # if the measured mass is less than the target,
        # increase speed by the % deviation
        if isinstance(self._data.W1, float) and self._data.W1 < W1_ml_bounds[0]:
            # if we're below the tolerance mL bounds, we need to increase the rate of
            # pump 2 to hit the target
            sign = 1

        elif isinstance(self._data.W1, float) and self._data.W1 > W1_ml_bounds[1]:
            # we're above the high end of the tolerance bounds, so we need to reduce the rate
            # of pump 2
            sign = -1

        if sign is not None:
            # set rate change magnitude to hit setpoint at next scheduled
            # check in
            # ***UPDATE 1/30/2021, remove normalization by interval here
            pump2_rate_magnitude_ml_min = (abs(self._data.W1 - self.scale1_target_ml) / self.scale1_target_time_min)
            # ***UPDATE 1/30/2021, account for actual scale_1_rate by subtracting rates.W1_ml_min
            pump2_new_rate = (sign * pump2_rate_magnitude_ml_min) + self._data.R2 - rates.W1_ml_min
            max_adjustment_ml_min = max(self._data.R2 * self.max_pump2_adjustment_pct,
                                        self.floor_pump2_adjustment_ml_min)
            pump2_new_rate = min(pump2_new_rate, self._data.R2 + max_adjustment_ml_min)
            pump2_new_rate = max(pump2_new_rate, self._data.R2 - max_adjustment_ml_min)
            pump2_new_rate = round(pump2_new_rate, 2)

            if pump2_new_rate is not None and pump2_new_rate > 0:
                print("Mode {} control: changing PUMP2 rate to {} mL/min to hit target SCALE1 setpoint of {} mL".format(
                    self.mode,
                    local.lib.tff.helpers.format_float(pump2_new_rate, 2),
                    self.scale1_target_ml
                ))
                self._devices.PUMP2.change_speed(pump2_new_rate)
                clear_cache = True
        else:
            self.handle_mode1(rates)
            clear_cache = True

        if clear_cache is True:
            self._data._cache.clear_cache()
            self._data._cache._scheduled_time = time.time() + self.check_interval_s


class Watchdog(object):
    """
    The Watchdog class will have access to all of the Alarm
    classes.

    """

    over_pressure_alarm: OverPressureAlarm
    low_pressure_alarm: LowP3PressureAlarm
    vacuum_condition_alarm: VacuumConditionAlarm
    low_buffer_vessel_alarm: BufferVesselEmptyAlarm
    low_retentate_vessel_alarm: RetentateVesselLowAlarm
    volume_accumulation_alarm: VolumeAccumulationAlarm

    _devices: Devices
    _aqueduct: Aqueduct
    _data: Data

    def __init__(self, data_obj: Data, devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: Data = data_obj
        self._devices: Devices = devices_obj
        self._aqueduct: Aqueduct = aqueduct_obj

        self.over_pressure_alarm = OverPressureAlarm(self._data, self._devices, self._aqueduct)
        self.low_pressure_alarm = LowP3PressureAlarm(self._data, self._devices, self._aqueduct)
        self.vacuum_condition_alarm = VacuumConditionAlarm(self._data, self._devices, self._aqueduct)
        self.low_buffer_vessel_alarm = BufferVesselEmptyAlarm(self._data, self._devices, self._aqueduct)
        self.low_retentate_vessel_alarm = RetentateVesselLowAlarm(self._data, self._devices, self._aqueduct)
        self.volume_accumulation_alarm = VolumeAccumulationAlarm(self._data, self._devices, self._aqueduct)

    def assign_process_to_alarms(self, process):
        """
        Set the reference to the Process instance for all of the Watchdog's alarms.

        :param process:
        :return:
        """
        for n, m in self.__dict__.items():
            a = getattr(self, n)
            if isinstance(a, Alarm):
                setattr(a, '_process', process)

    def turn_all_alarms_off(self):
        """
        Make all alarms inactive by setting their `active`
        attribute to False.

        :return:
        """

        self.over_pressure_alarm.active = False
        self.low_pressure_alarm.active = False
        self.vacuum_condition_alarm.active = False
        self.low_buffer_vessel_alarm.active = False
        self.low_retentate_vessel_alarm.active = False
        self.volume_accumulation_alarm.active = False

    def check_alarms(self):
        """
        Method to run the `check` method of each Alarm
        type.

        :return:
        """
        try:
            self.over_pressure_alarm.check()
            self.low_pressure_alarm.check()
            self.vacuum_condition_alarm.check()
            self.low_buffer_vessel_alarm.check()
            self.low_retentate_vessel_alarm.check()
            self.volume_accumulation_alarm.check()
        except TypeError:
            pass

    def set_quick_run_params(self):
        """
        Method to set all Member Alarms to
        restart with accelerated ramp intervals

        :return: None
        """

        for n, m in self.__dict__.items():
            a = getattr(self, n)
            if isinstance(a, Alarm):
                for attr in ['_pump_1_rate_change_interval_s', '_pumps_2_3_ramp_interval_s']:
                    if hasattr(a, attr):
                        setattr(a, attr, 5)


"""
PROCESS CLASSES
"""


class Process(object):
    """
    Class to contain process information like
    drug substance, filter area, etc.

    """
    INITIAL_CONC_PHASE = 0  # alias for process being in init conc
    DIAFILT_PHASE = 1  # alias for process being in diafilt phase
    FINAL_CONC_PHASE = 2  # alias for process being in final conc phase

    DEFAULT_DRUG_SUBSTANCE = "test"
    DEFAULT_FILTER_AREA = 50.  # cm^2
    DEFAULT_POLYSACCHARIDE_MASS = 500.  # mg

    DEFAULT_PUMP_1_FLOWRATE = 20.  # mL/min
    DEFAULT_PUMP_2_FLOWRATE = DEFAULT_PUMP_1_FLOWRATE / 2  # mL/min
    DEFAULT_PUMP_3_FLOWRATE = DEFAULT_PUMP_1_FLOWRATE / 2  # mL/min

    DEFAULT_TARGET_P3 = 5.  # psi

    DEFAULT_INIT_TRANSFER_VOL = 50.  # mL

    DEFAULT_INIT_CONC_TARGET_MASS = 100.  # grams
    DEFAULT_INIT_CONC_TIMEOUT_MIN = 360.  # minutes
    DEFAULT_INIT_CONC_TARGET = 10  # g/L
    DEFAULT_INIT_CONC_VOLUME_ML = 100.  # mL

    DEFAULT_DIAFILT_TARGET_MASS = 100.  # grams
    DEFAULT_DIAFILT_TIMEOUT_MIN = 360.  # minutes
    DEFAULT_NUMBER_DIAFILTRATIONS = 1  # integer

    DEFAULT_FINAL_CONC_TARGET_MASS = 100.  # grams
    DEFAULT_FINAL_CONC_TIMEOUT_MIN = 360.  # minutes
    DEFAULT_FINAL_CONC_TARGET = 10  # g/L

    DEFAULT_PINCH_VALVE_LOCK_IN_MIN = 2.  # minutes

    hub_sn: int = None
    lab_mode: bool

    # add 3/26/2021
    # flag to set for 2 pump only operation
    two_pump_config: bool = False

    log_file_name: str = "TFF_operation"

    drug_substance: str = None
    filter_area_cm2: float = None
    polysaccharide_mass_mg: float = None
    do_prompts: bool = True
    current_phase: int = None

    pump_1_target_flowrate_ml_min: float = None
    pump_2_target_flowrate_ml_min: float = None
    pump_3_target_flowrate_ml_min: float = None

    # initial buffer to transfer in 3 pump config
    initial_transfer_volume: float = None

    # shared pinch valve initial % open
    pinch_valve_init_pct_open: float = 0.35

    # shared pinch valve lock in time
    pinch_valve_lock_in_min: float = None

    # balance stabilization time delay
    record_mass_time_delay_s: float = 5.

    # #################################

    # *** init concentration params ***

    # timestamps
    init_conc_start_time: str = None
    init_conc_end_time: str = None

    # mass & concentration params
    init_conc_target_mass_g: float = None
    init_conc_actual_mass_g: float = None
    init_conc_timeout_min: float = None
    init_conc_target_g_l: float = None
    init_conc_volume_ml: float = None

    # pump 1 ramp params
    init_conc_pump1_ramp_interval_s: float = 30
    init_conc_pump1_ramp_increment_ml_min: float = 2
    init_conc_pump1_ramp_pct_inc: float = 0.25
    init_conc_pump1_ramp_timeout_min: float = 60

    # pumps 2 & 3 ramp params
    init_conc_pumps_2_3_ramp_interval_s: float = 30
    init_conc_pumps_2_3_ramp_number_rate_changes: int = 6
    init_conc_pumps_2_3_ramp_timeout_min: float = 60

    # pump target flowrates
    init_conc_pump_1_target_flowrate_ml_min: float = None
    init_conc_pump_2_target_flowrate_ml_min: float = None
    init_conc_pump_3_target_flowrate_ml_min: float = None

    # #################################

    # *** diafiltration  params ***

    # timestamps
    diafilt_start_time: str = None
    diafilt_end_time: str = None

    # mass & concentration params
    diafilt_target_mass_g: float = None
    diafilt_actual_mass_g: float = None
    diafilt_timeout_min: float = None
    number_diafiltrations: int = None

    # pumps 2 & 3 ramp params
    diafilt_pumps_2_3_ramp_interval_s: float = 30
    diafilt_pumps_2_3_ramp_number_rate_changes: int = 6
    diafilt_pumps_2_3_ramp_timeout_min: float = 60

    # pump target flowrates
    diafilt_pump_1_target_flowrate_ml_min: float = None
    diafilt_pump_2_target_flowrate_ml_min: float = None
    diafilt_pump_3_target_flowrate_ml_min: float = None

    # #################################

    # *** final concentration  params ***

    # timestamps
    final_conc_start_time: str = None
    final_conc_end_time: str = None

    # mass & concentration params
    final_conc_target_mass_g: float = None
    final_conc_actual_mass_g: float = None
    final_conc_target_g_l: float = None
    final_conc_timeout_min: float = None

    # pump 3 ramp params
    final_conc_pump3_ramp_interval_s: float = 30
    final_conc_pump3_ramp_increment_ml_min: float = 1
    final_conc_pump3_ramp_pct_inc: float = 0.25
    final_conc_pump3_ramp_timeout_min: float = 60

    # pump target flowrates
    final_conc_pump_1_target_flowrate_ml_min: float = None
    final_conc_pump_2_target_flowrate_ml_min: float = None
    final_conc_pump_3_target_flowrate_ml_min: float = None

    # #################################

    _devices: Devices = None
    _data: Data = None
    _aqueduct: Aqueduct = None
    _setpoints: Setpoints = None
    _watchdog: Watchdog = None
    _model: local.lib.tff.models = None

    def __init__(
            self,
            devices_obj: Devices = None,
            data: Data = None,
            aqueduct: Aqueduct = None,
            setpoints: Setpoints = None,
            watchdog: Watchdog = None,
            drug_substance: str = DEFAULT_DRUG_SUBSTANCE,
            filter_area_cm2: float = DEFAULT_FILTER_AREA,
            polysaccharide_mass_mg: float = DEFAULT_POLYSACCHARIDE_MASS,
            pump_1_target_flowrate_ml_min: float = DEFAULT_PUMP_1_FLOWRATE,
            pump_2_target_flowrate_ml_min: float = DEFAULT_PUMP_2_FLOWRATE,
            pump_3_target_flowrate_ml_min: float = DEFAULT_PUMP_3_FLOWRATE,
            initial_transfer_volume: float = DEFAULT_INIT_TRANSFER_VOL,
            init_conc_target_mass_g: float = DEFAULT_INIT_CONC_TARGET_MASS,
            init_conc_timeout_min: float = DEFAULT_INIT_CONC_TIMEOUT_MIN,
            init_conc_target_g_l: float = DEFAULT_INIT_CONC_TARGET,
            init_conc_volume_ml: float = DEFAULT_INIT_CONC_VOLUME_ML,
            diafilt_target_mass_g: float = DEFAULT_DIAFILT_TARGET_MASS,
            diafilt_timeout_min: float = DEFAULT_DIAFILT_TIMEOUT_MIN,
            number_diafiltrations: int = DEFAULT_NUMBER_DIAFILTRATIONS,
            final_conc_target_mass_g: float = DEFAULT_FINAL_CONC_TARGET_MASS,
            final_conc_timeout_min: float = DEFAULT_FINAL_CONC_TIMEOUT_MIN,
            final_conc_target_g_l: float = DEFAULT_FINAL_CONC_TARGET,
            pinch_valve_lock_in_min: float = DEFAULT_PINCH_VALVE_LOCK_IN_MIN,
            **kwargs
    ):

        self._devices = devices_obj
        self._data = data
        self._data._process = self
        self._aqueduct = aqueduct
        if isinstance(self._aqueduct, Aqueduct):
            self.hub_sn = self._aqueduct.hub_sn
            self.lab_mode = self._aqueduct.is_lab_mode()

        self._setpoints = setpoints
        self._watchdog = watchdog
        if isinstance(self._watchdog, Watchdog):
            self._watchdog.assign_process_to_alarms(self)
        self._model = local.lib.tff.models.PressureModel(
            aqueduct=self._aqueduct,
            devices_obj=self._devices,
            data=self._data,
        )
        self._data._model = self._model

        self.drug_substance = drug_substance
        self.filter_area_cm2 = filter_area_cm2
        self.polysaccharide_mass_mg = polysaccharide_mass_mg

        self.pump_1_target_flowrate_ml_min = pump_1_target_flowrate_ml_min
        self.pump_2_target_flowrate_ml_min = pump_2_target_flowrate_ml_min
        self.pump_3_target_flowrate_ml_min = pump_3_target_flowrate_ml_min

        self.assign_process_flowrates(**kwargs)

        self.initial_transfer_volume = initial_transfer_volume

        self.init_conc_target_mass_g = init_conc_target_mass_g
        self.init_conc_timeout_min = init_conc_timeout_min
        self.init_conc_target_g_l = init_conc_target_g_l
        self.init_conc_volume_ml = init_conc_volume_ml

        self.diafilt_target_mass_g = diafilt_target_mass_g
        self.diafilt_timeout_min = diafilt_timeout_min
        self.number_diafiltrations = number_diafiltrations

        self.final_conc_target_mass_g = final_conc_target_mass_g
        self.final_conc_timeout_min = final_conc_timeout_min
        self.final_conc_target_g_l = final_conc_target_g_l

        self.pinch_valve_lock_in_min = pinch_valve_lock_in_min

    def assign_process_flowrates(self, **kwargs: dict):
        """
        Assign pump_X_target_flowrate_ml_min
        to the init_conc, diafilt, final_conc phases

        :param kwargs:
        :return:
        """

        for _s in ['init_conc_', 'diafilt_', 'final_conc_']:
            for _r in ['pump_1_target_flowrate_ml_min',
                       'pump_2_target_flowrate_ml_min',
                       'pump_3_target_flowrate_ml_min']:
                a = _s + _r
                if a in kwargs:
                    setattr(self, a, kwargs.get(a))
                else:
                    setattr(self, a, getattr(self, _r))

    def get_target_flowrate(self, pump_name: str) -> Union[float, None]:

        if self.current_phase == self.INITIAL_CONC_PHASE:
            if pump_name == PUMP1_NAME:
                return self.init_conc_pump_1_target_flowrate_ml_min
            elif pump_name == PUMP2_NAME:
                return self.init_conc_pump_2_target_flowrate_ml_min
            elif pump_name == PUMP3_NAME:
                return self.init_conc_pump_3_target_flowrate_ml_min

        if self.current_phase == self.DIAFILT_PHASE:
            if pump_name == PUMP1_NAME:
                return self.diafilt_pump_1_target_flowrate_ml_min
            elif pump_name == PUMP2_NAME:
                return self.diafilt_pump_2_target_flowrate_ml_min
            elif pump_name == PUMP3_NAME:
                return self.diafilt_pump_3_target_flowrate_ml_min

        if self.current_phase == self.FINAL_CONC_PHASE:
            if pump_name == PUMP1_NAME:
                return self.final_conc_pump_1_target_flowrate_ml_min
            elif pump_name == PUMP2_NAME:
                return self.final_conc_pump_2_target_flowrate_ml_min
            elif pump_name == PUMP3_NAME:
                return self.final_conc_pump_3_target_flowrate_ml_min

    def get_target_mass(self) -> Union[float, None]:
        """
        Returns the target mass on Scale3 (permeate scale) for the Process,
        accounts for the current phase (init conc, diafilt, final conc)

        :return:
        """

        if self.current_phase == self.INITIAL_CONC_PHASE:
            return self.init_conc_target_mass_g
        elif self.current_phase == self.DIAFILT_PHASE:
            return self.diafilt_target_mass_g
        elif self.current_phase == self.FINAL_CONC_PHASE:
            return self.final_conc_target_mass_g

    def set_quick_run_params(self, speed: str = 'fast', accelerate_watchdog: bool = True):
        """
        Set's the parameters for pump ramping, valve lock in to compressed
        time values to allow for a quick run of the protocol.

        Intended for debugging.

        :return:
        """
        ramp_interval_s = 5
        timeout_min = .5
        pv_lock_in_min = 0.5

        if speed == 'fast':
            ramp_interval_s = 5
            timeout_min = .5
            pv_lock_in_min = 0.5

        elif speed == 'medium':
            ramp_interval_s = 10
            timeout_min = 30
            pv_lock_in_min = 2

        self.init_conc_pump1_ramp_interval_s = ramp_interval_s
        self.init_conc_pumps_2_3_ramp_interval_s = ramp_interval_s
        self.init_conc_timeout_min = timeout_min

        self.diafilt_pumps_2_3_ramp_interval_s = ramp_interval_s
        self.diafilt_timeout_min = timeout_min

        self.final_conc_pump3_ramp_interval_s = ramp_interval_s
        self.final_conc_timeout_min = timeout_min

        self.pinch_valve_lock_in_min = pv_lock_in_min

        if accelerate_watchdog:
            self._watchdog.set_quick_run_params()

    def do_tff_protocol(self, quick: bool = False):
        """
        Runs entire TFF operation protocol sequentially.

        :param quick: if set to True, will set the Process's params to enable a
            quick run
        :return: None
        """

        if quick is True:
            self.set_quick_run_params()

        self.initialize()
        self.do_initial_conc_prompts()
        self.do_init_transfer()
        self.do_init_conc()
        self.do_init_conc_to_diafilt_transition()
        self.do_diafiltration()
        self.do_diafilt_to_final_conc_transition()
        self.do_final_concentration()
        self.do_cleanup()
        self.do_wash()

    def log_info_to_dict(self) -> dict:
        """
        Converts the relevant log info to a Python dictionary.

        :return:
        """
        log_dict = {}

        for t in inspect.getmembers(self):
            attribute, value = t[0], t[1]
            if attribute[:1] != '_' \
                    and not any(l.isupper() for l in attribute) \
                    and not callable(value):
                log_dict.update({attribute: value})

        return log_dict

    def add_process_info_to_log(self):
        """
        Adds process parameters to the Aqueduct log file.

        :return:
        """
        log_dict = self.log_info_to_dict()
        log_info = pprint.pformat(log_dict)
        self._aqueduct.log("\n" + log_info)

    def initialize(self):
        """
        ************************
            Initialize
        ************************

        All Pumps begin at 0% flow
        Pinch Valve 30% open
        Start reading SCIP and OHSA devices at 1 s interval
        """

        print("Initializing Operation...")

        print("Stopping all Pumps.")

        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        self._devices.PV.set_position(pct_open=self.pinch_valve_init_pct_open, record=True)

        # start reading the outputs of the Parker SciLog
        # at an interval of once per second
        self._devices.SCIP.start(interval_s=1., record=True)

        # start reading the outputs of the OHSA balance device
        # at an interval of once per second
        self._devices.OHSA.start(interval_s=1., record=True)

    def do_initial_conc_prompts(self):
        """
        ************************
            User Interaction
            for Product Pour
            and Mass Input
        ************************

        User Input for log file name

        Prompt User to place an empty vessel on Scale 1 (feed vessel)
        Software tare Scale 1
        Prompt User to pour product into feed vessel on Scale 1

        Prompt User to place an empty vessel on Scale 2 (buffer vessel)
        Software tare Scale 2
        Prompt User to pour product into feed buffer on Scale 2

        Prompt User to place an empty vessel on Scale 3 (permeate vessel)
        Software tare Scale 3

        User Input for mass in mg
        User input for Concentration target in g/L
        User Input for Init Conc Total Volume in mL

        Calc permeate mass target in g
        """
        # assign the current phase
        self.current_phase = Process.INITIAL_CONC_PHASE

        if self.do_prompts:
            # Aqueduct input for the log file name
            ipt = self._aqueduct.input(
                message="Enter the desired log file name. Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=str.__name__,
            )

            self.log_file_name = ipt.get_value()

            # prompt operator to place empty vessel on buffer scale
            self._aqueduct.prompt(
                message="Place empty vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
                pause_recipe=True
            )

            # tare scale 2
            print("Taring SCALE2.")
            self._devices.OHSA.tare(SCALE2_INDEX)

            # prompt operator to pour product into buffer vessel, press prompt to continue
            self._aqueduct.prompt(
                message="Pour product solution into vessel on Scale 2 (buffer scale), connect the buffer feed line to "
                        "the retentate vessel, and manually prime the buffer feed line. "
                        "Press <b>continue</b> to continue.",
                pause_recipe=True
            )

            # prompt operator to place empty vessel on permeate scale
            self._aqueduct.prompt(
                message="Place empty vessel on Scale 3 (permeate scale). Press <b>continue</b> to continue.",
                pause_recipe=True
            )

            # tare scale 3
            print("Taring SCALE3.")
            self._devices.OHSA.tare(SCALE3_INDEX)

            # Aqueduct input for the Polysaccharide mass
            ipt = self._aqueduct.input(
                message="Enter the mass of Polysaccharide in milligrams (mg). Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )

            self.polysaccharide_mass_mg = ipt.get_value()

            # Aqueduct input for concentration target
            ipt = self._aqueduct.input(
                message="Enter the initial concentration target concentration in grams per liter (g/L). Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )

            self.init_conc_target_g_l = ipt.get_value()

            # catch a zero init_conc_target_g_l
            while not self.init_conc_target_g_l or self.init_conc_target_g_l == 0.:
                # Aqueduct input for concentration target
                ipt = self._aqueduct.input(
                    message="Error! Can't enter '0' for target concentration!<br><br>"
                            "Re-enter the initial concentration target concentration in grams per liter (g/L). "
                            "Press <b>submit</b> to continue.",
                    pause_recipe=True,
                    dtype=float.__name__,
                )

                self.init_conc_target_g_l = ipt.get_value()

            # Aqueduct input for the initial product volume
            ipt = self._aqueduct.input(
                message="Enter the initial product volume in milliliters (mL). Press <b>submit</b> to begin transfer"
                        " and initial concentration.",
                pause_recipe=True,
                dtype=float.__name__,
            )

            self.init_conc_volume_ml = ipt.get_value()

            # calculate the target mass (scale 3)
            # Initial product volume [2.a.x] - initial mass of product [2.a.viii] /
            # initial concentration target [2.a.ix]
            self.init_conc_target_mass_g = local.lib.tff.helpers.calc_init_conc_target_mass_g(
                init_conc_volume_ml=self.init_conc_volume_ml,
                polysaccharide_mass_mg=self.polysaccharide_mass_mg,
                init_conc_target_g_l=self.init_conc_target_g_l
            )

            print("Initial Concentration target mass (g) for Scale 3 (permeate scale): {}".format(
                local.lib.tff.helpers.format_float(self.init_conc_target_mass_g, 2)
            ))

    def do_init_transfer(self):

        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:

            ipt = self._aqueduct.input(
                message="Enter the volume of solution to transfer to the retentate vessel prior to initial"
                        " concentration. Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )
            self.initial_transfer_volume = ipt.get_value()

            # prompt operator to place empty vessel on feed scale
            self._aqueduct.prompt(
                message="Place empty vessel on Scale 1 (feed scale) and connect buffer feed line. Ensure all other"
                        " lines are disconnected from the vessel. Press <b>continue</b> to start transfer.",
                pause_recipe=True
            )

            # tare scale 1
            print("Taring SCALE1.")
            self._devices.OHSA.tare(SCALE1_INDEX)
            time.sleep(5)

            ipt = self._aqueduct.input(
                message="Enter the volume of solution to transfer to the retentate vessel prior to initial"
                        " concentration. Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )
            self.initial_transfer_volume = ipt.get_value()

            # prompt operator to place empty vessel on feed scale
            self._aqueduct.prompt(
                message="Place empty vessel on Scale 1 (feed scale) and connect buffer feed line. Ensure all other"
                        " lines are disconnected from the vessel. Press <b>continue</b> to start transfer.",
                pause_recipe=True
            )

            # tare scale 1
            print("Taring SCALE1.")
            self._devices.OHSA.tare(SCALE1_INDEX)

            self._devices.PUMP2.start(
                mode="continuous",
                direction="forward",
                rate_value=50,
                record=True,
            )

            self._data.update_data(debug=True, pause_on_error=True)
            time_start = time.time()
            timeout = time_start + 3 * 60

            # infinite loop until we meet a break condition
            loops = 0
            while True:

                # check to see whether we've timed out
                if time.time() > timeout:
                    self._devices.PUMP2.stop()
                    self._data.update_data()
                    time.sleep(2)
                    print("Actual amount transferred: {:.2f} g".format(self._data.W1))
                    break

                if isinstance(self._data.W1, float) and self._data.W1 > self.initial_transfer_volume:
                    self._devices.PUMP2.stop()
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog)

                if loops == 5:
                    print("Waiting for {} more seconds...".format(int((timeout - time.time()))))
                    loops = 0

                # increment loops by 1
                loops += 1

            # prompt to confirm completion of transfer and start initial concentration
            self._aqueduct.prompt(
                message="Transfer to retentate vessel complete. Press <b>continue</b> to proceed to initial "
                        "concentration.",
                pause_recipe=True
            )

        else:

            # prompt operator to place empty vessel on feed scale
            self._aqueduct.prompt(
                message="Place empty vessel on Scale 1 (feed scale) and connect all lines."
                        " Press <b>continue</b> to start transfer.",
                pause_recipe=True
            )

            # tare scale 1
            print("Taring SCALE1.")
            self._devices.OHSA.tare(SCALE1_INDEX)

            # prompt operator to pour product into feed vessel, press prompt to continue
            self._aqueduct.prompt(
                message="Pour product solution into vessel on Scale 1 (feed scale). Press <b>continue</b> to proceed to"
                        " initial concentration.",
                pause_recipe=True
            )

    def do_init_conc(self):

        """
        ************************
            Initial Concentration
            Step 1: Pump 1 Ramp Up
        ************************
        Start Pump 1
        Monitor P1, P3
        If P3 < 1 psi and P1 < 30 psi, increase Pinch Valve pressure
        If P1 > 30 psi and P3 > 3, decrease Pinch Valve pressure
        If P3 < 0 and  P1 > 30 psi, decrease Pump 1 flowrate
        Note: this condition is not typically met until startup is completed

        Increase Pump 1 flowrate once per minute, reaching target flowrate after 5 minutes

        """
        # log starting time for init conc
        self.init_conc_start_time = datetime.datetime.utcnow().isoformat()

        print("Beginning Initial Concentration Step 1: Pump 1 Ramp Up.")
        local.lib.tff.methods.pump_ramp(
            interval_s=1, pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.init_conc_pump_1_target_flowrate_ml_min / 2,
            end_flowrate_ml_min=self.init_conc_pump_1_target_flowrate_ml_min,
            rate_change_interval_s=self.init_conc_pump1_ramp_interval_s,
            rate_change_pct=self.init_conc_pump1_ramp_pct_inc,
            timeout_min=self.init_conc_pump1_ramp_timeout_min,
            adjust_pinch_valve=True,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog
        )

        """
        ************************
            Initial Concentration
            Step 2: Pumps 2 (if present) and 3 Ramp Up      
        ************************
        Start Pump 2 (if present) and Pump 3 at half of target flowrate 
        Increase Pump 2, Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes
        Will adjust pinch valve position during ramp to maintain setpoint bounds in `monitor` method
        """
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("Beginning Initial Concentration Step 2: Pump 2 and Pump 3 Ramp Up.")
        else:
            print("Beginning Initial Concentration Step 2: Pump 3 Ramp Up.")

        # ***UPDATE 1/30/2021 this is the point where we not want to cache the scale1 target mass
        # force an update of data to make sure the reading is latest before caching
        self._data.update_data()
        self._watchdog.volume_accumulation_alarm.set_scale1_target_mass()

        self._devices.SCIP.set_sim_rates_of_change(values=((0.01, 0.01, -0.01,) + 9 * (0,)))

        status = local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.init_conc_pump_2_target_flowrate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.init_conc_pump_2_target_flowrate_ml_min,
            pump3_start_flowrate_ml_min=self.init_conc_pump_3_target_flowrate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.init_conc_pump_3_target_flowrate_ml_min,
            rate_change_interval_s=self.init_conc_pumps_2_3_ramp_interval_s,
            number_rate_changes=self.init_conc_pumps_2_3_ramp_number_rate_changes,
            timeout_min=self.init_conc_pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=True,
            scale3_target_mass_g=self.init_conc_target_mass_g,
            devices_obj=self._devices, data=self._data, watchdog=self._watchdog
        )

        """
        ************************
            Initial Concentration
            Step 3: Pinch Valve Lock In      
        ************************
        """
        # if we hit the target mass during the ramp, skip the pinch valve lock in
        if status != STATUS_TARGET_MASS_HIT:
            print("Setting pinch valve.")
            self._devices.PV.set_position(pct_open=0.3)
            time.sleep(5)
            print("Beginning Initial Concentration Step 3: Pinch Valve Lock-In.")
            status = local.lib.tff.methods.pinch_valve_lock_in(
                interval=1,
                target_p3_psi=self._setpoints.P3_target_pressure.value,
                timeout_min=self.pinch_valve_lock_in_min,
                scale3_target_mass_g=self.init_conc_target_mass_g,
                devices_obj=self._devices,
                data=self._data
            )

        # update the data object
        self._data.update_data()

        """
        ************************
            Initial Concentration
            Step 4: Wait for Target Mass on Scale 3    
        ************************
        turn on over pressure and low pressure alarms
        wait for target mass or timeout 
        """
        # UPDATE 1/14/2021 - avoid lag in waiting here if init conc hit in ramp by jumping straight through
        # if we already hit the target mass, skip jump straight through init conc wait
        if status != STATUS_TARGET_MASS_HIT:
            print("Waiting for initial concentration SCALE3 target mass {:.2f} g".format(self.init_conc_target_mass_g))

            # find the timeout time to break from loop
            time_start = datetime.datetime.utcnow()
            timeout = time_start + datetime.timedelta(seconds=self.init_conc_timeout_min * 60)

            # turn on the overpressure, low pressure, vacuum condition, and volume accumulation alarms
            self._watchdog.over_pressure_alarm.on()
            self._watchdog.low_pressure_alarm.on()
            self._watchdog.vacuum_condition_alarm.on()
            self._watchdog.volume_accumulation_alarm.on()

            # clear the trailing rates cache
            self._data._cache.clear_cache()

            # turn control on
            self._setpoints.pinch_valve_control_active.update(True)

            # infinite loop until we meet a break condition
            while True:

                # if the mass on SCALE3 is greater than or equal to the process.init_conc_target_mass_g,
                # break from the loop
                if self._data.W3 is not None:
                    if self._data.W3 >= self.init_conc_target_mass_g:
                        break

                # check to see whether we've timed out
                if datetime.datetime.utcnow() > timeout:
                    print("Timed out waiting for initial concentration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog
                )

            # turn off the volume accumulation alarm
            self._watchdog.volume_accumulation_alarm.off()

            # turn off PV control
            self._setpoints.pinch_valve_control_active.update(False)

        """
        ************************
            Initial Concentration
            Complete!    
        ************************
        Stop Pumps 2 and 3, Pump 1 continues at same Rate
        record scale 3 mass as process.init_conc_actual_mass_g
        """

        print("Initial Concentration Step complete.")

        # Set PUMP2 (if present) and PUMP3 to no flow. Pump 1 will continue to operate at
        # target flowrate between Concentration and Diafiltration
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording init conc mass
        print("Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.init_conc_actual_mass_g = self._data.W3

        print("End Initial Concentration SCALE3 mass: {}g".format(self.init_conc_actual_mass_g))

        # log end time for init conc
        self.init_conc_end_time = datetime.datetime.utcnow().isoformat()

    def do_init_conc_to_diafilt_transition(self):

        """
        ************************
            Initial Concentration to
            Diafiltration Transition
        ************************
        tare scale 3 in software
        prompt to place an empty bottle on buffer scale
        tare buffer scale
        prompt to confirm liquid added to buffer scale bottle
        input to enter number of diafiltrations required for Diafilt 1
        """
        # tare scale 3
        print("Taring SCALE3.")
        self._devices.OHSA.tare(SCALE3_INDEX)
        time.sleep(5)

        # open pinch valve
        print("Opening pinch valve.")
        self._devices.PV.set_position(pct_open=0.4)

        if self.do_prompts:

            # prompt operator to place an empty bottle on buffer scale
            p = self._aqueduct.prompt(
                message="Place empty vessel on Scale 2 (buffer scale). Press <b>continue</b> to continue.",
                pause_recipe=False
            )

            # while the prompt hasn't been executed, log data and monitor alarms
            while p:
                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog
                )

            # tare scale 2 after empty vessel is placed on it
            self._devices.OHSA.tare(SCALE2_INDEX)

            # prompt operator to pour liquid into vessel, press prompt to continue
            p = self._aqueduct.prompt(
                message="Pour buffer solution into vessel on Scale 2 (buffer scale) and prime the buffer feed line."
                        " Press <b>continue</b> to continue.",
                pause_recipe=False
            )

            # while the prompt hasn't been executed, log data and monitor alarms
            while p:
                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog
                )

            # Aqueduct input for the the number of diafiltrations required for Diafilt 1
            ipt = self._aqueduct.input(
                message="Enter the number of diavolumes required for Diafiltration 1. Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=int.__name__,
            )

            self.number_diafiltrations = ipt.get_value()

            # calculate diafiltration target mass for scale 3 in grams
            self.diafilt_target_mass_g = local.lib.tff.helpers.calc_diafilt_target_mass_g(
                number_diafiltrations=self.number_diafiltrations,
                polysaccharide_mass_mg=self.polysaccharide_mass_mg,
                init_conc_target_g_l=self.init_conc_target_g_l,
            )

            print("Diafiltration 1 target mass (g) for SCALE3: {}".format(
                local.lib.tff.helpers.format_float(self.diafilt_target_mass_g, 2)
            ))

    def do_diafiltration(self):
        """
        ************************
            Diafiltration
            Step 1: Pump 2 and Pump 3 ramp up
        ************************
        Start Pump 2 and Pump 3 at half of target flowrate
        Increase Pump 2, Pump 3 flowrate once per minute, reaching target flowrate after 5 minutes
        """
        # assign the current phase
        self.current_phase = Process.DIAFILT_PHASE

        # log start time for diafilt
        self.diafilt_start_time = datetime.datetime.utcnow().isoformat()

        # turn off the underpressure alarm during ramp and lock in
        self._watchdog.low_pressure_alarm.off()

        # force an update of data to make sure the reading is latest before caching
        self._data.update_data()
        self._watchdog.volume_accumulation_alarm.set_scale1_target_mass()

        print("Beginning Diafiltration Step 1: PUMP2 and PUMP3 Ramp Up.")
        status = local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.diafilt_pump_2_target_flowrate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.diafilt_pump_2_target_flowrate_ml_min,
            pump3_start_flowrate_ml_min=self.diafilt_pump_3_target_flowrate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.diafilt_pump_3_target_flowrate_ml_min,
            rate_change_interval_s=self.diafilt_pumps_2_3_ramp_interval_s,
            number_rate_changes=self.diafilt_pumps_2_3_ramp_number_rate_changes,
            timeout_min=self.diafilt_pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=True,
            scale3_target_mass_g=self.diafilt_target_mass_g,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog
        )

        """
        ************************
            Diafiltration
            Step 2: Pinch Valve Lock In      
        ************************
        """
        # if we hit the target mass during the ramp, skip the pinch valve lock in
        if status != STATUS_TARGET_MASS_HIT:
            print("Setting pinch valve.")
            self._devices.PV.set_position(pct_open=0.3)
            time.sleep(5)
            print("Beginning Diafiltration Step 2: Pinch Valve Lock-In.")
            status = local.lib.tff.methods.pinch_valve_lock_in(
                interval=1,
                target_p3_psi=self._setpoints.P3_target_pressure.value,
                timeout_min=self.pinch_valve_lock_in_min,
                scale3_target_mass_g=self.diafilt_target_mass_g,
                devices_obj=self._devices,
                data=self._data
            )

        # update the data object
        self._data.update_data()

        """
        ************************
            Diafiltration
            Step 3: Wait for Target Mass on Scale 3    
        ************************
        turn on over pressure and low pressure alarms
        wait for target mass or timeout 
        """
        # if we already hit the target mass, skip jump straight through diafilt wait
        if status != STATUS_TARGET_MASS_HIT:
            print("Waiting for diafiltration SCALE3 target mass {:.2f}g".format(self.diafilt_target_mass_g))

            # turn on the overpressure, underpressure alarms
            self._watchdog.over_pressure_alarm.on()
            self._watchdog.low_pressure_alarm.on()
            self._watchdog.volume_accumulation_alarm.on()

            # clear the trailing rates cache
            self._data._cache.clear_cache()

            # find the timeout time to break from loop
            time_start = datetime.datetime.utcnow()
            timeout = time_start + datetime.timedelta(seconds=self.diafilt_timeout_min * 60)

            self._setpoints.pinch_valve_control_active.update(False)

            # infinite loop until we meet a break condition
            while True:

                # if the mass on SCALE3 is greater than or equal to the process.diafilt_target_mass_g,
                # break from the loop
                if self._data.W3 is not None:
                    if self._data.W3 >= self.diafilt_target_mass_g:
                        break

                # check to see whether we've timed out
                if datetime.datetime.utcnow() > timeout:
                    print("Timed out waiting for diafiltration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog
                )

            # turn off the volume accumulation alarm
            self._watchdog.volume_accumulation_alarm.off()

        """
        ************************
            Diafiltration 
            Complete!
        ************************
        shut off Pump 2 and Pump 3 (buffer and permeate)
        Pump 1 continues at rate from end of Diafilt 
        Record Diafilt mass on Scale 3
        """

        print("Diafiltration Step complete.")

        # Set PUMP2 (if present) and PUMP3 to no flow. Pump 1 will continue to operate at
        # target flowrate between Diafiltration and Final Conc.
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording diafiltration mass
        print("Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.diafilt_actual_mass_g = self._data.W3

        print("End Diafiltration SCALE3 mass: {}g".format(self.diafilt_actual_mass_g))

        # log end time for diafilt
        self.diafilt_end_time = datetime.datetime.utcnow().isoformat()

    def do_diafilt_to_final_conc_transition(self):
        """
        ************************
            Diafilt to Final Conc.
            Transition
        ************************
        tare permeate scale in software
        input for final concentration in g/L
        calculate final concentration target mass
        """

        # tare permeate scale
        print("Taring SCALE3 (permeate scale).")
        self._devices.OHSA.tare(SCALE3_INDEX)
        time.sleep(5)

        # open pinch valve
        print("Opening pinch valve.")
        self._devices.PV.set_position(pct_open=0.4)

        if self.do_prompts:
            # Aqueduct input for final concentration target
            ipt = self._aqueduct.input(
                message="Enter the final concentration target in grams per liter (g/L). Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )

            self.final_conc_target_g_l = ipt.get_value()

        # catch a zero final_conc_target_g_l
        while not self.final_conc_target_g_l or self.final_conc_target_g_l == 0.:
            # Aqueduct input for concentration target
            ipt = self._aqueduct.input(
                message="Error! Can't enter '0' for target concentration!<br><br>"
                        "Re-enter the final concentration target concentration in grams per liter (g/L). "
                        "Press <b>submit</b> to continue.",
                pause_recipe=True,
                dtype=float.__name__,
            )

            self.final_conc_target_g_l = ipt.get_value()

        """
        Target mass (scale 3) = 
        initial mass of product [2.a.viii] / initial concentration target [2.a.ix] - 
        initial mass of product [2.a.viii] / final concentration target [5.d.i]
        """
        self.final_conc_target_mass_g = local.lib.tff.helpers.calc_final_conc_target_mass_g(
            polysaccharide_mass_mg=self.polysaccharide_mass_mg,
            init_conc_target_g_l=self.init_conc_target_g_l,
            final_conc_target_g_l=self.final_conc_target_g_l
        )

        print("Final Concentration target mass (g) for SCALE3: {}".format(
            local.lib.tff.helpers.format_float(self.final_conc_target_mass_g, 2)
        ))

    def do_final_concentration(self):
        """
        ************************
            Final Concentration
            Step 1: Pump 3 ramp up
        ************************
        Start Pump 3 at half of target flowrate
        Increase Pump 3 flowrate in increments of self.final_conc_pump3_ramp_increment_ml_min
            every self.final_conc_pump3_ramp_interval_s seconds until
            target flow rate is reached
        """
        # assign the current phase
        self.current_phase = Process.FINAL_CONC_PHASE

        # log start time for final conc
        self.final_conc_start_time = datetime.datetime.utcnow().isoformat()

        # turn off the underpressure alarms
        self._watchdog.low_pressure_alarm.off()

        print("Beginning Final Concentration Step 1: PUMP3 Ramp Up.")
        status = local.lib.tff.methods.pump_ramp(
            interval_s=1, pump=self._devices.PUMP3, pump_name="PUMP3",
            start_flowrate_ml_min=self.final_conc_pump_3_target_flowrate_ml_min / 2,
            end_flowrate_ml_min=self.final_conc_pump_3_target_flowrate_ml_min,
            rate_change_interval_s=self.final_conc_pump3_ramp_interval_s,
            rate_change_pct=self.final_conc_pump3_ramp_pct_inc,
            timeout_min=self.final_conc_pump3_ramp_timeout_min,
            adjust_pinch_valve=True,
            scale3_target_mass_g=self.final_conc_target_mass_g,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog
        )

        """
        ************************
            Final Concentration
            Step 2: Pinch Valve Lock In      
        ************************
        """
        if status != STATUS_TARGET_MASS_HIT:
            print("Setting pinch valve.")
            self._devices.PV.set_position(pct_open=0.3)
            time.sleep(5)
            print("Beginning Final Concentration Step 2: Pinch Valve Lock-In.")
            status = local.lib.tff.methods.pinch_valve_lock_in(
                interval=1,
                target_p3_psi=self._setpoints.P3_target_pressure.value,
                timeout_min=self.pinch_valve_lock_in_min,
                scale3_target_mass_g=self.final_conc_target_mass_g,
                devices_obj=self._devices,
                data=self._data)

        self._data.update_data()

        """
        ************************
            Final Concentration
            Step 3: Wait for Target Mass on Scale 3   
        ************************
        turn on over pressure and low pressure alarms
        wait for target mass or timeout 
        """
        # avoid lag in waiting here if final conc target hit in ramp by jumping straight through
        # if we already hit the target mass, skip jump straight through final conc wait
        if status != STATUS_TARGET_MASS_HIT:
            print("Waiting for final concentration SCALE3 target mass {:.2f}g".format(self.final_conc_target_mass_g))

            # turn on the overpressure, underpressure alarms
            self._watchdog.over_pressure_alarm.on()
            self._watchdog.low_pressure_alarm.on()
            self._watchdog.volume_accumulation_alarm.on()

            # clear the trailing rates cache
            self._data._cache.clear_cache()

            # find the timeout time to break from loop
            time_start = datetime.datetime.utcnow()
            timeout = time_start + datetime.timedelta(seconds=self.final_conc_timeout_min * 60)

            self._setpoints.pinch_valve_control_active.update(False)

            # infinite loop until we meet a break condition
            while True:

                # if the mass on SCALE3 is greater than or equal to the process.final_conc_target_mass_g,
                # break from the loop
                if self._data.W3 is not None:
                    if self._data.W3 >= self.final_conc_target_mass_g:
                        break

                # check to see whether we've timed out
                if datetime.datetime.utcnow() > timeout:
                    print("Timed out waiting for final concentration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog
                )

            # turn off the volume accumulation alarm
            self._watchdog.volume_accumulation_alarm.off()

        """
        ************************
            Final Concentration
            Complete!
        ************************
        Stop Pumps 2 and 3
        Wait for Scale 3 to stabilize (hard coded time delay)
        Record Final Concentration mass
        """

        print("Final Concentration Step complete.")

        # stop Pumps 2 (if present) and 3
        if isinstance(self._devices.PUMP2, devices.aqueduct.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording final conc mass
        print("Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.final_conc_actual_mass_g = self._data.W3

        print("End Final Concentration SCALE3 mass: {}g".format(self.final_conc_actual_mass_g))

        # log final conc end time
        self.final_conc_end_time = datetime.datetime.utcnow().isoformat()

    def do_cleanup(self):
        """
        ************************
            Final Concentration
            Clean Up
        ************************
        slowly open pinch valve to 30%
        User Prompt to confirm that the retentate line is blown down (wait here)
        Stop Pump 1
        """

        # slowly open pinch valve to 30%
        print("Beginning clean-up, open pinch valve to 30%")
        local.lib.tff.methods.open_pinch_valve(
            target_pct_open=self.pinch_valve_init_pct_open,
            increment_pct_open=0.005,
            interval_s=1,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog)

        # prompt operator to confirm that the retentate line is blown down (wait here)
        p = self._aqueduct.prompt(
            message="Confirm that the retentate line is blown down. Press <b>continue</b> to continue.",
            pause_recipe=True
        )

        # stop Pump 1
        print("Stopping PUMP1.")
        self._devices.PUMP1.stop()

    def do_wash(self):
        """
        *********************
            Recovery Wash
        *********************
        append the process info to the log file
        save the log file
        Execute recovery wash of filter
        Stop Pump 1
        Stop reading in data from the OHSA and SCIP devices
        """

        # prompt operator to set up recovery flush
        p = self._aqueduct.prompt(
            message="Set up recovery flush. Place the feed and retentate lines in a conical with the desired wash"
                    " volume. Press <b>continue</b> to start wash.",
            pause_recipe=True
        )

        # start Pump !
        self._devices.PUMP1.start(rate_value=self.init_conc_pump_1_target_flowrate_ml_min)

        # clear the trailing rates cache
        self._data._cache.clear_cache()

        # find the timeout time to break from loop
        time_start = datetime.datetime.utcnow()
        timeout = time_start + datetime.timedelta(seconds=5 * 60)
        print("Washing for 5 minutes.")

        # infinite loop until we meet a break condition
        while True:

            # check to see whether we've timed out
            if datetime.datetime.utcnow() > timeout:
                print("Wash Complete.")
                break

            local.lib.tff.methods.monitor(
                interval_s=1,
                adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog)

        # stop Pump 1
        print("Stopping PUMP1.")
        self._devices.PUMP1.stop()

        # save log file
        self.add_process_info_to_log()
        self._aqueduct.save_log_file(self.log_file_name, timestamp=True)

        # stop balance and pressure A/D
        self._devices.OHSA.stop()
        self._devices.SCIP.stop()

        print("TFF Full Operation complete!")

    def check_alarms(self):
        """
        Method to quickly check alarm activation / tripping.

        This method turns on the:
            1) over pressure alarm
            2) low pressure alarm
            3) vacuum condition alarm

        The pumps must be started manually.

        :return: None
        """

        # start the balances and pressure transducers
        self._devices.OHSA.start(record=True)
        self._devices.SCIP.start(record=True)

        self._watchdog.over_pressure_alarm.on()
        self._watchdog.low_pressure_alarm.on()
        self._watchdog.vacuum_condition_alarm.on()

        # turn on any other alarms you want to trip here

        last_print: float = time.time()
        print_interval_s: int = 30

        print("Waiting on alarms...")

        while True:
            local.lib.tff.methods.monitor(
                interval_s=1,
                adjust_pinch_valve=False,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog)

            if time.time() > last_print + print_interval_s:
                print("Waiting on alarms...")
                last_print = time.time() + print_interval_s

    def _check_alarms(self):
        """
        Method to be run in simulation mode.

        This method checks the:
            1) over pressure alarm
            2) low pressure alarm
            3) vacuum condition alarm

        By changing the simulated pressures for each
        transducer to a value that will trigger the alarm.
        The alarm restart stop and restart protocol
        will then intervene to recover.

        :return: None
        """

        self.set_quick_run_params()
        self._watchdog.set_quick_run_params()

        self.initialize()

        def reset_sim_pressures_to_3_psi():
            for tn in [TXDCR1_INDEX, TXDCR2_INDEX, TXDCR3_INDEX]:
                self._devices.SCIP.set_sim_pressure(value=3, input_num=SCIP_INDEX, txdcr_num=tn)

        print("Doing Pump 1 Ramp Up...")
        local.lib.tff.methods.pump_ramp(
            interval_s=1, pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.pump_1_target_flowrate_ml_min / 2,
            end_flowrate_ml_min=self.pump_1_target_flowrate_ml_min,
            rate_change_interval_s=1,
            rate_change_ml_min=self.init_conc_pump1_ramp_increment_ml_min,
            timeout_min=self.init_conc_pump1_ramp_timeout_min,
            adjust_pinch_valve=False,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog)

        print("Doing Pumps 2 and 3 Ramp Up...")
        local.lib.tff.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.pump_2_target_flowrate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.pump_2_target_flowrate_ml_min,
            pump3_start_flowrate_ml_min=self.pump_3_target_flowrate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.pump_3_target_flowrate_ml_min,
            rate_change_interval_s=1,
            number_rate_changes=self.init_conc_pumps_2_3_ramp_number_rate_changes,
            timeout_min=self.init_conc_pumps_2_3_ramp_timeout_min,
            adjust_pinch_valve=False, devices_obj=self._devices, data=self._data,
            watchdog=self._watchdog
        )

        self._devices.SCIP.set_sim_noise(active=0)
        self._watchdog.over_pressure_alarm.on()
        self._watchdog.low_pressure_alarm.on()
        self._watchdog.vacuum_condition_alarm.on()

        pressures = [
            (40, TXDCR1_INDEX),
            (40, TXDCR2_INDEX),
            (40, TXDCR3_INDEX),
            (0, TXDCR3_INDEX),
            (-5, TXDCR1_INDEX),
            (-5, TXDCR2_INDEX),
            (-5, TXDCR3_INDEX),
        ]

        for tp in pressures:
            self._devices.SCIP.set_sim_pressure(tp[0], SCIP_INDEX, tp[1])
            time.sleep(1)

            while True:
                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=False,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog)

                reset_sim_pressures_to_3_psi()
                break
