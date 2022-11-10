import time
import enum
import json
import datetime
import threading

from .definitions import *
from .models import ReactionModel, PidModel
from .pid import PID

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import Setpoint, ALLOWED_DTYPES

import aqueduct.devices.pp.obj
import aqueduct.devices.pp.constants
import aqueduct.devices.ph3.obj
import aqueduct.devices.ph3.constants

from typing import List, Tuple, Callable, Union

from local.lib.ph_control.helpers import format_float


class Devices(object):
    """
    Class with members to contain each Aqueduct Device
    Object in the Setup.

    PUMP0 is the peristaltic pump dedicated to the addition of the base (device type PP)
    PUMP1 is the peristaltic pump dedicated to the addition of the acid (device type PP)
    PUMP2 is the peristaltic pump dedicated to the addition of the reagent (device type PP)
    PH_PROBE is the 3 x pH probe with one input active (device type PH3)

    In DEV MODE, we create 3 x `aqueduct.devices.pp.obj` and 1 x 
    `aqueduct.devices.ph3.obj` for easy access to the methods & constants for each device type.

    In LAB MODE, we associate each Device with the Name for the device
    that is saved on its firmware.
    """
    PUMP0: aqueduct.devices.pp.obj.PP = None
    PUMP1: aqueduct.devices.pp.obj.PP = None
    PUMP2: aqueduct.devices.pp.obj.PP = None
    PH_PROBE: aqueduct.devices.ph3.obj.PH3 = None

    def __init__(self, aq: aqueduct.core.aq.Aqueduct):
        self.PUMP0 = aq.devices.get(PUMP0_NAME)
        self.PUMP1 = aq.devices.get(PUMP1_NAME)
        self.PUMP2 = aq.devices.get(PUMP2_NAME)
        self.PH_PROBE = aq.devices.get(PH_PROBE_NAME)


class DataCacheItem(object):
    """
    A class to structure cached data. Mirrors the structure of the
    Data class.
    """
    pH_0: Union[float, None] = None
    pH_1: Union[float, None] = None
    pH_2: Union[float, None] = None
    timestamp: Union[float, None] = None  # timestamp of last update

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


