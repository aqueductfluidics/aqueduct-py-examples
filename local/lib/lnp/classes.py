import datetime
import inspect
import pprint
import time
from typing import Union

import aqueduct.devices.mfpp.constants
import aqueduct.devices.mfpp.obj
import aqueduct.devices.mfm.constants
import aqueduct.devices.mfm.obj
import aqueduct.devices.sol4.constants
import aqueduct.devices.sol4.obj
import aqueduct.devices.scip.constants
import aqueduct.devices.scip.obj
import aqueduct.devices.tempx.constants
import aqueduct.devices.tempx.obj
import local.lib.lnp.alarms
import local.lib.lnp.devices
import local.lib.lnp.data
import local.lib.lnp.helpers
import local.lib.lnp.methods
import local.lib.lnp.models
import local.lib.lnp.pid
from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import ALLOWED_DTYPES, Setpoint
from local.lib.lnp.definitions import *


class Setpoints(object):
    """
    Class that will contain all Aqueduct Setpoints
    for the LNP setup.

    Setpoints will display as User Params on the
    Recipe Editor screen and can be edited
    by a user.

    """
    pinch_valve_control_active: Setpoint = None
    P3_target_pressure: Setpoint = None
    k_p: Setpoint = None
    k_i: Setpoint = None
    k_d: Setpoint = None

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

        # create a Setpoint to adjust the proportional PID constant
        self.k_p = self._aqueduct.setpoint(
            name=f"k_p",
            value=0.0005,
            dtype=float.__name__,
        )

        # create a Setpoint to adjust the integral PID constant
        self.k_i = self._aqueduct.setpoint(
            name=f"k_i",
            value=0.0,
            dtype=float.__name__,
        )

        # create a Setpoint to adjust the derivative PID constant
        self.k_d = self._aqueduct.setpoint(
            name=f"k_d",
            value=0.0,
            dtype=float.__name__,
        )


