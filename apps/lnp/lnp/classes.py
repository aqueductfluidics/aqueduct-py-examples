import datetime
import inspect
import pprint
import time

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import ALLOWED_DTYPES, Setpoint
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

import lnp.alarms
import lnp.devices
import lnp.data
import lnp.helpers
import lnp.methods
import lnp.models
import lnp.pid
from lnp.definitions import *


class Setpoints:
    """
    Class that will contain all Aqueduct Setpoints
    for the LNP setup.

    Setpoints will display as User Params on the
    Recipe Editor screen and can be edited
    by a user.

    """

    aq_target_ml_min: Setpoint = None
    oil_target_ml_min: Setpoint = None
    dilution_target_ml_min: Setpoint = None

    _aqueduct: Aqueduct = None

    def __init__(self, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param aqueduct_obj:
        """
        self._aqueduct = aqueduct_obj

        self.aq_target_ml_min = self._aqueduct.setpoint(
            name="aq_target_ml_min", value=50, dtype=float.__name__
        )

        self.oil_target_ml_min = self._aqueduct.setpoint(
            name="oil_target_ml_min",
            value=50,
            dtype=float.__name__,
        )

        self.dilution_target_ml_min = self._aqueduct.setpoint(
            name="dilution_target_ml_min",
            value=150,
            dtype=float.__name__,
        )


class Watchdog:
    """
    The Watchdog class will have access to all of the Alarm
    classes.

    """

    over_pressure_alarm: lnp.alarms.OverPressureAlarm

    _devices: "lnp.devices.Devices"
    _aqueduct: Aqueduct
    _data: "lnp.data.Data"

    def __init__(
        self,
        data_obj: "lnp.data.Data",
        devices_obj: "lnp.devices.Devices",
        aqueduct_obj: Aqueduct,
    ):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: "lnp.data.Data" = data_obj
        self._devices: "lnp.devices.Devices" = devices_obj
        self._aqueduct: Aqueduct = aqueduct_obj

        self.over_pressure_alarm = lnp.alarms.OverPressureAlarm(
            self._data, self._devices, self._aqueduct
        )

    def assign_process_to_alarms(self, process):
        """
        Set the reference to the Process instance for all of the Watchdog's alarms.

        :param process:
        :return:
        """
        for n, m in self.__dict__.items():
            a = getattr(self, n)
            if isinstance(a, lnp.alarms.Alarm):
                setattr(a, "_process", process)

    def turn_all_alarms_off(self):
        """
        Make all alarms inactive by setting their `active`
        attribute to False.

        :return:
        """

        self.over_pressure_alarm.active = False

    def check_alarms(self):
        """
        Method to run the `check` method of each Alarm
        type.

        :return:
        """
        try:
            self.over_pressure_alarm.check()
        except TypeError:
            pass


"""
PROCESS CLASSES
"""


class Process:
    """
    Class to contain process information like
    drug substance, filter area, etc.

    """

    hub_sn: int = None
    lab_mode: bool

    log_file_name: str = "LNP_operation"
    do_prompts: bool = True
    current_phase: int = None

    aq_pump_init_flowrate_ml_min: float = None
    oil_pump_init_flowrate_ml_min: float = None
    dilution_pump_init_flowrate_ml_min: float = None

    aq_pump_target_flowrate_ml_min: float = None
    oil_pump_target_flowrate_ml_min: float = None
    dilution_pump_target_flowrate_ml_min: float = None

    collection_time_min: float = 2

    _devices: "lnp.devices.Devices" = None
    _data: "lnp.data.Data" = None
    _aqueduct: Aqueduct = None
    _setpoints: Setpoints = None
    _watchdog: Watchdog = None
    _model: "lnp.models" = None
    _pid: "lnp.pid.PID"

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
        devices_obj: "lnp.devices.Devices" = None,
        data: "lnp.data.Data" = None,
        aqueduct: Aqueduct = None,
        setpoints: Setpoints = None,
        watchdog: Watchdog = None,
        **kwargs,
    ):

        self._devices = devices_obj
        self._data = data
        self._data._process = self
        self._aqueduct = aqueduct

        self._setpoints = setpoints
        self._watchdog = watchdog

        if isinstance(self._watchdog, Watchdog):
            self._watchdog.assign_process_to_alarms(self)

        self._model = lnp.models.MassFlowModel(
            aqueduct=self._aqueduct,
            devices_obj=self._devices,
            data=self._data,
        )
        self._data._model = self._model

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
            if (
                attribute[:1] != "_"
                and not any(l.isupper() for l in attribute)
                and not callable(value)
            ):
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
        """

        print("[PHASE (INIT)] Initializing Operation...")

        print("[PHASE (INIT)] Stopping all Pumps.")

        self.devices.AQ_PUMP.clear_recorded()
        self.devices.OIL_PUMP.clear_recorded()
        self.devices.DILUTION_PUMP.clear_recorded()

        self.devices.AQ_PUMP.stop()
        self.devices.OIL_PUMP.stop()
        self.devices.DILUTION_PUMP.stop()

        self.devices.SOL_VALVES.clear_recorded()

        valve_command = self.devices.SOL_VALVES.make_empty_command()
        valve_command[AQUEOUS_VALVE_INDEX] = BYPASS_POSITION
        valve_command[OIL_VALVE_INDEX] = BYPASS_POSITION
        self.devices.SOL_VALVES.set_positions(valve_command, record=True)

        self.devices.MFM.clear_recorded()
        self.devices.MFM.start(interval_s=1.0, record=True)

        self.devices.SCIP.clear_recorded()
        self.devices.SCIP.start(interval_s=1.0, record=True)

        self.devices.TEMP_PROBE.clear_recorded()
        self.devices.TEMP_PROBE.start(interval_s=1.0, record=True)

    def do_pump_ramp(self):

        lnp.methods.multi_pump_ramp(
            pumps=(
                self.devices.AQ_PUMP,
                self.devices.OIL_PUMP,
                self.devices.DILUTION_PUMP,
            ),
            start_flow_rates_ml_min=[20, 20, 50],
            end_flow_rates_ml_min=[50, 50, 100],
            interval_s=1,
            number_rate_changes=6,
            rate_change_interval_s=5,
            devices_obj=self.devices,
            data=self.data,
            watchdog=self.watchdog,
        )

    def do_collection(self):
        """
        ************************
            Collection
            Step 1: Set valves to Collect
        ************************

        """

        print("[PHASE (COLLECT)] Beginning Collection.")

        self.data.update_data()

        valve_command = self.devices.SOL_VALVES.make_empty_command()
        valve_command[AQUEOUS_VALVE_INDEX] = PRODUCT_POSITION
        valve_command[OIL_VALVE_INDEX] = PRODUCT_POSITION
        self.devices.SOL_VALVES.set_positions(valve_command, record=True)

        time_start = datetime.datetime.utcnow()
        timeout = time_start + datetime.timedelta(seconds=self.collection_time_min * 60)

        # infinite loop until we meet a break condition
        while True:

            # check to see whether we've timed out
            if datetime.datetime.utcnow() > timeout:
                print("[PHASE (COLLECT)] Collection period expired.")
                break

            lnp.methods.monitor(
                interval_s=1,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog,
                process=self,
            )

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
        if (
            isinstance(self._devices.PUMP2, aqueduct.devices.mfpp.obj.MFPP)
            and self.two_pump_config is False
        ):
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

        print(
            "[PHASE (INIT)] End Initial Concentration SCALE3 mass: {}g".format(
                self.init_conc_actual_mass_g
            )
        )

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
            f"[PHASE (CLN)] Beginning clean-up, open pinch valve to {self.pinch_valve_init_pct_open * 100}%"
        )
        lnp.methods.open_pinch_valve(
            target_pct_open=self.pinch_valve_init_pct_open,
            increment_pct_open=0.005,
            interval_s=1,
            devices_obj=self._devices,
            data=self._data,
            watchdog=self._watchdog,
        )

        # prompt operator to confirm that the retentate line is blown down (wait here)
        p = self._aqueduct.prompt(
            message="Confirm that the retentate line is blown down. Press <b>continue</b> to continue.",
            pause_recipe=True,
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
            pause_recipe=True,
        )

        # start Pump !
        self._devices.PUMP1.start(
            rate_value=self.init_conc_pump_1_target_flowrate_ml_min
        )

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

            lnp.methods.monitor(
                interval_s=1,
                adjust_pinch_valve=self._setpoints.pinch_valve_control_active.value,
                devices_obj=self._devices,
                data=self._data,
                watchdog=self._watchdog,
                process=self,
            )

            counter += 1

            if counter > 30:
                seconds_left = lnp.helpers.format_float(
                    (timeout - datetime.datetime.utcnow()).total_seconds(), 1
                )
                print(f"[PHASE (WASH)] Washing for {seconds_left} more seconds...")
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