class TrailingData(object):
    """
    Class used to format trailing rate-of-change and mean pH values.
    """
    pH_0_per_min: Union[float, None]
    pH_0_mean: Union[float, None]
    pH_1_per_min: Union[float, None]
    pH_1_mean: Union[float, None]
    pH_2_per_min: Union[float, None]
    pH_2_mean: Union[float, None]

    def __init__(
            self,
            pH_0_per_min: float,
            pH_0_mean: float,
            pH_1_per_min: float,
            pH_1_mean: float,
            pH_2_per_min: float,
            pH_2_mean: float,
    ):
        self.pH_0_per_min = pH_0_per_min
        self.pH_0_mean = pH_0_mean
        self.pH_1_per_min = pH_1_per_min
        self.pH_1_mean = pH_1_mean
        self.pH_2_per_min = pH_2_per_min
        self.pH_2_mean = pH_2_mean

    def as_string(self):
        return "pH[0] roc: {} pH/min., mean: {}\npH[1] roc: {} pH/min., mean: {}\npH[2] roc: {} " \
               "pH/min., mean: {},".format(
                    format_float(self.pH_0_per_min, 3),
                    format_float(self.pH_0_mean, 3),
                    format_float(self.pH_1_per_min, 3),
                    format_float(self.pH_1_mean, 3),
                    format_float(self.pH_2_per_min, 3),
                    format_float(self.pH_2_mean, 3),
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
    _length: int = 30

    # averaging length
    _averaging_length: int = 4

    # index 0 == pH_0 roc tolerance, 1 == pH_0 mean tolerance
    # index 2 == pH_1 roc tolerance, 3 == pH_1 mean tolerance
    # index 4 == pH_2 roc tolerance, 5 == pH_2 mean tolerance
    _tolerances: List[int] = [1000, 10, 1000, 10, 1000, 10]

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

        pH_0_roc_values, pH_0_values = [], []
        pH_1_roc_values, pH_1_values = [], []
        pH_2_roc_values, pH_2_values = [], []

        # set tolerance for time between reads to be acceptable for averaging
        delta_t_interval_s = 0.2
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
                        print(f"[WARNING calc_trailing_data, interval tolerance exceeded]: {_dt}s")
                        break

                # on the first iteration, we're setting the interval tolerance
                # mean as the time delta between the first and second points
                else:
                    delta_t_interval_s = _dt

                current_pH_0, prev_pH_0 = self._cache[-data_index].pH_0, self._cache[-(data_index + 1)].pH_0
                current_pH_1, prev_pH_1 = self._cache[-data_index].pH_1, self._cache[-(data_index + 1)].pH_1
                current_pH_2, prev_pH_2 = self._cache[-data_index].pH_2, self._cache[-(data_index + 1)].pH_2

                pH_0_roc_values.append(((current_pH_0 - prev_pH_0) / _dt) * 60.)
                pH_0_values.append(current_pH_0)

                pH_1_roc_values.append(((current_pH_1 - prev_pH_1) / _dt) * 60.)
                pH_1_values.append(current_pH_1)

                pH_2_roc_values.append(((current_pH_2 - prev_pH_2) / _dt) * 60.)
                pH_2_values.append(current_pH_2)

            if len(pH_0_roc_values) < 1:
                # not enough data to calculate
                print(f"[ERROR calc_trailing_data, not enough data to calculate]: {pH_0_values}, {pH_0_roc_values}")
                return None

            pH_0_roc_mean, pH_0_mean, pH_1_roc_mean, pH_1_mean, pH_2_roc_mean, pH_2_mean = 0, 0, 0, 0, 0, 0

            for measurement_id, measurement_list in enumerate([
                pH_0_roc_values,
                pH_0_values,
                pH_1_roc_values,
                pH_1_values,
                pH_2_roc_values,
                pH_2_values,
            ]):
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
                    pH_0_roc_mean = vals_mean

                elif measurement_id == 1:
                    pH_0_mean = vals_mean

                elif measurement_id == 2:
                    pH_1_roc_mean = vals_mean

                elif measurement_id == 3:
                    pH_1_mean = vals_mean

                elif measurement_id == 4:
                    pH_2_roc_mean = vals_mean

                elif measurement_id == 5:
                    pH_2_mean = vals_mean

            data = TrailingData(
                pH_0_mean=float(format_float(pH_0_mean, 3)),
                pH_0_per_min=float(format_float(pH_0_roc_mean, 3)),
                pH_1_mean=float(format_float(pH_1_mean, 3)),
                pH_1_per_min=float(format_float(pH_1_roc_mean, 3)),
                pH_2_mean=float(format_float(pH_2_mean, 3)),
                pH_2_per_min=float(format_float(pH_2_roc_mean, 3)),
            )

            return data

        except BaseException as e:
            if not isinstance(e, ZeroDivisionError):
                print(f"[ERROR calc_trailing_data, exception]: {str(e)}")
            else:
                print("[WARNING calc_trailing_data, ZeroDivisionError]")
            return None

    def calc_trailing_mean(self, index: int = 0, length: int = 3, precision: int = 3) -> Union[float, None]:
        try:
            length = min(length, len(self._cache))
            key = f"pH_{index}"
            return round(sum(getattr(a, key) for a in self._cache[-length::]) / length, precision)
        except BaseException as e:
            # don't let this break
            print(f"[ERROR calc_trailing_mean, exception]: {str(e)}")
            return None

    def calc_trailing_max(self, index: int = 0, length: int = 5) -> Union[float, None]:
        try:
            length = min(length, len(self._cache))
            key = f"pH_{index}"
            return max(getattr(a, key) for a in self._cache[-length::])
        except BaseException as e:
            # don't let this break
            print(f"[ERROR calc_trailing_max, exception]: {str(e)}")
            return None


class Data(object):
    """
    Class to help with logging and updating data.
    """
    pH_0: Union[float, None] = None
    pH_1: Union[float, None] = None
    pH_2: Union[float, None] = None
    timestamp: Union[float, None] = None

    log_timestamp: Union[float, None] = None  # timestamp of last write to log file
    _logging_interval_s: Union[int, float] = 5  # interval in seconds between writes to log file

    _cache: DataCache = None

    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process: "ProcessHandler" = None  # pointer to Process object

    def __init__(self, devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param devices_obj:
        :param aqueduct_obj:
        """
        self._devices = devices_obj
        self._aqueduct = aqueduct_obj

        self._is_lab_mode = False

        self._cache: DataCache = DataCache(self._devices)

    def update_data(self) -> None:
        """
        Method to update the global data dictionary.

        Uses the specific Device Object methods to get the
        data from memory.

        :return:
        """
        ph = self._devices.PH_PROBE.get_all_values()

        self.timestamp = time.time()
        self.pH_0 = ph[0]
        self.pH_1 = ph[1]
        self.pH_2 = ph[2]

        # save the data to the cache
        self._cache.cache(data=self)

    def log_data(self) -> None:
        """
        Method to log:

            pH

        at a given time.

        :return: None
        """
        pass
        # self._aqueduct.log(
        #     "pH_0: {0}, pH_1: {1}, pH_2: {2}".format(
        #         format_float(self.pH_0, 3),
        #         format_float(self.pH_1, 3),
        #         format_float(self.pH_2, 3),
        #     )
        # )

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

        :param update_before_log:
        :param overwrite_file:
        :param interval_s:
        :return:
        """

        if not interval_s:
            interval_s = self._logging_interval_s

        now = time.time()

        if self.log_timestamp is not None and now < (self.log_timestamp + interval_s):
            return

        if update_before_log is True:
            self.update_data()

        self.log_data()

        if overwrite_file is True:
            self._process.save_log_file()

        self.log_timestamp = now

    def print_data(self):
        try:
            print(self._cache.calc_trailing_data(length=5).as_string())

        except Exception as e:  # noqa
            print(f"[ERROR: print_data]: {str(e)}")

    @property
    def cache(self):
        return self._cache


class ReactionStation(object):
    """
    
    """

    class Enabled(enum.Enum):
        """
        Enum to enable/disable a Reaction Station. If a ReactionStation is disabled, the
        ReactionProcessHandler will not take any action. If the ReactionStation is enabled,
        the ReactionProcessHandler will monitor the phases of the ReactionStation and
        execute the required steps sequentially.
        """
        DISABLED = 0
        ENABLED = 1

    class Phase(enum.Enum):
        """
        An enumeration of Phases for the ReactionStation Process.
        """

        # state upon recipe start
        INITIALIZED = 0

        # before starting the reaction, the output tubing lines for 
        # the base, acid, and reagent may be primed to ensure 
        # that liquid is drawn all the way to the tubing outlet
        PRIME_TUBING = 1

        # before proceeding with base addition, wait for the 
        # rate of change of pH in the reaction vessel to stabilize
        WAIT_FOR_PH_EQUIL = 2

        # set monomer valve to waste, infuse pump completely at
        # priming_infuse_rate_(pump)_ml_min
        INITIAL_BASE_ADDITION = 3

        # phase 2 complete!
        REACTION_COMPLETE = 99

    class CurrentPhaseStatus(enum.Enum):
        """
        Track the status of the current phase.
        """
        NOT_STARTED = 0
        STARTED = 1
        COMPLETE = 2

    # each ReactionProcess has an index for the ReactionProcessHandler
    # list of stations
    index: int = 0

    # each ReactionProcess can be set to active or inactive
    # when the ProcessHandler encounters an inactive process
    # it won't take any action, to enable toggling of station's
    # enabled state we use an Aqueduct Setpoint
    enabled_setpoint: Setpoint = None

    # each ReactionProcess has a phase that tracks the infusion
    # process for monomer and initiator, to enable toggling of station's
    # current phase we use an Aqueduct Setpoint
    phase_setpoint: Setpoint = None

    # create a Setpoint to allow toggling of the pH setpoint value
    pH_setpoint: Setpoint = None

    # track the status of the current phase using one of the CurrentPhaseStatus
    # enum's members
    current_phase_status: int = CurrentPhaseStatus.NOT_STARTED.value

    # logging
    logging_enabled: bool = True
    log_file_name: str = "reaction_"

    # for on/off control
    dose_counter: int = 0
    dose_totalizer_ml: float = 0.
    max_dose_ml: float = 0.5
    min_dose_ml: float = 0.01

    _is_dosing: bool = False
    _last_dose_volume_ml: float = None
    _last_dose_start_ph: float = None
    _last_dose_end_ph: float = None

    # for PID control
    _in_tolerance_count: int = 0
    _tolerance: float = 0.05
    _wind_up_tolerance_count: int = 0
    _wind_up_tolerance: float = 0.1

    # reference to the Global aqueduct instance
    _devices: Devices = None
    _aqueduct: Aqueduct = None
    _data: Data = None
    _model: ReactionModel = None

    def __init__(
            self,
            index: int = 0,
            devices_obj: Devices = None,
            aqueduct: Aqueduct = None,
            data: Data = None,
    ):

        self.index = index

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

        if isinstance(data, Data):
            self._data = data

    def __str__(self):
        return f"Station {self.index}: enabled={self.enabled_setpoint.value}, phase={self.phase_setpoint.value}"

    def make_setpoints(self) -> None:
        """
        Method used to generate the enable_setpoint and phase_setpoint.

        :return:
        """

        self.enabled_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_enabled",
            value=ReactionStation.Enabled.ENABLED.value,
            dtype=int.__name__
        )

        self.phase_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_phase",
            value=ReactionStation.Phase.INITIALIZED.value,
            dtype=int.__name__
        )

        self.pH_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_pH_setpoint",
            value=8.5,
            dtype=float.__name__
        )

    @staticmethod
    def phase_to_str(phase: int) -> str:
        """
        Helper method to convert the Phase Enum number to a readable string.

        :param phase:
        :return: human readable phase description
        """
        if phase == ReactionStation.Phase.INITIALIZED.value:
            return "initialized"
        elif phase == ReactionStation.Phase.PRIME_TUBING.value:
            return "initial purge to waste"

    def set_current_phase_status(self, phase_status: CurrentPhaseStatus) -> None:
        self.current_phase_status = phase_status.value

    def calc_last_dose_dph_dml(self) -> Union[float, None]:
        try:
            return round(
                (self._last_dose_end_ph - self._last_dose_start_ph) / self._last_dose_volume_ml,
                4
            )
        except BaseException as e:  # noqa
            print(f"[ERROR calc_last_dose_dpH_dml error]: {str(e)}")
            return None

    def _phase_helper(
            self,
            do_if_not_started: Callable = None,
            next_phase: "ReactionStation.Phase" = None,
            do_if_not_started_kwargs: dict = None
    ) -> None:
        """
        Helper to avoid repeating phase block logic.

        Pass a method `do_if_not_started` to perform if the current phase has not been started
        and a `next_phase` :class:ReactionStation.Phase to assign if the current phase has been
        started and is complete.

        :param do_if_not_started:
        :param next_phase:
        :param do_if_not_started_kwargs:
        :return:
        """
        # if the current phase status is NOT_STARTED, mark the phase STARTED and check to see
        # whether there is a `do_if_not_started` function associated with the step
        if self.current_phase_status == ReactionStation.CurrentPhaseStatus.NOT_STARTED.value:
            self.set_current_phase_status(ReactionStation.CurrentPhaseStatus.STARTED)
            if do_if_not_started is not None:
                if do_if_not_started_kwargs is not None:
                    do_if_not_started(**do_if_not_started_kwargs)
                else:
                    do_if_not_started()
        # if the phase has already STARTED, set the current phase back to NOT_STARTED
        # and advance to the next step
        elif self.current_phase_status == ReactionStation.CurrentPhaseStatus.STARTED.value:
            self.set_current_phase_status(ReactionStation.CurrentPhaseStatus.NOT_STARTED)
            self.phase_setpoint.update(next_phase.value)

    def do_next_phase(self):

        # aliases for the ReactionStation.Phase Enum and the ReactionStation.CurrentPhaseStatus Enum to
        # avoid typing for each comparison
        PC = ReactionStation.Phase

        # flag to repeat the "do_next_phase" loop after printing the status update
        # initialized to False
        repeat: bool = False

        # start of a logging string that tracks the phase and status change
        log_str: str = f"Station {self.index}: {ReactionStation.phase_to_str(self.phase_setpoint.value)}" \
                       f"({self.phase_setpoint.value}[{self.current_phase_status}]) -> "

        if self.phase_setpoint.value == PC.INITIALIZED.value:
            self._phase_helper(
                do_if_not_started=None,
                next_phase=PC.PRIME_TUBING
            )
            repeat = True

        elif self.phase_setpoint.value == PC.PRIME_TUBING.value:
            self._phase_helper(
                do_if_not_started=self.prime_tubing,
                next_phase=PC.WAIT_FOR_PH_EQUIL
            )

        elif self.phase_setpoint.value == PC.REACTION_COMPLETE.value:
            self.enabled_setpoint.update(ReactionStation.Enabled.DISABLED.value)

        log_str += f"{ReactionStation.phase_to_str(self.phase_setpoint.value)}" \
                   f"({self.phase_setpoint.value}[{self.current_phase_status}])"

        print(log_str)

        if self.logging_enabled:
            self._aqueduct.log(log_str)
            self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

        if repeat is True:
            self.do_next_phase()

    def prime_tubing(self) -> None:
        """
        Flash a user input asking if the operator wishes to prime the acid, base, and reagent 
        tubing lines.

        :return:
        """

        aq_input = self._aqueduct.input(
            message="Do you want to prime the pump tubing lines?",
            pause_recipe=True,
            input_type=UserInputTypes.BUTTONS.value,
            options={"Yes": 1, "No": 0},
            dtype=int.__name__,
        )

        do_prime = aq_input.get_value()

        if do_prime == 1:

            for name, pump in zip(
                    ("base pump", "acid pump", "reagent pump"),
                    (self._devices.PUMP0, self._devices.PUMP1, self._devices.PUMP2)
            ):
                input_rows = [
                    dict(
                        hint=f"priming volume (mL)",
                        value=0,
                        dtype=float.__name__,
                        name="priming_vol_ml"
                    ),
                    dict(
                        hint=f"priming rate (mL/min)",
                        value=0,
                        dtype=float.__name__,
                        name="priming_rate_ml_min"
                    ),
                ]

                tabular_ipt = self._aqueduct.input(
                    message=f"""
                    Place the outlet of the tubing for the {name} in a collection vessel. 
                    Enter the volume (in mL) and rate (in mL/min) that you wish to prime.""",
                    input_type="table",
                    dtype="str",
                    rows=input_rows,
                )

                input_val = tabular_ipt.get_value()

                confirmed_values = json.loads(input_val)

                priming_vol_ml = confirmed_values[0].get('value')
                priming_rate_ml_min = confirmed_values[1].get('value')

                pump.start(
                    mode=pump.FINITE,
                    direction=pump.FORWARD,
                    rate_value=priming_rate_ml_min,
                    rate_units=pump.ML_MIN,
                    finite_value=priming_vol_ml,
                    finite_units=pump.ML
                )

    def wait_for_ph_equilibrium(self) -> None:
        """
        Flash a user input asking if the operator wishes to prime the acid, base, and reagent 
        tubing lines.

        :return:
        """
        pass

    def maybe_dose_base(
        self,
        index,
        pump: "aqueduct.devices.pp.obj.PP",
        pH_setpoint: float,
        reaction_model: ReactionModel,
        pH_index: int = 0,
    ):

        self._is_dosing = True

        try:

            start_dose_pH: float = self._data.cache.calc_trailing_mean(index=pH_index, length=2)

            if start_dose_pH is not None and start_dose_pH < pH_setpoint:
                # we're doing a dose...
                maybe_dpH_dml = self.calc_last_dose_dph_dml()

                dose_ml = 0.1

                if maybe_dpH_dml is not None:
                    # if the dpH/dml ratio is negative (last dose had no impact...),
                    # double the dose volume
                    if maybe_dpH_dml <= 0:
                        dose_ml = 2 * self._last_dose_volume_ml
                    # otherwise...
                    else:
                        # calculate the new dose volume by targeting the pH setpoint
                        # + 0.1 pH based on the last dpH/dmL ratio
                        new_dose_ml = ((pH_setpoint + 0.1) - start_dose_pH) / maybe_dpH_dml
                        # limit the new dose volume to be at most twice the volume of the last dose
                        dose_ml = min(new_dose_ml, 2 * self._last_dose_volume_ml)
                    # limit the dose volume to be between the min and max dose volumes
                    dose_ml = round(max(min(self.max_dose_ml, dose_ml), self.min_dose_ml), 4)
                    print(f"[Station {index}] adjusting dose to {dose_ml} mL")

                print(f"[Station {index}] Dose {self.dose_counter} of NaOH, "
                      f"total mL of NaOH added: {self.dose_totalizer_ml:.3f}")

                pump.start(
                    mode=pump.FINITE,
                    direction=pump.FORWARD,
                    rate_value=300,
                    rate_units=pump.RPM,
                    finite_value=dose_ml,
                    finite_units=pump.ML,
                )

                n = 0
                while n < 50 and pump.rpm() > 0:
                    time.sleep(1)
                    n += 1

                self.dose_counter += 1
                self.dose_totalizer_ml += dose_ml
                self._last_dose_start_ph = start_dose_pH
                self._last_dose_volume_ml = dose_ml

                reaction_model.add_dose(dose_ml, ph_index=pH_index)

                time.sleep(3)

                i = 0
                # wait for 30 seconds or until the pH is no longer increasing
                while i < 30:
                    trailing_data = self._data.cache.calc_trailing_data(length=3)
                    if trailing_data is not None:
                        # if the mean of the last 5 dpH/dt data points is
                        # less than 0.5 pH/min, then break from the while loop
                        if getattr(trailing_data, f"pH_{pH_index}_per_min") < 0.5:
                            break

                    i += 1
                    time.sleep(1)

                # record the end dose pH as the mean of the last 2 data points
                self._last_dose_end_ph = self._data.cache.calc_trailing_max(index=pH_index, length=10)

        except BaseException as e:
            print(f"[ERROR] maybe_dose_base exception: {str(e)}")

        self._is_dosing = False

    def maybe_change_rate(
            self,
            index,
            pump: "aqueduct.devices.pp.obj.PP",
            pH_setpoint: float,
            pid_controller: PID,
            pid_model: PidModel,
            pH_index: int = 0,
    ):

        self._is_dosing = True

        try:

            current_pH: float = self._data.cache.calc_trailing_mean(index=pH_index, length=2)
            pid_controller.setpoint = pH_setpoint

            target_rate_ml_min = round(pid_controller(current_pH), 5)

            print(f"[Station {index}] target rate: {target_rate_ml_min} (mL/min), target pH: {pH_setpoint}")

            pump.change_speed(
                rate_value=target_rate_ml_min,
                rate_units=pump.ML_MIN,
            )

            pid_model.change_rate(target_rate_ml_min)

            last_error = pid_controller.get_last_error()
            if last_error is not None:
                if abs(last_error) < self._tolerance:
                    self._in_tolerance_count += 1
                else:
                    self._in_tolerance_count = 0

                if abs(last_error) < self._wind_up_tolerance:
                    self._wind_up_tolerance_count += 1
                else:
                    self._wind_up_tolerance_count = 0

                if self._in_tolerance_count > 30:
                    pid_controller.period_s = 2
                else:
                    pid_controller.period_s = 1

                if self._wind_up_tolerance_count == 20:
                    print("Adjusting PID controller after initialization...")
                    pid_controller.tunings = (1.0, 0.025, 0.15)

        except BaseException as e:
            print(f"[ERROR] maybe_change_rate exception: {str(e)}")

        self._is_dosing = False


