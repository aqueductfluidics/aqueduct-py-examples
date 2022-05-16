import datetime
import time
import enum
import json
import threading

from aqueduct.aqueduct import (
    Aqueduct, Setpoint, Recordable, UserInputTypes, ALLOWED_DTYPES
)

import devices.aqueduct.trcx.obj
import devices.aqueduct.trcx.constants
import devices.aqueduct.eust.obj
import devices.aqueduct.eust.constants

from typing import List, Tuple, Callable, Union

from local.lib.ph_control.helpers import format_float


def format_float(value: Union[float, int, str], precision: int = 2) -> str:
    """
    Helper method to format a value as a float with
    precision and handle possible None values.

    :param value:
    :param precision:
    :return:
    """
    try:
        return "~" if value is None else float(format(float(value), '.{}f'.format(precision)))
    except ValueError:
        return "~"



PUMP_NAME = "TRCX000001"
MIXER_NAME = "EUST000001"


class Devices(object):
    """
    Class with members to contain each Aqueduct Device
    Object in the Setup.

    PUMP is the TRCX TriContinent Node
    MIXER is the IKA EuroStar 60 Overhead Mixer

    In DEV MODE, we create dummy devices for easy access to the methods & constants for each device type.

    In LAB MODE, we associate each Device with the Name for the device
    that is saved on its firmware.
    """
    PUMP: devices.aqueduct.trcx.obj.TRCX = None
    MIXER: devices.aqueduct.eust.obj.EUST = None

    def __init__(self, **kwargs):
        self.PUMP = globals().get(kwargs.get("pump_name"))
        self.MIXER = globals().get(kwargs.get("mixer_name"))

    @classmethod
    def generate_dev_devices(cls):
        dev = Devices()
        dev.PUMP = devices.aqueduct.trcx.obj.TRCX(**devices.aqueduct.trcx.constants.BASE)
        dev.MIXER = devices.aqueduct.eust.obj.EUST(**devices.aqueduct.eust.constants.BASE)

        return dev


class DataCacheItem(object):
    """
    A class to structure cached data. Mirrors the structure of the
    Data class.
    """
    temperature_C: Union[float, None] = None  
    timestamp: Union[float, None] = None  # timestamp of last update

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


class TrailingData(object):
    """
    Class used to format trailing rate-of-change and mean pH values.
    """
    temperature_per_min: Union[float, None]
    temperature_mean: Union[float, None]

    def __init__(self, temperature_per_min: float, temperature_mean: float):
        """
        :param pH_per_min:
        """
        self.temperature_per_min = temperature_per_min
        self.temperature_mean = temperature_mean

    def as_string(self):
        return "temperature R.o.C.: {} C/min., temperature mean: {} C".format(
            format_float(self.temperature_per_min, 2),
            format_float(self.temperature_mean, 2),
        )

    def print(self):
        print(self.as_string())


