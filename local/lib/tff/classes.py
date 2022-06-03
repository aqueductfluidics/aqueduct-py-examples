import datetime
import time
import pprint
import inspect

import local.lib.tff.helpers
import local.lib.tff.methods
import local.lib.tff.models
import local.lib.tff.alarms
import local.lib.tff.data
from local.lib.tff.definitions import *

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import Setpoint, ALLOWED_DTYPES

import aqueduct.devices.mfpp.obj
import aqueduct.devices.mfpp.constants
import aqueduct.devices.ohsa.obj
import aqueduct.devices.ohsa.constants
import aqueduct.devices.scip.obj
import aqueduct.devices.scip.constants
import aqueduct.devices.pv.obj
import aqueduct.devices.pv.constants

from typing import Union


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
    PUMP1: aqueduct.devices.mfpp.obj.MFPP = None
    PUMP2: aqueduct.devices.mfpp.obj.MFPP = None
    PUMP3: aqueduct.devices.mfpp.obj.MFPP = None
    SCIP: aqueduct.devices.scip.obj.SCIP = None
    OHSA: aqueduct.devices.ohsa.obj.OHSA = None
    PV: aqueduct.devices.pv.obj.PV = None

    def __init__(self, aq: aqueduct.core.aq.Aqueduct):
        self.PUMP1 = aq.devices.get(PUMP1_NAME)
        self.PUMP2 = aq.devices.get(PUMP2_NAME)
        self.PUMP3 = aq.devices.get(PUMP3_NAME)
        self.OHSA = aq.devices.get(OHSA_NAME)
        self.SCIP = aq.devices.get(SCIP_NAME)
        self.PV = aq.devices.get(PV_NAME)


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


