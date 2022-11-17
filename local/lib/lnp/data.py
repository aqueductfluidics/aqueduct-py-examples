import time
from typing import List, Union

from aqueduct.core.aq import Aqueduct
import local.lib.lnp.helpers
from local.lib.lnp.definitions import *
from local.lib.lnp.devices import *

class TrailingRates(object):
    """
    Class used to format trailing rate-of-change values for the
    balances and pump rates.
    """
    aq_pump_ml_min: Union[float, None]
    oil_pump_ml_min: Union[float, None]
    dilution_pump_ml_min: Union[float, None]
    aq_mfm_ml_min: Union[float, None]
    oil_mfm_ml_min: Union[float, None]
    dilution_mfm_ml_min: Union[float, None]

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
        self.aq_pump_ml_min = R1_ml_min
        self.oil_pump_ml_min = W1_ml_min
        self.dilution_pump_ml_min = R2_ml_min
        self.aq_mfm_ml_min = W2_ml_min
        self.oil_mfm_ml_min = R3_ml_min
        self.dilution_mfm_ml_min = W3_ml_min

    def print(self):
        print("[DATA] W1: {} mL/min, R1: {} mL/min, W2: {} mL/min, R2: {} mL/min, W3: {} mL/min, R3: {} mL/min".format(
            local.lib.lnp.helpers.format_float(self.oil_pump_ml_min, 3),
            local.lib.lnp.helpers.format_float(self.aq_pump_ml_min, 2),
            local.lib.lnp.helpers.format_float(self.aq_mfm_ml_min, 3),
            local.lib.lnp.helpers.format_float(self.dilution_pump_ml_min, 2),
            local.lib.lnp.helpers.format_float(self.dilution_mfm_ml_min, 3),
            local.lib.lnp.helpers.format_float(self.oil_mfm_ml_min, 2),
        ))


class DataCacheItem(object):
    """
    A class to structure cached data. Mirrors the structure of the
    Data class.
    """
    aq_mfm_ml_min: Union[float, None] = None  
    aq_pres_psi: Union[float, None] = None
    aq_pump_ml_min: Union[float, None] = None  
    aq_valve_pos: Union[int, None] = None
    dilution_pump_ml_min: Union[float, None] = None  
    oil_mfm_ml_min: Union[float, None] = None  
    oil_pres_psi: Union[float, None] = None
    oil_pump_ml_min: Union[float, None] = None  
    oil_valve_pos: Union[int, None] = None
    product_mfm_ml_min: Union[float, None] = None  
    product_pres_psi: Union[float, None] = None
    timestamp: Union[float, None] = None  

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
    _devices: local.lib.lnp.devices.Devices = None

    def __init__(self, devices_obj: local.lib.lnp.devices.Devices):
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

            if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP):
                enum_keys = (('W1', 'R1'), ('W2', 'R2'), ('W3', 'R3'))
            else:
                # have to use R3 in lieu of R2 when PUMP2 is absent
                enum_keys = (('W1', 'R1'), ('W2', 'R3'), ('W3', 'R3'))

            # loop through the cache in reverse
            for i in range(1, len(self._cache) - 1):

                # calculate the time interval between the cache timestamps
                _dt = self._cache[-i].timestamp - \
                    self._cache[-(i + 1)].timestamp

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
                        (getattr(self._cache[-i], k[0]) -
                         getattr(self._cache[-(i + 1)], k[0])) / _dt
                    )

                    # multiply by 60 to convert to g/min
                    balance_accumulation_list_g_min[jj].append(
                        balance_delta_mass_g_delta_t_s * 60.)

                    pump_nominal_rate_ml_min = (getattr(self._cache[-i], k[1]) + getattr(self._cache[-(i + 1)],
                                                                                         k[1])) / 2.

                    pump_nominal_rate_list_ml_min[jj].append(
                        pump_nominal_rate_ml_min)

                counts += 1

            # remove outliers from the the balance_accumulation_list_g_min
            for i, rate_list in enumerate(balance_accumulation_list_g_min):
                rate_sum = sum(rate_list)
                rate_mean = rate_sum / len(rate_list)
                # threshold deviation for determining an outlier
                threshold_ml_min = 5
                good_rates = [r for r in rate_list if (
                    rate_mean - threshold_ml_min < r < rate_mean + threshold_ml_min)]
                # set the mean with the good values
                balance_accumulation_mean_g_min[i] = sum(
                    good_rates) / len(good_rates)

            # remove outliers from the the pump_nominal_rate_list_ml_min
            for i, rate_list in enumerate(pump_nominal_rate_list_ml_min):
                rate_sum = sum(rate_list)
                rate_mean = rate_sum / len(rate_list)
                # threshold deviation for determining an outlier
                threshold_ml_min = 5
                good_rates = [r for r in rate_list if (
                    rate_mean - threshold_ml_min < r < rate_mean + threshold_ml_min)]
                # set the mean with the good values
                pump_nominal_rate_mean_ml_min[i] = sum(
                    good_rates) / len(good_rates)

            if counts > 0:
                if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP):
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
                print("[DATA] Trailing calc exception: {}".format(e))
            return None