class DataCache(object):
    """
    A Class to store cached data.
    """
    # a cache of the the previous data objects, should be cleared after
    # ramps to begin calculating from steady state
    # newest value last
    _cache: List[DataCacheItem] = []

    # number of items to keep in _cache list
    _length: int = 360

    # averaging length
    _averaging_length: int = 4

    # index 0 == roc tolerance, 1 == mean tolerance
    _tolerances: List[int] = [1000, 10]

    # set whether the tolerances should be ignored (useful in sims with high roc)
    _ignore_tolerance = False

    # the time when the next item should be added to the list
    _scheduled_time: float = None

    # the cache will only accept items with a timestamp delta of this or greater
    _interval_s: float = 1.

    # ref to Devices
    _devices: Devices = None

    def __init__(self, devices_obj: Devices):
        self._devices = devices_obj

    # enclose the Data close in quotes
    # necessary because the Data class is declared after this point
    # in the code
    def cache(self, data: "Data") -> None:
        """
        Pass the Data class object to cache turbidity measurements.

        :param data: Data
        :return: None
        """

        # if the current time is less than the scheduled time to cache the data,
        # add the data
        if self._scheduled_time is None or self._scheduled_time < data.timestamp:
            item = DataCacheItem(**data.__dict__)

            # append the latest Item to the cache's list
            self._cache.append(item)

            # trim cache length if it exceeds the _length param
            self._cache = self._cache[-1 * self._length:]

            # schedule the next recording time
            self._scheduled_time = self._interval_s + data.timestamp

    def clear_cache(self):
        self._cache = []

    def calc_trailing_data(self, length: int = None) -> Union[TrailingData, None]:

        temperature_roc_values = []
        temperature_values = []

        # set tolerance for time between reads to be acceptable for averaging
        delta_t_interval_s = 1
        delta_t_interval_tolerance_s = 2

        # set the minimum safe iteration length
        if length is None:
            iter_len = min(len(self._cache), self._averaging_length)
        else:
            iter_len = min(len(self._cache), length)

        if iter_len < 2:
            # not enough data to calculate
            return None

        try:
            # check that there are no time differences out of spec
            # if there are, only iterate through the vals after the break
            for data_index in range(1, iter_len - 1):

                _dt = self._cache[-data_index].timestamp - self._cache[-(data_index + 1)].timestamp

                # if we're on the second+ iteration, we're checking
                # the time interval tolerance
                if data_index > 1:

                    if not (
                        delta_t_interval_s - delta_t_interval_tolerance_s < 
                        _dt <
                        delta_t_interval_s + delta_t_interval_tolerance_s
                    ):
                        print(f"time interval tolerance exceeded: {_dt}s")
                        break

                # on the first iteration, we're setting the interval tolerance
                # mean as the time delta between the first and second points
                else:
                    delta_t_interval_s = _dt

                current_temperature = self._cache[-data_index].temperature_C
                previous_temperature = self._cache[-(data_index + 1)].temperature_C

                temperature_roc_values.append(((current_temperature - previous_temperature) / _dt) * 60.)
                temperature_values.append(current_temperature)

            if len(temperature_roc_values) < 1:
                # not enough data to calculate
                print(f"Trailing calc exception, not enough data to calculate: {temperature_values}, {temperature_roc_values}")
                return None

            temperature_roc_mean = 0            
            temperature_mean = 0
          
            for measurement_id, measurement_list in enumerate([temperature_roc_values, temperature_values]):
                vals = measurement_list
                vals_mean = sum(vals) / len(vals)

                # check if the ignore tolerances flag is set
                if not self._ignore_tolerance:

                    def _in_tolerance(v):
                        return (
                            vals_mean - self._tolerances[measurement_id] < 
                            v <
                            vals_mean + self._tolerances[measurement_id]
                        )

                    # remove outliers
                    vals = list(filter(_in_tolerance, vals))
                    
                    # recalc the mean less outliers
                    vals_mean = sum(vals) / len(vals)

                # update the respective attribute
                if measurement_id == 0:
                    temperature_roc_mean = vals_mean

                if measurement_id == 1:
                    temperature_mean = vals_mean

            data = TrailingData(
                temperature_per_min=float(format_float(temperature_roc_mean, 3)),
                temperature_mean=float(format_float(temperature_mean, 3)),
            )

            return data

        except BaseException as e:
            if not isinstance(e, ZeroDivisionError):
                print("Trailing calc exception: {}".format(e))
            else:
                print("No values within tolerances")
            return None

    def calc_trailing_mean(self, length: int = 3, precision: int = 3) -> Union[float, None]:
        try:
            length = min(length, len(self._cache))
            return round(sum(a.pH for a in self._cache[-length::]) / length, precision)
        except BaseException as e:
            # don't let this break
            print(f"calc_trailing_mean error: {str(e)}")
            return None

    def calc_trailing_max(self, length: int = 5) -> Union[float, None]:
        try:
            length = min(length, len(self._cache))
            return max(a.pH for a in self._cache[-length::])
        except BaseException as e:
            # don't let this break
            print(f"calc_trailing_max error: {str(e)}")
            return None


class Data(object):
    """
    Class to help with logging and updating data.
    """
    temperature_C: Union[float, None] = None  
    timestamp: Union[float, None] = None
    
    log_timestamp: Union[float, None] = None  # timestamp of last write to log file
    _logging_interval_s: Union[int, float] = 5  # interval in seconds between writes to log file

    _cache: DataCache = None

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

        self._cache: DataCache = DataCache(self._devices)

    def update_data(self, mixer_index = 0) -> None:
        """
        Method to update the global data dictionary.

        Uses the specific Device Object methods to get the
        data from memory.

        :return:
        """
        self.timestamp = time.time()
        self.temperature_C = self._devices.MIXER.get_temperature(index=mixer_index)

        # save the data to the cache
        self._cache.cache(data=self)

    def log_data(self) -> None:
        """
        Method to log:

            pH

        at a given time.

        :return: None
        """
        self._aqueduct.log(
            "temp: {0}".format(format_float(self.temperature_C, 2),)
        )

    def log_data_at_interval(
            self, 
            interval_s: float = None,
            overwrite_file: bool = True,
            update_before_log: bool = False
        ) -> None:
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

        now = time.time()
        
        if self.log_timestamp is not None:
            if now > (self.log_timestamp + interval_s):
                self.update_data()
                self.log_data()
                self._process.save_log_file()
                self.log_timestamp = now
        
        else:
            self.update_data()
            self.log_data()
            self.log_timestamp = now

    def as_dict(self) -> dict:
        """
        Converts the DataPoint to a dictionary for easy JSON serialization
        and transfer over HTTP.

        :return: dictionary
        """
        keys = [
            ('temperature_C', 3),
            ('timestamp', 3),
        ]
        d = {}
        for k in keys:
            d.update({k[0]: format_float(getattr(self, k[0], None), k[1])})
        return d

    def print_data(self):
        try:
            print(self._cache.calc_trailing_data(length=5).as_string())

        except Exception as e:
            print("No object returned.")


