import time

from typing import Union

from aqueduct.core.aq import Aqueduct
from aqueduct.devices.pump import PeristalticPump
from aqueduct.devices.balance import Balance
from aqueduct.devices.pressure import PressureTransducer
from aqueduct.devices.valve import PinchValve

import tff.classes
import tff.methods

class Alarm(object):
    """
    Class to assist with checking on alarm conditions and
    responding appropriately.

    """
    active: bool = False
    _data: "Data" = None  # pointer to Data object
    _devices: "Devices" = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process = None  # pointer to Process object

    def __init__(self, data_obj: "Data", devices_obj: "Devices", aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param data_obj:
        :param devices_obj:
        :param aqueduct_obj:
        """
        self._data: "Data" = data_obj
        self._devices: "Devices" = devices_obj
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
        if self._process.current_phase == tff.classes.Process.INITIAL_CONC_PHASE:
            return self._process.init_conc_target_mass_g
        elif self._process.current_phase == tff.classes.Process.DIAFILT_PHASE:
            return self._process.diafilt_target_mass_g
        elif self._process.current_phase == tff.classes.Process.FINAL_CONC_PHASE:
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

    def condition(self) -> bool:
        """
        If P1 > max_pressure_psi || P2 > max_pressure_psi || P3 > max_pressure_psi, raise alarm

        :return:
        """

        if (
            self._data.P1 > self.max_pressure_psi or
            self._data.P2 > self.max_pressure_psi or
            self._data.P3 > self.max_pressure_psi
        ):
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

        print("[***ALARM***] Overpressure alarm raised! Stopping all pumps. Dismiss prompt to continue.")
        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
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

        tff.methods.pump_ramp(
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

        tff.methods.pumps_2_and_3_ramp(
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

        print("[***ALARM***] Underpressure P3 alarm raised!")
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            print("[ALARM (UNDERPRESSURE)] Stopping Pumps 2 and 3.")
        else:
            print("[ALARM (UNDERPRESSURE)] Stopping Pump 3.")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        # small time delay
        time.sleep(5)

        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            print("[ALARM (UNDERPRESSURE)] Ramping Pumps 2 and 3 to 90% of previous rates.")
        else:
            print("[ALARM (UNDERPRESSURE)] Ramping Pump 3 to 90% of previous rates.")

        tff.methods.pumps_2_and_3_ramp(
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

        print("[***ALARM***] Vacuum Condition Alarm raised! Stopping all pumps. Dismiss prompt to continue.")
        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
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

        tff.methods.pump_ramp(
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

        tff.methods.pumps_2_and_3_ramp(
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
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            print("""[***ALARM***] Low Buffer Vessel Mass alarm raised! 
            Stopping Pumps 2 and 3.""")
        else:
            print("""[***ALARM***] Low Buffer Vessel Mass alarm raised! 
            Stopping Pump 3.""")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
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

        tff.methods.pumps_2_and_3_ramp(
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
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            print("""[***ALARM***] Retentate Vessel Mass alarm raised! 
            Stopping Pumps 1, 2, and 3.""")

        else:
            print("""[***ALARM***] Retentate Vessel Mass alarm raised! 
            Stopping Pumps 1 and 3.""")

        self.cached_pump1_rate_ml_min = self._data.R1
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self.cached_pump2_rate_ml_min = self._data.R2
        self.cached_pump3_rate_ml_min = self._data.R3
        self._devices.PUMP1.stop()
        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
            self._devices.PUMP2.stop()
        self._devices.PUMP3.stop()

        if isinstance(self._devices.PUMP2, PeristalticPump) and self._process.two_pump_config is False:
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

        tff.methods.pump_ramp(
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

        tff.methods.pumps_2_and_3_ramp(
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

        if isinstance(rates, tff.data.TrailingRates):
            rates.print()

            # if PUMP2 is present, try to handle the vol. accum
            if isinstance(self._devices.PUMP2, PeristalticPump):

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
                print("[CONTROL] Setting SCALE1 setpoint volume to: {} mL".format(self._data.W1))
                self.scale1_target_ml = self._data.W1
                return
            time.sleep(1)
            self._data.update_data()
            n += 1

    def check_max_deviation(self, rates: "TrailingRates") -> None:
        if abs(abs(rates.W2_ml_min) - abs(rates.R2_ml_min)) > self.pump2_max_deviation_ml_min:
            print("""[CONTROL] Deviation between PUMP2 rate: {} mL/min, 
            and buffer removal rate, {} mL/min, 
            exceeds maximum allowable value of {} mL/min.""".format(
                rates.R2_ml_min, rates.W2_ml_min, self.pump2_max_deviation_ml_min)
            )

    def handle_mode1(self, rates: "TrailingRates"):
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
                print("[CONTROL (MODE {})] changing PUMP2 rate to {} mL/min".format(
                    self.mode,
                    tff.helpers.format_float(pump2_new_rate, 2)))
                
                commands = self._devices.PUMP2.make_commands()
                command = PeristalticPump.make_change_speed_command(
                    rate_value=pump2_new_rate,
                    rate_units=self._devices.PUMP2.RATE_UNITS.MlMin,
                )
                self._devices.PUMP2.set_command(commands, 0, command)
                self._devices.PUMP2.change_speed(commands)

                clear_cache = True

        if clear_cache is True:
            self._data._cache.clear_cache()
            self._data._cache._scheduled_time = time.time() + self.check_interval_s

    def handle_mode2(self, rates: "TrailingRates"):
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
            pump2_rate_magnitude_ml_min = (abs(self._data.W1 - self.scale1_target_ml) / self.scale1_target_time_min)
            pump2_new_rate = (sign * pump2_rate_magnitude_ml_min) + self._data.R2 - rates.W1_ml_min
            max_adjustment_ml_min = max(self._data.R2 * self.max_pump2_adjustment_pct,
                                        self.floor_pump2_adjustment_ml_min)
            pump2_new_rate = min(pump2_new_rate, self._data.R2 + max_adjustment_ml_min)
            pump2_new_rate = max(pump2_new_rate, self._data.R2 - max_adjustment_ml_min)
            pump2_new_rate = round(pump2_new_rate, 2)

            if pump2_new_rate is not None and pump2_new_rate > 0:
                print("[CONTROL (MODE {})] changing PUMP2 rate to {} mL/min to "
                      "hit target SCALE1 setpoint of {} mL".format(
                    self.mode,
                    tff.helpers.format_float(pump2_new_rate, 2),
                    self.scale1_target_ml
                ))
                
                commands = self._devices.PUMP2.make_commands()
                command = PeristalticPump.make_change_speed_command(
                    rate_value=pump2_new_rate,
                    rate_units=self._devices.PUMP2.RATE_UNITS.MlMin,
                )
                self._devices.PUMP2.set_command(commands, 0, command)
                self._devices.PUMP2.change_speed(commands)

                clear_cache = True
        else:
            self.handle_mode1(rates)
            clear_cache = True

        if clear_cache is True:
            self._data._cache.clear_cache()
            self._data._cache._scheduled_time = time.time() + self.check_interval_s