class Watchdog(object):
    """
    The Watchdog class will have access to all of the Alarm
    classes.

    """

    over_pressure_alarm: local.lib.tff.alarms.OverPressureAlarm
    low_pressure_alarm: local.lib.tff.alarms.LowP3PressureAlarm
    vacuum_condition_alarm: local.lib.tff.alarms.VacuumConditionAlarm
    low_buffer_vessel_alarm: local.lib.tff.alarms.BufferVesselEmptyAlarm
    low_retentate_vessel_alarm: local.lib.tff.alarms.RetentateVesselLowAlarm
    volume_accumulation_alarm: local.lib.tff.alarms.VolumeAccumulationAlarm

    _devices: Devices
    _aqueduct: Aqueduct
    _data: "local.lib.tff.data.Data"

    def __init__(self, data_obj: "local.lib.tff.data.Data", devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: "local.lib.tff.data.Data" = data_obj
        self._devices: Devices = devices_obj
        self._aqueduct: Aqueduct = aqueduct_obj

        self.over_pressure_alarm = local.lib.tff.alarms.OverPressureAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_pressure_alarm = local.lib.tff.alarms.LowP3PressureAlarm(
            self._data, self._devices, self._aqueduct)
        self.vacuum_condition_alarm = local.lib.tff.alarms.VacuumConditionAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_buffer_vessel_alarm = local.lib.tff.alarms.BufferVesselEmptyAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_retentate_vessel_alarm = local.lib.tff.alarms.RetentateVesselLowAlarm(
            self._data, self._devices, self._aqueduct)
        self.volume_accumulation_alarm = local.lib.tff.alarms.VolumeAccumulationAlarm(
            self._data, self._devices, self._aqueduct)

    def assign_process_to_alarms(self, process):
        """
        Set the reference to the Process instance for all of the Watchdog's alarms.

        :param process:
        :return:
        """
        for n, m in self.__dict__.items():
            a = getattr(self, n)
            if isinstance(a, local.lib.tff.alarms.Alarm):
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
            if isinstance(a, local.lib.tff.alarms.Alarm):
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

    DEFAULT_PINCH_VALVE_LOCK_IN_MIN = 4.  # minutes

    hub_sn: int = None
    lab_mode: bool

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
    _data: "local.lib.tff.data.Data" = None
    _aqueduct: Aqueduct = None
    _setpoints: Setpoints = None
    _watchdog: Watchdog = None
    _model: local.lib.tff.models = None

    def __init__(
            self,
            devices_obj: Devices = None,
            data: "local.lib.tff.data.Data" = None,
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
        # if isinstance(self._aqueduct, Aqueduct):
            # self.hub_sn = self._aqueduct.hub_sn
            # self.lab_mode = self._aqueduct.is_lab_mode()

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

        print("[PHASE (INIT)] Initializing Operation...")

        print("[PHASE (INIT)] Stopping all Pumps.")

        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:
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
            print("[PHASE (INIT)] Taring SCALE2.")
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
            print("[PHASE (INIT)] Taring SCALE3.")
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
                message="Enter the initial concentration target concentration in grams "
                        "per liter (g/L). Press <b>submit</b> to continue.",
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

            print("[PHASE (INIT)] Initial Concentration target mass (g) for Scale 3 (permeate scale): {}".format(
                local.lib.tff.helpers.format_float(self.init_conc_target_mass_g, 2)
            ))

    def do_init_transfer(self):

        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:

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
            print("[PHASE (INIT)] Taring SCALE1.")
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
            print("[PHASE (INIT)] Taring SCALE1.")
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
                    print("[PHASE (INIT)] Actual amount transferred: {:.2f} g".format(self._data.W1))
                    break

                if isinstance(self._data.W1, float) and self._data.W1 > self.initial_transfer_volume:
                    self._devices.PUMP2.stop()
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
                )

                if loops == 5:
                    print("[PHASE (INIT)] Waiting for {} more seconds...".format(int((timeout - time.time()))))
                    loops = 0

                # increment loops by 1
                loops += 1

            self._data.update_data()

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
            print("[PHASE (INIT)] Taring SCALE1.")
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

        print("[PHASE (INIT)] Beginning Initial Concentration Step 1: Pump 1 Ramp Up.")
        local.lib.tff.methods.pump_ramp(
            interval_s=1,
            pump=self._devices.PUMP1,
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
        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("[PHASE (INIT)] Beginning Initial Concentration Step 2: Pump 2 and Pump 3 Ramp Up.")
        else:
            print("[PHASE (INIT)] Beginning Initial Concentration Step 2: Pump 3 Ramp Up.")

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
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog
        )

        """
        ************************
            Initial Concentration
            Step 3: Pinch Valve Lock In      
        ************************
        """
        # if we hit the target mass during the ramp, skip the pinch valve lock in
        if status != STATUS_TARGET_MASS_HIT:
            time.sleep(5)
            print("[PHASE (INIT)] Beginning Initial Concentration Step 3: Pinch Valve Lock-In.")
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
        # avoid lag in waiting here if init conc hit in ramp by jumping straight through
        # if we already hit the target mass, skip jump straight through init conc wait
        if status != STATUS_TARGET_MASS_HIT:
            print("[PHASE (INIT)] Waiting for initial concentration SCALE3 target mass {:.2f} g".format(
                self.init_conc_target_mass_g)
            )

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
                    print("[PHASE (INIT)] Timed out waiting for initial concentration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
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

        print("[PHASE (INIT)] Initial Concentration Step complete.")

        # Set PUMP2 (if present) and PUMP3 to no flow. Pump 1 will continue to operate at
        # target flowrate between Concentration and Diafiltration
        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("[PHASE (INIT)] Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("[PHASE (INIT)] Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording init conc mass
        print("[PHASE (INIT)] Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.init_conc_actual_mass_g = self._data.W3

        print("[PHASE (INIT)] End Initial Concentration SCALE3 mass: {}g".format(self.init_conc_actual_mass_g))

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
        print("[PHASE (INIT->DIA)] Taring SCALE3.")
        self._devices.OHSA.tare(SCALE3_INDEX)
        time.sleep(5)

        # open pinch valve
        print("[PHASE (INIT->DIA)] Opening pinch valve.")
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
                    watchdog=self._watchdog,
                    process=self,
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
                    watchdog=self._watchdog,
                    process=self,
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

            print("[PHASE (INIT->DIA)] Diafiltration 1 target mass (g) for SCALE3: {}".format(
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

        print("[PHASE (DIA)] Beginning Diafiltration Step 1: PUMP2 and PUMP3 Ramp Up.")
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
            time.sleep(5)
            print("[PHASE (DIA)] Beginning Diafiltration Step 2: Pinch Valve Lock-In.")
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
            print("[PHASE (DIA)] Waiting for diafiltration SCALE3 target mass {:.2f}g".format(
                self.diafilt_target_mass_g)
            )

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
                    print("[PHASE (DIA)] Timed out waiting for diafiltration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
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

        print("[PHASE (DIA)] Diafiltration Step complete.")

        # Set PUMP2 (if present) and PUMP3 to no flow. Pump 1 will continue to operate at
        # target flowrate between Diafiltration and Final Conc.
        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("[PHASE (DIA)] Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("[PHASE (DIA)] Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording diafiltration mass
        print("[PHASE (DIA)] Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.diafilt_actual_mass_g = self._data.W3

        print("[PHASE (DIA)] End Diafiltration SCALE3 mass: {}g".format(self.diafilt_actual_mass_g))

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
        print("[PHASE (DIA->FINAL)] Taring SCALE3 (permeate scale).")
        self._devices.OHSA.tare(SCALE3_INDEX)
        time.sleep(5)

        # open pinch valve
        print("[PHASE (DIA->FINAL)] Opening pinch valve.")
        self._devices.PV.set_position(pct_open=0.4)

        if self.do_prompts:
            # Aqueduct input for final concentration target
            ipt = self._aqueduct.input(
                message="Enter the final concentration target in grams per liter (g/L). "
                        "Press <b>submit</b> to continue.",
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

        print("[PHASE (DIA->FINAL)] Final Concentration target mass (g) for SCALE3: {}".format(
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

        print("[PHASE (FINAL)] Beginning Final Concentration Step 1: PUMP3 Ramp Up.")

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
            print("[PHASE (FINAL)] Setting pinch valve.")
            self._devices.PV.set_position(pct_open=0.3)
            time.sleep(5)
            print("[PHASE (FINAL)] Beginning Final Concentration Step 2: Pinch Valve Lock-In.")
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
            print("[PHASE (FINAL)] Waiting for final concentration SCALE3 target mass {:.2f}g".format(
                self.final_conc_target_mass_g)
            )

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
                    print("[PHASE (FINAL)] Timed out waiting for final concentration SCALE3 target mass.")
                    break

                local.lib.tff.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
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

        print("[PHASE (FINAL)] Final Concentration Step complete.")

        # stop Pumps 2 (if present) and 3
        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:
            print("[PHASE (FINAL)] Stopping PUMP2 and PUMP3.")
            self._devices.PUMP2.stop()
        else:
            print("[PHASE (FINAL)] Stopping PUMP3.")
        self._devices.PUMP3.stop()

        # time delay to allow for pumps to decelerate to a stop before
        # recording final conc mass
        print("[PHASE (FINAL)] Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.final_conc_actual_mass_g = self._data.W3

        print("[PHASE (FINAL)] End Final Concentration SCALE3 mass: {}g".format(self.final_conc_actual_mass_g))

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
        print("[PHASE (CLN)] Beginning clean-up, open pinch valve to 30%")
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
        print("[PHASE (CLN)] Stopping PUMP1.")
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
        print("[PHASE (WASH)] Washing for 5 minutes.")

        # infinite loop until we meet a break condition
        while True:

            # check to see whether we've timed out
            if datetime.datetime.utcnow() > timeout:
                print("[PHASE (WASH)] Wash Complete.")
                break

            local.lib.tff.methods.monitor(
                interval_s=1,
                adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog,
                process=self,
            )

        # stop Pump 1
        print("[PHASE (WASH)] Stopping PUMP1.")
        self._devices.PUMP1.stop()

        # save log file
        self.add_process_info_to_log()
        self._aqueduct.save_log_file(self.log_file_name, timestamp=True)

        # stop balance and pressure A/D
        self._devices.OHSA.stop()
        self._devices.SCIP.stop()

        print("[PHASE (WASH)] TFF Full Operation complete!")

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
                watchdog=self._watchdog,
                process=self,
            )

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
                    watchdog=self._watchdog,
                    process=self,
                )

                reset_sim_pressures_to_3_psi()
                break