class ProcessHandler(object):
    """
    Class to handle processing each of the reaction stations.
    """

    stations: Tuple[ReactionStation] = ()

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
    _models: List[Union[ReactionModel, PidModel]] = None

    def __init__(
            self,
            devices_obj: Devices = None,
            aqueduct: Aqueduct = None,
            data: Data = None
    ):

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

        if isinstance(data, Data):
            self._data = data
            data._process = self

    def make_stations(self, number_stations: int = 1) -> None:

        stations = []

        for i in range(0, number_stations):
            stations.append(
                ReactionStation(
                    index=i,
                    devices_obj=self._devices,
                    aqueduct=self._aqueduct,
                    data=self._data,
                ),
            )

        self.stations = tuple(stations)

        s: ReactionStation
        for s in self.stations:
            s.make_setpoints()

    def print_all_stations(self):
        """
        Method to print the status of each station.

        :return:
        """
        for s in self.stations:
            print(s)

    def save_log_file(self):
        pass
        # self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

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

    def on_off_control(
            self,
            pumps: Tuple[
                "aqueduct.devices.pp.obj.PP",
                "aqueduct.devices.pp.obj.PP",
                "aqueduct.devices.pp.obj.PP"
            ] = (None, None, None),
            pH_probe_indices: Tuple[int, int, int] = (0, 1, 2),
    ):

        self.log_file_name = f"data_{datetime.datetime.now().isoformat()}"
        
        # create a Setpoint to terminate the Recipe
        terminate_sp = self._aqueduct.setpoint(
            name="terminate",
            value=False,
            dtype=bool.__name__,
        )

        if len(pumps) != len(pH_probe_indices):
            raise ValueError("Number of `pumps` must equals number of `pH_probe_indices`!")

        self.make_stations(number_stations=len(pumps))

        self._models = []

        for i in range(0, len(pumps)):

            # create a `PidModel` to simulate feedback
            self._models.append(ReactionModel(
                devices_obj=self._devices,
                aqueduct=self._aqueduct,
                data=self._data,
            ))

            self._models[i].start_reaction()

        self._devices.PH_PROBE.set_sim_values(values=(6, 6, 6))
        self._devices.PH_PROBE.set_sim_rates_of_change(values=(
            self._models[0].calc_rate_of_change(),
            self._models[1].calc_rate_of_change(),
            self._models[2].calc_rate_of_change()
        ))
        self._devices.PH_PROBE.set_sim_noise(values=(0.001, 0.001, 0.001))

        # start recording data from the pH probe
        self._devices.PH_PROBE.start(
            interval_s=1,
            record=True
        )

        # wait 1 s to allow for data
        time.sleep(1)

        # this method, dedicated to acquiring, printing, and 
        # logging data at a 1 second interval, will be run 
        # in the `data_thread` Thread
        def update_data(stop: threading.Event):
            while not stop.is_set():
                try:
                    self._data.update_data()
                    self._data.print_data()

                except Exception as e:
                    print(e)

                self._data.log_data_at_interval(interval_s=5, overwrite_file=True, update_before_log=False)
                time.sleep(1)

        # define an event to signal the data_thread to quit
        stop_data_thread = threading.Event()
        data_thread = threading.Thread(target=update_data, args=(stop_data_thread,))
        data_thread.start()

        while not terminate_sp.value:

            for i, s in enumerate(self.stations):

                s: ReactionStation
                if not s._is_dosing and s.enabled_setpoint.value:  # noqa
                    t = threading.Thread(
                        target=s.maybe_dose_base,
                        args=(
                            i,
                            pumps[i],
                            s.pH_setpoint.value,
                            self._models[i],
                            i,
                        ),
                        daemon=True,
                    )
                    t.start()

            time.sleep(1)

        print("On-Off Control complete!")

        stop_data_thread.set()
        data_thread.join()

    def pid_control(
            self,
            initial_rate_rpm: float = 1,
            pumps: Tuple[
                "aqueduct.devices.pp.obj.PP",
                "aqueduct.devices.pp.obj.PP",
                "aqueduct.devices.pp.obj.PP"
            ] = (None, None, None),
            pH_probe_indices: Tuple[int, int, int] = (0, 1, 2),
            output_limits: Tuple[Tuple] = (),
    ):

        self.log_file_name = f"data_{datetime.datetime.now().isoformat()}"
        
        # create a Setpoint to terminate the Recipe
        terminate_sp = self._aqueduct.setpoint(
            name="terminate",
            value=False,
            dtype=bool.__name__,
        )

        if len(pumps) != len(pH_probe_indices):
            raise ValueError("Number of `pumps` must equals number of `pH_probe_indices`!")

        self.make_stations(number_stations=len(pumps))

        self._models = []
        pid_controllers = []
        rates_of_change = []

        for i in range(0, len(pumps)):
            # create a Setpoint to adjust the proportional PID constant
            kp_sp = self._aqueduct.setpoint(
                name=f"k_p_{i}",
                value=1,
                dtype=float.__name__,
            )

            # create a Setpoint to adjust the integral PID constant
            ki_sp = self._aqueduct.setpoint(
                name=f"k_i_{i}",
                value=0.05,
                dtype=float.__name__,
            )

            # create a Setpoint to adjust the derivative PID constant
            kd_sp = self._aqueduct.setpoint(
                name=f"k_d_{i}",
                value=0.55,
                dtype=float.__name__,
            )

            # create a `PidModel` to simulate feedback
            self._models.append(PidModel(
                pH_probe_index=pH_probe_indices[i],
                devices_obj=self._devices,
                aqueduct=self._aqueduct,
                data=self._data,
            ))

            self._models[i].start_reaction()

            rates_of_change.append(self._models[i].calc_rate_of_change(0))

            if output_limits and output_limits[i]:
                low, up = output_limits[i][0],  output_limits[i][1]
            else:
                low, up = 0, 20

            pid_controllers.append(PID(
                k_p=kp_sp.value,
                k_i=ki_sp.value,
                k_d=kd_sp.value,
                period_s=1,
                output_limits=(low, up),  # limit the max rate to 20 mL/min
                controllable_limits=(0.5, 0.5,)  # controllable range is setpoint +/- 0.5 pH to use integral term
            ))

            # any time a user changes the Kp, Ki, or Kd values from the interface,
            # we want to make sure to update the values in our PID controller
            def handle_update_controller():
                pid_controllers[i].tunings = (kp_sp.value, ki_sp.value, kd_sp.value)

            # register the on_change callback to update the Kp, Ki, and Kd values
            kp_sp.on_change = handle_update_controller
            ki_sp.on_change = handle_update_controller
            kd_sp.on_change = handle_update_controller

        # this method, dedicated to acquiring, printing, and 
        # logging data at a 1 second interval, will be run 
        # in the `data_thread` Thread
        def update_data(stop: threading.Event):
            while not stop.is_set():
                try:
                    self._data.update_data()
                    self._data.print_data()

                except Exception as e:
                    print(e)

                self._data.log_data_at_interval(interval_s=5, overwrite_file=True, update_before_log=False)
                time.sleep(1)

        self._devices.PH_PROBE.set_sim_values(values=(6, 6, 6))
        self._devices.PH_PROBE.set_sim_rates_of_change(values=rates_of_change)
        self._devices.PH_PROBE.set_sim_noise(values=(0.0001, 0.0001, 0.0001))
        self._devices.PH_PROBE.clear_recorded()
        self._devices.PH_PROBE.update_record(True)

        # start recording data from the pH probe
        self._devices.PH_PROBE.start(
            interval_s=1,
            record=True
        )

        # define an event to signal the data_thread to quit
        stop_data_thread = threading.Event()
        data_thread = threading.Thread(target=update_data, args=(stop_data_thread,))
        data_thread.start()

        # wait 1 s to allow for data
        time.sleep(1)

        # start the pumps at 1 rpm in the forward (clockwise) direction
        for p in pumps:
            p.start(
                direction=p.FORWARD,
                mode=p.CONTINUOUS,
                rate_value=initial_rate_rpm,
                rate_units=p.RPM,
                record=True,
            )

        while not terminate_sp.value:

            for i, s in enumerate(self.stations):

                s: ReactionStation
                if not s._is_dosing and s.enabled_setpoint.value:  # noqa
                    t = threading.Thread(
                        target=s.maybe_change_rate,
                        args=(
                            i,
                            pumps[i],
                            s.pH_setpoint.value,
                            pid_controllers[i],
                            self._models[i],
                            i,
                        ),
                        daemon=True,
                    )
                    t.start()

            time.sleep(1)

        print("PID Control complete!")

        stop_data_thread.set()
        data_thread.join()