class Data(object):
    """
    Class to help with logging and updating data for the
    LNP setup.
    """
    aq_mfm_ml_min: Union[float, None] = None 
    aq_pres_psi: Union[float, None] = None
    aq_pump_ml_min: Union[float, None] = None  
    aq_valve_pos: Union[int, None] = None
    aq_temperature_c: Union[float, None] = None  
    dilution_pump_ml_min: Union[float, None] = None  
    oil_mfm_ml_min: Union[float, None] = None  
    oil_pres_psi: Union[float, None] = None
    oil_pump_ml_min: Union[float, None] = None 
    oil_valve_pos: Union[int, None] = None
    oil_temperature_c: Union[float, None] = None 
    product_mfm_ml_min: Union[float, None] = None  
    product_pres_psi: Union[float, None] = None
    product_temperature_c: Union[float, None] = None 
    timestamp: Union[float, None] = None 

    # timestamp of last write to log file
    log_timestamp: Union[float, None] = None
    # interval in seconds between writes to log file
    _logging_interval_s: Union[int, float] = 5

    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process = None  # pointer to Process object
    _model = None  # pointer to Model object

    _cache: DataCache = None

    # errors to simulate mismatch between nominal flow rates and
    # measured values
    _oil_pump_sim_error_pct = 0.0025
    _aq_pump_sim_error_pct = -0.0032
    _dilution_pump_sim_error_pct = 0.018

    _extrapolation_timestamp: float = None

    def __init__(self, devices_obj: local.lib.lnp.devices.Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param devices_obj:
        :param aqueduct_obj:
        """
        self._devices = devices_obj
        self._aqueduct = aqueduct_obj

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
        mass_flows = self._devices.MFM.get_all_mass_flows()
        aq_pump_mass_flow = self._devices.AQ_PUMP.get_flow_rate()
        oil_pump_mass_flow = self._devices.OIL_PUMP.get_flow_rate()
        dilution_pump_mass_flow = self._devices.DILUTION_PUMP.get_flow_rate()
        valve_positions = self._devices.SOL_VALVES.positions()
        temperatures = self._devices.TEMP_PROBE.get_all_temperatures()

        self.aq_mfm_ml_min: Union[float, None] = aq_pump_mass_flow 
        self.aq_pres_psi: Union[float, None] = pressures[AQUEOUS_PRES_TDCR_INDEX]
        self.aq_pump_ml_min: Union[float, None] = mass_flows[AQUEOUS_MFM_INDEX]  
        self.aq_valve_pos: Union[int, None] = valve_positions[AQUEOUS_VALVE_INDEX]
        self.aq_temperature_c: Union[float, None] = temperatures[AQUEOUS_TEMP_PROBE_INDEX] 
        self.dilution_pump_ml_min: Union[float, None] = dilution_pump_mass_flow 
        self.oil_mfm_ml_min: Union[float, None] = mass_flows[OIL_MFM_INDEX]    
        self.oil_pres_psi: Union[float, None] = pressures[OIL_PRES_TDCR_INDEX]
        self.oil_pump_ml_min: Union[float, None] = oil_pump_mass_flow  
        self.oil_valve_pos: Union[int, None] = valve_positions[OIL_VALVE_INDEX]
        self.oil_temperature_c: Union[float, None] = temperatures[OIL_TEMP_PROBE_INDEX] 
        self.product_mfm_ml_min: Union[float, None] = mass_flows[PRODUCT_MFM_INDEX]     
        self.product_pres_psi: Union[float, None] = mass_flows[PRODUCT_PRES_TDCR_INDEX] 
        self.product_temperature_c: Union[float, None] = temperatures[PRODUCT_TEMP_PROBE_INDEX] 

        self.timestamp = time.time()

        # if not self._is_lab_mode:
        #     balance_rocs = [0, 0, 0, 0]
        #     # if PUMP2 is present, use this to drive sim value balance
        #     if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP):
        #         balance_rocs[SCALE2_INDEX] = (-1 * self.R2) * \
        #             (1. + self._scale2_sim_error_pct)
        #     # else, use PUMP3 to drive it
        #     else:
        #         balance_rocs[SCALE2_INDEX] = (-1 * self.R3) * \
        #             (1. + self._scale2_sim_error_pct)
        #     balance_rocs[SCALE3_INDEX] = self.R3 * \
        #         (1. + self._scale3_sim_error_pct)
        #     balance_rocs[SCALE1_INDEX] = -1 * \
        #         (balance_rocs[SCALE2_INDEX] + balance_rocs[SCALE3_INDEX])
        #     # mL/min to mL/s
        #     balance_rocs = [r / 60. for r in balance_rocs]
        #     self._devices.OHSA.set_sim_rates_of_change(balance_rocs)
        #     self._model.calc_pressures()

        # save the data to the cache
        self._cache.cache(data=self)

    def log_data(self) -> None:
        """
        Method to log:


        at a given time.

        :return: None
        """
        # self._aqueduct.log(
        #     "P1: {0}, "
        #     "P2: {1}, "
        #     "P3: {2}, "
        #     "W1: {3}, "
        #     "W2: {4}, "
        #     "W3: {5}, "
        #     "R1: {6}, "
        #     "R2: {7}, "
        #     "R3: {8}, "
        #     "PV: {9}".format(
        #         local.lib.lnp.helpers.format_float(self.P1, 3),
        #         local.lib.lnp.helpers.format_float(self.P2, 3),
        #         local.lib.lnp.helpers.format_float(self.P3, 3),
        #         local.lib.lnp.helpers.format_float(self.W1, 3),
        #         local.lib.lnp.helpers.format_float(self.W2, 3),
        #         local.lib.lnp.helpers.format_float(self.W3, 3),
        #         local.lib.lnp.helpers.format_float(self.R1, 3),
        #         local.lib.lnp.helpers.format_float(self.R2, 3),
        #         local.lib.lnp.helpers.format_float(self.R3, 3),
        #         local.lib.lnp.helpers.format_float(self.PV, 4)
        #     ))

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
                d.update(
                    {k[0]: getattr(self, k[0], None).strftime('%Y-%m-%dT%H:%M:%S.%f')})
            else:
                d.update({k[0]: local.lib.lnp.helpers.format_float(
                    getattr(self, k[0], None), k[1])})
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
                scale3_delta_m_g = self.R3 / 60. * \
                    (self.timestamp - self._extrapolation_timestamp)

                scale3_mass_g = self.W3 + scale3_delta_m_g * \
                    (1. + self._scale3_sim_error_pct)

                # BUFFER pump, debit this value
                # if PUMP2 is present, drive with PUMP2
                if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP):
                    scale2_delta_m_g = self.R2 / 60. * \
                        (self.timestamp - self._extrapolation_timestamp)
                    scale2_mass_g = self.W2 - scale2_delta_m_g * \
                        (1. + self._scale2_sim_error_pct)

                else:
                    scale2_delta_m_g = self.R3 / 60. * \
                        (self.timestamp - self._extrapolation_timestamp)
                    scale2_mass_g = self.W2 - scale2_delta_m_g * \
                        (1. + self._scale2_sim_error_pct)

                # FEED pump, adding from BUFFER, debiting from PERMEATE
                scale1_mass_g = self.W1 + \
                    (scale2_delta_m_g - scale3_delta_m_g) * \
                    (1. + self._scale1_sim_error_pct)

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
            print("[DATA] Extrapolation error: {}".format(e))

    def init_sim_values(self):

        if not self._is_lab_mode:
            if isinstance(self._devices.TEMP_PROBE, aqueduct.devices.tempx.obj.TEMPX):
                self._devices.TEMP_PROBE.set_sim_noise(0.1)
                self._devices.TEMP_PROBE.set_sim_temperatures(values=(25, 25, 25, 25))
                self._devices.TEMP_PROBE.set_sim_rates_of_change(values=(0, 0, 0, 0))

            if isinstance(self._devices.SCIP, aqueduct.devices.scip.obj.SCIP):
                self._devices.SCIP.set_sim_pressures(
                    values=((5., 5., 5.,) + 9 * (0,)))
                self._devices.SCIP.set_sim_noise(
                    values=((0.01, 0.01, 0.01,) + 9 * (0,)))
                self._devices.SCIP.set_sim_rates_of_change(values=(12 * (0,)))