class Watchdog(object):
    """
    The Watchdog class will have access to all of the Alarm
    classes.

    """

    over_pressure_alarm: local.lib.lnp.alarms.OverPressureAlarm
    low_pressure_alarm: local.lib.lnp.alarms.LowP3PressureAlarm
    vacuum_condition_alarm: local.lib.lnp.alarms.VacuumConditionAlarm
    low_buffer_vessel_alarm: local.lib.lnp.alarms.BufferVesselEmptyAlarm
    low_retentate_vessel_alarm: local.lib.lnp.alarms.RetentateVesselLowAlarm
    volume_accumulation_alarm: local.lib.lnp.alarms.VolumeAccumulationAlarm

    _devices: "local.lib.lnp.devices.Devices"
    _aqueduct: Aqueduct
    _data: "local.lib.lnp.data.Data"

    def __init__(
        self,
        data_obj: "local.lib.lnp.data.Data",
        devices_obj: "local.lib.lnp.devices.Devices",
        aqueduct_obj: Aqueduct
    ):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: "local.lib.lnp.data.Data" = data_obj
        self._devices: "local.lib.lnp.devices.Devices" = devices_obj
        self._aqueduct: Aqueduct = aqueduct_obj

        self.over_pressure_alarm = local.lib.lnp.alarms.OverPressureAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_pressure_alarm = local.lib.lnp.alarms.LowP3PressureAlarm(
            self._data, self._devices, self._aqueduct)
        self.vacuum_condition_alarm = local.lib.lnp.alarms.VacuumConditionAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_buffer_vessel_alarm = local.lib.lnp.alarms.BufferVesselEmptyAlarm(
            self._data, self._devices, self._aqueduct)
        self.low_retentate_vessel_alarm = local.lib.lnp.alarms.RetentateVesselLowAlarm(
            self._data, self._devices, self._aqueduct)
        self.volume_accumulation_alarm = local.lib.lnp.alarms.VolumeAccumulationAlarm(
            self._data, self._devices, self._aqueduct)

    def assign_process_to_alarms(self, process):
        """
        Set the reference to the Process instance for all of the Watchdog's alarms.

        :param process:
        :return:
        """
        for n, m in self.__dict__.items():
            a = getattr(self, n)
            if isinstance(a, local.lib.lnp.alarms.Alarm):
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
            if isinstance(a, local.lib.lnp.alarms.Alarm):
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

    hub_sn: int = None
    lab_mode: bool

    log_file_name: str = "LNP_operation"
    do_prompts: bool = True
    current_phase: int = None

    aq_pump_target_flowrate_ml_min: float = None
    oil_pump_target_flowrate_ml_min: float = None
    dilution_pump_target_flowrate_ml_min: float = None

    # #################################

    # #################################

    # #################################

    # #################################

    _devices: "local.lib.lnp.devices.Devices" = None
    _data: "local.lib.lnp.data.Data" = None
    _aqueduct: Aqueduct = None
    _setpoints: Setpoints = None
    _watchdog: Watchdog = None
    _model: "local.lib.lnp.models" = None
    _pid: "local.lib.lnp.pid.PID"

    @property
    def setpoints(self):
        return self._setpoints

    @property
    def aqueduct(self):
        return self._aqueduct

    @property
    def devices(self):
        return self._devices

    @property
    def data(self):
        return self._data

    @property
    def watchdog(self):
        return self._watchdog

    @property
    def model(self):
        return self._model

    @property
    def pid(self):
        return self._pid

    def __init__(
            self,
            devices_obj: "local.lib.lnp.devices.Devices" = None,
            data: "local.lib.lnp.data.Data" = None,
            aqueduct: Aqueduct = None,
            setpoints: Setpoints = None,
            watchdog: Watchdog = None,
            **kwargs
    ):

        self._devices = devices_obj
        self._data = data
        self._data._process = self
        self._aqueduct = aqueduct

        self._setpoints = setpoints
        self._watchdog = watchdog

        if isinstance(self._watchdog, Watchdog):
            self._watchdog.assign_process_to_alarms(self)

        self._model = local.lib.lnp.models.MassFlowModel(
            aqueduct=self._aqueduct,
            devices_obj=self._devices,
            data=self._data,
        )
        self._data._model = self._model

        self._pid = local.lib.lnp.pid.PID(
            k_p=self._setpoints.k_p.value,
            k_i=self._setpoints.k_i.value,
            k_d=self._setpoints.k_d.value,
        )

        self.assign_process_flowrates(**kwargs)

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
            if pump_name == AQ_PUMP:
                return self.init_conc_pump_1_target_flowrate_ml_min
            elif pump_name == OIL_PUMP:
                return self.init_conc_pump_2_target_flowrate_ml_min
            elif pump_name == DILUTION_PUMP:
                return self.init_conc_pump_3_target_flowrate_ml_min

        if self.current_phase == self.DIAFILT_PHASE:
            if pump_name == AQ_PUMP:
                return self.diafilt_pump_1_target_flowrate_ml_min
            elif pump_name == OIL_PUMP:
                return self.diafilt_pump_2_target_flowrate_ml_min
            elif pump_name == DILUTION_PUMP:
                return self.diafilt_pump_3_target_flowrate_ml_min

        if self.current_phase == self.FINAL_CONC_PHASE:
            if pump_name == AQ_PUMP:
                return self.final_conc_pump_1_target_flowrate_ml_min
            elif pump_name == OIL_PUMP:
                return self.final_conc_pump_2_target_flowrate_ml_min
            elif pump_name == DILUTION_PUMP:
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

    def do_lnp_protocol(self, quick: bool = False):
        """
        Runs entire LNP operation protocol sequentially.

        :param quick: if set to True, will set the Process's params to enable a
            quick run
        :return: None
        """

        if quick is True:
            self.set_quick_run_params()

        self.initialize()
        self.do_initial_prompts()
        self.do_pump_ramp()
        self.do_collection()
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
        # self._aqueduct.log("\n" + log_info)

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

        self._devices.PV.set_position(
            pct_open=self.pinch_valve_init_pct_open, record=True)

        # start reading the outputs of the Parker SciLog
        # at an interval of once per second
        self._devices.SCIP.start(interval_s=1., record=True)

        # start reading the outputs of the OHSA balance device
        # at an interval of once per second
        self._devices.OHSA.start(interval_s=1., record=True)

    def do_initial_prompts(self):
        """
        ************************
            User Interaction
            for Product Pour
            and Mass Input
        ************************


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
            self.init_conc_target_mass_g = local.lib.lnp.helpers.calc_init_conc_target_mass_g(
                init_conc_volume_ml=self.init_conc_volume_ml,
                polysaccharide_mass_mg=self.polysaccharide_mass_mg,
                init_conc_target_g_l=self.init_conc_target_g_l
            )

            print("[PHASE (INIT)] Initial Concentration target mass (g) for Scale 3 (permeate scale): {}".format(
                local.lib.lnp.helpers.format_float(
                    self.init_conc_target_mass_g, 2)
            ))

    def do_pump_ramp(self):

        if isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP) and self.two_pump_config is False:

            if self.do_prompts:
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

            if self.do_prompts:
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
                    print("[PHASE (INIT)] Transfer complete.")
                    time.sleep(2)
                    print("[PHASE (INIT)] Actual amount transferred: {:.2f} g".format(
                        self._data.W1))
                    break

                if isinstance(self._data.W1, float) and self._data.W1 > self.initial_transfer_volume:
                    self._devices.PUMP2.stop()
                    self._data.update_data()
                    print("[PHASE (INIT)] Transfer complete.")
                    time.sleep(2)
                    print("[PHASE (INIT)] Actual amount transferred: {:.2f} g".format(
                        self._data.W1))
                    break

                local.lib.lnp.methods.monitor(
                    interval_s=.2,
                    adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
                )

                if loops == 5:
                    print("[PHASE (INIT)] Waiting for {} more seconds...".format(
                        int((timeout - time.time()))))
                    loops = 0

                # increment loops by 1
                loops += 1

            self._data.update_data()

            if self.do_prompts:
                # prompt to confirm completion of transfer and start initial concentration
                self._aqueduct.prompt(
                    message="Transfer to retentate vessel complete. Press <b>continue</b> to proceed to initial "
                            "concentration.",
                    pause_recipe=True
                )

        else:

            if self.do_prompts:
                # prompt operator to place empty vessel on feed scale
                self._aqueduct.prompt(
                    message="Place empty vessel on Scale 1 (feed scale) and connect all lines."
                            " Press <b>continue</b> to start transfer.",
                    pause_recipe=True
                )

            # tare scale 1
            print("[PHASE (INIT)] Taring SCALE1.")
            self._devices.OHSA.tare(SCALE1_INDEX)

            if self.do_prompts:
                # prompt operator to pour product into feed vessel, press prompt to continue
                self._aqueduct.prompt(
                    message="Pour product solution into vessel on Scale 1 (feed scale)."
                            " Press <b>continue</b> to proceed to"
                            " initial concentration.",
                    pause_recipe=True
                )

    def do_collection(self):
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
        local.lib.lnp.methods.pump_ramp(
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
            print(
                "[PHASE (INIT)] Beginning Initial Concentration Step 2: Pump 2 and Pump 3 Ramp Up.")
        else:
            print(
                "[PHASE (INIT)] Beginning Initial Concentration Step 2: Pump 3 Ramp Up.")

        # ***UPDATE 1/30/2021 this is the point where we not want to cache the scale1 target mass
        # force an update of data to make sure the reading is latest before caching
        self._data.update_data()
        self._watchdog.volume_accumulation_alarm.set_scale1_target_mass()

        self._devices.SCIP.set_sim_rates_of_change(
            values=((0.01, 0.01, -0.01,) + 9 * (0,)))

        status = local.lib.lnp.methods.pumps_2_and_3_ramp(
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
            print(
                "[PHASE (INIT)] Beginning Initial Concentration Step 3: Pinch Valve Lock-In.")
            status = local.lib.lnp.methods.pinch_valve_lock_in_pid(
                interval=0.2,
                timeout_min=self.pinch_valve_lock_in_min,
                scale3_target_mass_g=self.init_conc_target_mass_g,
                process=self,
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
            timeout = time_start + \
                datetime.timedelta(seconds=self.init_conc_timeout_min * 60)

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
                    print(
                        "[PHASE (INIT)] Timed out waiting for initial concentration SCALE3 target mass.")
                    break

                local.lib.lnp.methods.monitor(
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
        self._data.update_data()

        # time delay to allow for pumps to decelerate to a stop before
        # recording init conc mass
        print("[PHASE (INIT)] Waiting for SCALE3 to stabilize...")
        time.sleep(self.record_mass_time_delay_s)
        self._data.update_data()
        self._data.log_data_at_interval(5)
        self.init_conc_actual_mass_g = self._data.W3

        print("[PHASE (INIT)] End Initial Concentration SCALE3 mass: {}g".format(
            self.init_conc_actual_mass_g))

        # log end time for init conc
        self.init_conc_end_time = datetime.datetime.utcnow().isoformat()

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
        print(
            f"[PHASE (CLN)] Beginning clean-up, open pinch valve to {self.pinch_valve_init_pct_open * 100}%")
        local.lib.lnp.methods.open_pinch_valve(
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
        self._devices.PUMP1.start(
            rate_value=self.init_conc_pump_1_target_flowrate_ml_min)

        # clear the trailing rates cache
        self._data._cache.clear_cache()

        # find the timeout time to break from loop
        time_start = datetime.datetime.utcnow()
        timeout = time_start + datetime.timedelta(seconds=5 * 60)
        print("[PHASE (WASH)] Washing for 5 minutes.")

        counter = 0

        # infinite loop until we meet a break condition
        while True:

            # check to see whether we've timed out
            if datetime.datetime.utcnow() > timeout:
                print("[PHASE (WASH)] Wash Complete.")
                break

            local.lib.lnp.methods.monitor(
                interval_s=1,
                adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog,
                process=self,
            )

            counter += 1

            if counter > 30:
                seconds_left = local.lib.lnp.helpers.format_float(
                    (timeout - datetime.datetime.utcnow()).total_seconds(),
                    1
                )
                print(
                    f"[PHASE (WASH)] Washing for {seconds_left} more seconds...")
                counter = 0

        # stop Pump 1
        print("[PHASE (WASH)] Stopping PUMP1.")
        self._devices.PUMP1.stop()

        # save log file
        self.add_process_info_to_log()
        # self._aqueduct.save_log_file(self.log_file_name, timestamp=True)

        # stop balance and pressure A/D
        self._devices.OHSA.stop()
        self._devices.SCIP.stop()

        print("[PHASE (WASH)] LNP Full Operation complete!")

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
            local.lib.lnp.methods.monitor(
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
                self._devices.SCIP.set_sim_pressure(
                    value=3, input_num=SCIP_INDEX, txdcr_num=tn)

        print("Doing Pump 1 Ramp Up...")
        local.lib.lnp.methods.pump_ramp(
            interval_s=1, pump=self._devices.PUMP1,
            pump_name="PUMP1",
            start_flowrate_ml_min=self.aq_pump_target_flowrate_ml_min / 2,
            end_flowrate_ml_min=self.aq_pump_target_flowrate_ml_min,
            rate_change_interval_s=1,
            rate_change_ml_min=self.init_conc_pump1_ramp_increment_ml_min,
            timeout_min=self.init_conc_pump1_ramp_timeout_min,
            adjust_pinch_valve=False,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog)

        print("Doing Pumps 2 and 3 Ramp Up...")
        local.lib.lnp.methods.pumps_2_and_3_ramp(
            interval_s=1,
            pump2_start_flowrate_ml_min=self.oil_pump_target_flowrate_ml_min / 2,
            pump2_end_flowrate_ml_min=self.oil_pump_target_flowrate_ml_min,
            pump3_start_flowrate_ml_min=self.dilution_pump_target_flowrate_ml_min / 2,
            pump3_end_flowrate_ml_min=self.dilution_pump_target_flowrate_ml_min,
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
                local.lib.lnp.methods.monitor(
                    interval_s=1,
                    adjust_pinch_valve=False,
                    devices_obj=self._devices,
                    data=self._data,
                    watchdog=self._watchdog,
                    process=self,
                )

                reset_sim_pressures_to_3_psi()
                break