class ProcessHandler(object):
    """
    Class to handle processing each of the reaction stations
    as they proceed through the forumulation steps.

    """
    terminate: Setpoint = None

    pump0_dose_ml: Setpoint = None
    pump1_dose_ml: Setpoint = None
    pump2_dose_ml: Setpoint = None

    pump0_dose_delay_s: Setpoint = None
    pump1_dose_delay_s: Setpoint = None
    pump2_dose_delay_s: Setpoint = None

    temperature_ramp_C_min: Setpoint = None
    temperature_hold_min: Setpoint = None
    temperature_setpoint_C: Setpoint = None

    pump0_mL_added: Recordable = None
    pump1_mL_added: Recordable = None
    pump2_mL_added: Recordable = None

    # control the period in seconds at which
    # the process prints the status of all stations to screen
    status_print_interval_s: float = 360.
    last_status_print_time: float = None

    # the heartbeat interval in seconds to wait between processing
    # any events
    interval_s: int = 1

    # log file name
    log_file_name: str = "reaction_log"

    # reference to the Devices, Data, and Aqueduct classes
    _devices: Devices = None
    _data: Data = None
    _aqueduct: Aqueduct = None

    def __init__(self, devices_obj: Devices = None, aqueduct: Aqueduct = None, data: Data = None):

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

        if isinstance(data, Data):
            self._data = data
            data._process = self

    def print_all_stations(self):
        """
        Method to print the status of each station.

        :return:
        """
        for s in self.stations:
            print(s)

    def save_log_file(self):
        self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

    def print_station_status_at_interval(self):
        """
        Method that prints the status of each station at the
        `status_print_interval_s` period.

        :return:
        """

        if self.last_status_print_time is None or \
                (time.time() > self.last_status_print_time + self.status_print_interval_s):
            self.print_all_stations()
            self.last_status_print_time = time.time()

    def make_setpoints(self):
        for n in (
            "pump0_dose_ml",
            "pump1_dose_ml",
            "pump2_dose_ml",
        ):
            s = self._aqueduct.setpoint(
                name=n,
                dtype=float.__name__,
                value=2,
            )
            setattr(self, n, s)

        for n in (
            "pump0_dose_delay_s",
            "pump1_dose_delay_s",
            "pump2_dose_delay_s",
        ):
            s = self._aqueduct.setpoint(
                name=n,
                dtype=float.__name__,
                value=60,
            )
            setattr(self, n, s)

        self.terminate = self._aqueduct.setpoint(
            name="terminate",
            value=False,
            dtype=bool.__name__,
        )

        self.temperature_ramp_C_min = self._aqueduct.setpoint(
            name="temperature_ramp_C_min",
            value=.5,
            dtype=float.__name__,
        )

        self.temperature_hold_min = self._aqueduct.setpoint(
            name="temperature_hold_min",
            value=2,
            dtype=float.__name__,
        )

        self.temperature_setpoint_C = self._aqueduct.setpoint(
            name="temperature_setpoint_C",
            value=90,
            dtype=float.__name__,
        )

    def make_recordables(self): 
        for n in [
            "pump0_mL_added",
            "pump1_mL_added",
            "pump2_mL_added",
        ]:

            r = self._aqueduct.recordable(
                name=n,
                dtype=float.__name__,
                value=0,
            )
            setattr(self, n, r)

    def dose_pump(self, pump_index: int = 0):

        vc = self._devices.PUMP.make_valve_command(position=4)
        self._devices.PUMP.set_valves(**{f"pump{pump_index}": vc})
        
        time.sleep(1)
        
        wdrw_c = self._devices.PUMP.make_command(
            direction=self._devices.PUMP.WITHDRAW,
            rate_value=5,
            rate_units=self._devices.PUMP.ML_MIN,
            finite_value=3,
            finite_units=self._devices.PUMP.ML_MIN
        )
        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{pump_index}": wdrw_c})
        
        while self._devices.PUMP.is_active(**{f"pump{pump_index}": True}):
            time.sleep(1)
        
        vc = self._devices.PUMP.make_valve_command(position=3)
        self._devices.PUMP.set_valves(**{f"pump{pump_index}": vc})
        
        time.sleep(1)
        
        wdrw_c = self._devices.PUMP.make_command(
            direction=self._devices.PUMP.INFUSE,
            rate_value=1,
            rate_units=self._devices.PUMP.ML_MIN,
            finite_value=3,
            finite_units=self._devices.PUMP.ML_MIN,
            record=True,
        )
        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{pump_index}": wdrw_c})

        time.sleep(1)

        while self._devices.PUMP.is_active(**{f"pump{pump_index}": True}):
            mL_dispensed = self._devices.PUMP.vol_pumped()[pump_index][0]
            r: Recordable
            r = getattr(self, f"pump{pump_index}_mL_added")
            r.update(value=mL_dispensed)
            time.sleep(1)

    def do_process(self):

        self.make_setpoints()
        self.make_recordables()

        self._devices.MIXER.set_sim_temperatures(values=(30,))
        self._devices.MIXER.set_sim_noise(values=(0.2,))
        self._devices.MIXER.set_sim_rates_of_change(values=(self.temperature_ramp_C_min.value,))

        self._devices.MIXER.start(record=True)

        def update_data(stop: threading.Event):
            while not stop.is_set():
                try:
                    self._data.update_data(mixer_index=0)
                    self._data.print_data()

                except Exception as e:
                    print(e)

                self._data.log_data_at_interval(interval_s=5, overwrite_file=True, update_before_log=False)
                time.sleep(1)

        stop_data_thread = threading.Event()
        data_thread = threading.Thread(target=update_data, args=(stop_data_thread,))
        data_thread.start()

        start_time = time.time()
        temperature_setpoint_reached = False
        temperature_rampdown_started = False
        temperature_hold_start_time = None

        pump_threads = [None, None, None]

        print(f"Starting mixer...")
        mc = self._devices.MIXER.make_command(
            direction=self._devices.MIXER.CLOCKWISE, 
            rpm=600
        )
        self._devices.MIXER.start_mixers(mixer0=mc)

        while not self.terminate.value:

            for i, s in enumerate([
                self.pump0_dose_delay_s,
                self.pump1_dose_delay_s,
                self.pump2_dose_delay_s,
            ]):
                if (
                    time.time() - start_time > s.value 
                    and pump_threads[i] is None
                    and temperature_setpoint_reached
                ):
                    print(f"Starting dose for pump: {i}")
                    pump_threads[i] = threading.Thread(target=self.dose_pump, args=(i,))
                    pump_threads[i].start()
                    time.sleep(0.5)

            if (
                self._data.temperature_C >= self.temperature_setpoint_C.value 
                and not temperature_setpoint_reached
            ):
                print(f"Temperature setpoint {self.temperature_setpoint_C.value} C reached.")
                temperature_setpoint_reached = True
                temperature_hold_start_time = time.time()
                self._devices.MIXER.set_sim_rates_of_change(values=(0,))

            if (
                temperature_setpoint_reached 
                and not temperature_rampdown_started
                and time.time() - temperature_hold_start_time > self.temperature_hold_min.value * 60
            ):
                print(f"Temperature hold completed, beginning ramp down...")
                temperature_rampdown_started = True
                self._devices.MIXER.set_sim_rates_of_change(values=(-1 * self.temperature_ramp_C_min.value,))

            if (
                temperature_rampdown_started
                and self._data.temperature_C <= 30
            ):
                print("Temperature rampdown complete...recipe completing.")
                self.terminate.value = True

            time.sleep(1)

        print(f"Stopping mixer...")
        self._devices.MIXER.stop_mixers(mixer0=True)
        self._devices.MIXER.set_sim_rates_of_change(values=(0,))

        stop_data_thread.set()
        data_thread.join()
            


if __name__ == "__main__":
    import config
    # local imports
    if not config.LAB_MODE_ENABLED:

        from aqueduct.aqueduct import Aqueduct

        aqueduct = Aqueduct('G', None, None, None)

        # make the Devices object
        devices = Devices.generate_dev_devices()

    else:

        # pass the aqueduct object
        aqueduct = globals().get('aqueduct')

        # pass the globals dictionary, which will have the
        # objects for the Devices already instantiated
        devices = Devices(**dict(pump_name="TRCX000001", mixer_name="EUST000001"))

    # make the Data object, pass the new devices object
    # and the aqueduct object
    data = Data(devices, aqueduct)

    # make the Process object
    process = ProcessHandler(
        devices_obj=devices,
        aqueduct=aqueduct,
        data=data,
    )

    """
    Add code here
    """
    process.do_process()
