"""Dispensing Classes Module"""
# pylint: disable=pointless-string-statement

import time
import enum
import json

from typing import List, Tuple, Callable, Union

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import Setpoint, ALLOWED_DTYPES

from aqueduct.devices.pump import SyringePump

import dispensing.helpers
import dispensing.methods
from dispensing.definitions import *

class Devices(object):
    """
    PUMP is the TriContinent C(X) series of pumps with up to 12 inputs

    In DEV MODE, we create `aqueduct.devices.trcx.obj` for easy access to
    the methods for each device type.

    In LAB MODE, we associate each Device with the Name for the device
    that is saved on its firmware.
    """
    PUMP: SyringePump = None

    def __init__(self, aq: Aqueduct):
        self.PUMP = aq.devices.get(PUMP_NAME)


class Data(object):
    """
    Class to help with logging and updating data for the dosing setup.
    """
    W1: Union[float, None] = None  # weight on the SCALE, in grams

    timestamp: Union[float, None] = None
    log_timestamp: Union[float, None] = None  # timestamp of last write to log file
    _logging_interval_s: Union[int, float] = 5  # interval in seconds between writes to log file

    _devices: Devices = None  # pointer to Devices object
    _aqueduct: Aqueduct = None  # pointer to Aqueduct object
    _process: "ReactionProcessHandler" = None  # pointer to Process object

    def __init__(self, devices_obj: Devices, aqueduct_obj: Aqueduct):
        """
        Instantiation method.

        :param devices_obj:
        :param aqueduct_obj:
        """
        self._devices = devices_obj
        self._aqueduct = aqueduct_obj

        if isinstance(aqueduct_obj, Aqueduct):
            self._is_lab_mode = True
        else:
            self._is_lab_mode = False

    def update_data(self) -> None:
        """
        Method to update the global data dictionary.

        Uses the specific Device Object methods to get the
        data from memory.

        :return:
        """
        self.timestamp = time.time()

    def log_data(self) -> None:
        """
        Method to log:

            W1 (in grams)

        at a given time.

        :return: None
        """
        self._aqueduct.log(
            "W1: {0}".format(
                local.lib.dispensing.helpers.format_float(self.W1, 3),
            ))

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
            ('W1', 3),
            ('timestamp', 3),
        ]
        d = {}
        for k in keys:
            d.update({k[0]: local.lib.dispensing.helpers.format_float(getattr(self, k[0], None), k[1])})
        return d


class PumpInput(object):
    # index should correspond to the TRCX device pump input, 0-11 (12 in total)
    index: int = None

    # reference to the Devices object
    _devices: Devices = None

    def __init__(self, index: int = None, devices_obj: Devices = None):
        self.index = index
        self._devices = devices_obj

    def get_syringe_volume_ul(self) -> float:
        return self._devices.PUMP.config[self.index].syringe_vol_ul

    def get_max_rate_ul_min(self) -> float:
        return self._devices.PUMP.get_max_rate_ul_min(self.index)

    def get_min_rate_ul_min(self) -> float:
        return self._devices.PUMP.get_min_rate_ul_min(self.index)


class MonomerPumpInput(PumpInput):
    """
    Class to represent a Monomer Pump Input as part of a Reaction Station.
    """
    monomer_A_input_port: int = 1
    monomer_B_input_port: int = 2
    output_port: int = 3
    waste_port: int = 4

    # adjust the priming volumes as needed to completely prime tubing of various
    # length and inner diameter
    # in house testing tubing length = 300 mm, 0.8 mm ID = 151 uL volume
    # update 8/11/21 - add 200 uL to default priming volumes
    monomer_a_priming_volume_ul: float = 151. + 300. + 200.
    monomer_b_priming_volume_ul: float = 151. + 300. + 200.

    # output tubing volume
    # in house testing tubing length = 600 mm, 0.8 mm ID = 302 uL volume
    # empirically set to 350 uL
    output_tubing_volume_ul: float = 350.

    def __init__(self, index: int = None, devices_obj: Devices = None):
        """
        Instantiation method.

        :param index:
        :param devices_obj:
        """
        super().__init__(index, devices_obj)


class InitiatorPumpInput(PumpInput):
    """
    Class to represent an Initiator Pump Input as part of a Reaction Station.
    """
    initiator_input_port: int = 1
    output_port: int = 2
    waste_port: int = 3

    # adjust the priming volumes as needed to completely prime tubing of various
    # length and inner diameter
    # in house testing tubing length = 300 mm, 0.8 mm ID = 151 uL volume
    # update 8/11/21 - add 200 uL to default priming volume
    initiator_priming_volume_ul: float = 151. + 300. + 200.

    # output tubing volume
    # in house testing tubing length = 600 mm, 0.8 mm ID = 302 uL volume
    # empirically set to 350 uL
    output_tubing_volume_ul: float = 350.

    def __init__(self, index: int = None, devices_obj: Devices = None):
        """
        Instantiation method.

        :param index:
        :param devices_obj:
        """
        super().__init__(index, devices_obj)


class ReactionStation(object):
    """
    Class to contain all relevant parameters for executing a 2 Phase Monomer A / Initiator A +
    Monomer B / Initiator B reaction.

    Monomer A is added manually.

    Phase 1: (1hr) dispensing Monomer A into each reactor and
    Phase 2: (3hr) dispensing of Monomer B and Initiator B into each reactor
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
        PHASE_1_INITIALIZED = 0

        # set monomer and initiator valves to waste,
        # infuse both pumps completely at max rate
        PHASE_1_PRIMING_INIT_PURGE_TO_WASTE = 1

        # set monomer valve to monomer A input, withdraw enough volume
        # to fill input tubing + some volume in syringe,
        # at priming_withdraw_rate_ml_min
        PHASE_1_PRIMING_WITHDRAW = 2

        # set monomer valve to waste, infuse pump completely at
        # priming_infuse_rate_(pump)_ml_min
        PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE = 3

        # now we need to withdraw the volume necessary to
        # do the monomer A dispense, which might include the
        # output tubing volume
        PHASE_1_MONOMER_A_WITHDRAW = 4

        # now we set the monomer valve to output and 
        # begin infusing to quickly run the
        # liquid slug to almost the end of the tubing
        PHASE_1_OUTPUT_PRIMING = 5

        # now we begin infusing at the specified monomer A addition rate
        PHASE_1_INFUSING_MONOMER_A = 6

        # withdraw residual monomer A from output line and
        # send it to waste
        PHASE_1_OUTPUT_PURGE = 7

        # monomer A infusion complete
        PHASE_1_COMPLETE = 8

        # start of phase 2, monomer B and initiator co-dispense
        PHASE_2_INITIALIZED = 9

        # set monomer and initiator valves to waste,
        # infuse both pumps completely at max rate
        PHASE_2_PRIMING_INIT_PURGE_TO_WASTE = 10

        # set monomer valve to monomer B input and initiator valve to input
        # withdraw enough volume to fill input tubing + some volume in syringe,
        # infuse at priming_withdraw_rate_ml_min
        PHASE_2_PRIMING_WITHDRAW = 11

        # set monomer valve to waste and initiator valve to waste
        # infuse pump completely at priming_infuse_rate_(pump)_ml_min
        PHASE_2_PRIMING_FINAL_PURGE_TO_WASTE = 12

        # now we need to withdraw the volumes of monomer B and
        # init B necessary to do the monomer B and init B dispense,
        # which might include the output tubing volume
        PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW = 13

        # now we set the monomer valve to output and
        # the initiator valve to output and
        # begin infusing to quickly run the
        # liquid slugs to almost the end of the tubing
        PHASE_2_OUTPUT_PRIMING = 14

        # now we begin infusing at the specified
        # monomer B addition rate and init B addition rate
        PHASE_2_INFUSING_MONOMER_B_AND_INIT_B = 15

        # withdraw residual monomer B and initiator B
        # from the output lines and and send the liquids to waste
        PHASE_2_OUTPUT_PURGE = 16

        # phase 2 complete!
        PHASE_2_COMPLETE = 99

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

    # track the status of the current phase using one of the CurrentPhaseStatus
    # enum's members
    current_phase_status: int = CurrentPhaseStatus.NOT_STARTED.value

    # logging
    logging_enabled: bool = True
    log_file_name: str = "reaction_"

    # each ReactionStation has a monomer input and an initiator input
    monomer_input: MonomerPumpInput = None
    initiator_input: InitiatorPumpInput = None

    # MONOMER A PARAMS

    # monomer A process params
    monomer_a_volume_to_dispense_ul: float = 1000
    monomer_a_dispense_rate_ul_min: float = 16.

    # volume and rate used to quickly prime to the end of the output
    # tubing line for the first dispense
    monomer_a_output_tubing_prime_volume_ul: float = 315.
    monomer_a_output_tubing_prime_rate_ul_min: float = 2000.

    # rate to use when withdrawing monomer A
    monomer_a_withdraw_rate_ul_min: float = 25000.

    _monomer_a_dispensed_ul_counter: float = 0.
    _monomer_a_infusions_counter: int = 0

    # MONOMER B PARAMS

    # monomer B process params
    monomer_b_volume_to_dispense_ul: float = 20000
    monomer_b_dispense_rate_ul_min: float = 100.

    # volume and rate used to quickly prime to the end of the output
    # tubing line for the first dispense
    monomer_b_output_tubing_prime_volume_ul: float = 315.
    monomer_b_output_tubing_prime_rate_ul_min: float = 2000.

    # rate to use when withdrawing monomer B
    monomer_b_withdraw_rate_ul_min: float = 25000.

    _monomer_b_dispensed_ul_counter: float = 0.
    _monomer_b_infusions_counter: int = 0
    _monomer_b_dispense_volume_ul: float = 0

    # INITIATOR B PARAMS

    # initiator B process params
    initiator_b_dispense_rate_ul_min: float = 10

    initiator_b_output_tubing_prime_volume_ul: float = 315.
    initiator_b_output_tubing_prime_rate_ul_min: float = 2000.

    # rate to use when withdrawing initiator B
    initiator_b_withdraw_rate_ul_min: float = 25000.

    _initiator_b_dispensed_ul_counter: float = 0.
    _initiator_b_infusions_counter: int = 0
    _initiator_b_dispense_volume_ul: float = 0

    _last_monomer_withdraw_volume_ul: float = 0.
    _last_initiator_withdraw_volume_ul: float = 0.

    _repeat: bool = False

    # reference to the Global aqueduct instance
    _devices: Devices = None
    _aqueduct: Aqueduct = None

    def __init__(
            self,
            index: int = 0,
            devices_obj: Devices = None,
            aqueduct: Aqueduct = None
    ):

        self.index = index

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

    def __str__(self):
        return f"Station {self.index} (mon. {self.monomer_input.index}, init. {self.initiator_input.index}): " \
               f"enabled={self.enabled_setpoint.value}, phase={self.phase_setpoint.value}"

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
            value=ReactionStation.Phase.PHASE_1_INITIALIZED.value,
            dtype=int.__name__
        )

    def calc_initiator_b_volume_to_dispense_ul(self) -> float:
        """
        A ratiometric calculation of the volume of Initiator B to dispense based on initiator_b_dispense_rate_ul_min

        :return: volume of Initiator B to dispense, in uL
        """
        return round((self.initiator_b_dispense_rate_ul_min / self.monomer_b_dispense_rate_ul_min)
                     * self.monomer_b_volume_to_dispense_ul, 3)

    def reset_phase_1(self) -> None:
        """
        Reset the dispense counter for monomer A.

        """
        self._monomer_a_dispensed_ul_counter: float = 0.
        self._monomer_a_infusions_counter: int = 0

    def reset_phase_2(self) -> None:
        """
        Reset the dispense counters for monomer B and initiator B.

        """
        self._monomer_b_dispensed_ul_counter: float = 0.
        self._initiator_b_dispensed_ul_counter: float = 0.
        self._monomer_b_infusions_counter: int = 0
        self._initiator_b_infusions_counter: int = 0

    def reset(self) -> None:
        """
        Reset both Phase 1 and Phase 2 counters.

        """
        self.reset_phase_1()
        self.reset_phase_2()

    def set_plunger_mode(self, pump_input: PumpInput, target_mode: int, pump_name: str, force: bool = False):
        """
        Helper method to change the plunger stepping mode of a given input.

        Will print the change of resolution to the screen and, if the ReactionStation's `logging_enabled`
        member is set to True, will log the change to the process log file.

        :param pump_input:
        :param target_mode:
        :param pump_name:
        :param force:
        :return:
        """

        if int(self._devices.PUMP.config[pump_input.index].plgr_mode) != int(target_mode) or force is True:
            _ = f"Station {self.index}: setting {pump_name} plunger resolution to {target_mode}"
            print(_)
            if self.logging_enabled:
                self._aqueduct.log(_)
            self._devices.PUMP.set_plunger_resolution(**{f"pump{pump_input.index}": target_mode})
            self._devices.PUMP.config[pump_input.index].plgr_mode = target_mode
            time.sleep(0.5)

    @staticmethod
    def phase_to_str(phase: int) -> str:
        """
        Helper method to convert the Phase Enum number to a readable string.

        :param phase:
        :return: human readable phase description
        """
        if phase == ReactionStation.Phase.PHASE_1_INITIALIZED.value:
            return "phase 1 initialized"
        elif phase == ReactionStation.Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE.value:
            return "initial purge to waste"
        elif phase == ReactionStation.Phase.PHASE_1_PRIMING_WITHDRAW.value:
            return "mon. A priming wdrw"
        elif phase == ReactionStation.Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE.value:
            return "mon. A priming purge to waste"
        elif phase == ReactionStation.Phase.PHASE_1_MONOMER_A_WITHDRAW.value:
            return "mon. A wdrw"
        elif phase == ReactionStation.Phase.PHASE_1_OUTPUT_PRIMING.value:
            return "mon. A output priming"
        elif phase == ReactionStation.Phase.PHASE_1_INFUSING_MONOMER_A.value:
            return "mon. A inf"
        elif phase == ReactionStation.Phase.PHASE_1_OUTPUT_PURGE.value:
            return "mon. A output purging"
        elif phase == ReactionStation.Phase.PHASE_1_COMPLETE.value:
            return "phase 1 complete"
        elif phase == ReactionStation.Phase.PHASE_2_INITIALIZED.value:
            return "phase 2 initialized"
        elif phase == ReactionStation.Phase.PHASE_2_PRIMING_INIT_PURGE_TO_WASTE.value:
            return "initial purge to waste"
        elif phase == ReactionStation.Phase.PHASE_2_PRIMING_WITHDRAW.value:
            return "mon. B and init. B priming wdrw"
        elif phase == ReactionStation.Phase.PHASE_2_PRIMING_FINAL_PURGE_TO_WASTE.value:
            return "mon. B and init. B priming purge to waste"
        elif phase == ReactionStation.Phase.PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW.value:
            return "mon. B and init. B wdrw"
        elif phase == ReactionStation.Phase.PHASE_2_OUTPUT_PRIMING.value:
            return "mon. B and init. B output priming"
        elif phase == ReactionStation.Phase.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B.value:
            return "mon. B and init. B inf"
        elif phase == ReactionStation.Phase.PHASE_2_OUTPUT_PURGE.value:
            return "mon. B and init. B output purging"
        elif phase == ReactionStation.Phase.PHASE_2_COMPLETE.value:
            return "phase 2 complete"

    def set_current_phase_status(self, phase_status: CurrentPhaseStatus) -> None:
        self.current_phase_status = phase_status.value

    def _phase_helper(
            self,
            do_if_not_started: Callable = None,
            next_phase: "ReactionStation.Phase" = None,
            do_if_not_started_kwargs: dict = None) -> None:
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
        if self.current_phase_status == ReactionStation.CurrentPhaseStatus.NOT_STARTED.value:
            self.set_current_phase_status(ReactionStation.CurrentPhaseStatus.STARTED)
            if do_if_not_started is not None:
                if do_if_not_started_kwargs is not None:
                    do_if_not_started(**do_if_not_started_kwargs)
                else:
                    do_if_not_started()
        elif self.current_phase_status == ReactionStation.CurrentPhaseStatus.STARTED.value:
            self.set_current_phase_status(ReactionStation.CurrentPhaseStatus.NOT_STARTED)
            self.phase_setpoint.update(next_phase.value)

    def do_next_phase(self):

        # aliases for the ReactionStation.Phase Enum and the ReactionStation.CurrentPhaseStatus Enum to
        # avoid typing for each comparison
        PC = ReactionStation.Phase

        # flag to repeat the method after printing the status update
        # initialized to False
        repeat: bool = False

        # start of a logging string that tracks the phase and status change
        log_str: str = f"Station {self.index}: {ReactionStation.phase_to_str(self.phase_setpoint.value)}" \
                       f"({self.phase_setpoint.value}[{self.current_phase_status}]) -> "

        if self.phase_setpoint.value == PC.PHASE_1_INITIALIZED.value:
            self._phase_helper(do_if_not_started=None,
                               next_phase=PC.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE)
            repeat = True

        elif self.phase_setpoint.value == PC.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE.value:
            self._phase_helper(do_if_not_started=self.do_initial_purge_to_waste,
                               next_phase=PC.PHASE_1_PRIMING_WITHDRAW)

        elif self.phase_setpoint.value == PC.PHASE_1_PRIMING_WITHDRAW.value:
            self._phase_helper(do_if_not_started=self.do_phase_1_priming_withdraw,
                               next_phase=PC.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE)

        elif self.phase_setpoint.value == PC.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE.value:
            self._phase_helper(do_if_not_started=self.do_phase_1_priming_final_purge_to_waste,
                               next_phase=PC.PHASE_1_MONOMER_A_WITHDRAW)

        elif self.phase_setpoint.value == PC.PHASE_1_MONOMER_A_WITHDRAW.value:
            self._phase_helper(do_if_not_started=self.do_phase_1_monomer_a_withdraw,
                               next_phase=PC.PHASE_1_OUTPUT_PRIMING)

        elif self.phase_setpoint.value == PC.PHASE_1_OUTPUT_PRIMING.value:
            # on the first dispense we need to prime,
            # otherwise straight to dispense at dispense_rate
            if self._monomer_a_dispensed_ul_counter == 0:
                self._phase_helper(do_if_not_started=self.do_phase_1_output_tubing_prime,
                                   next_phase=PC.PHASE_1_INFUSING_MONOMER_A)
            else:
                self._phase_helper(do_if_not_started=None,
                                   next_phase=PC.PHASE_1_INFUSING_MONOMER_A)
                repeat = True

        elif self.phase_setpoint.value == PC.PHASE_1_INFUSING_MONOMER_A.value:
            if self.current_phase_status == ReactionStation.CurrentPhaseStatus.NOT_STARTED.value:
                self._phase_helper(do_if_not_started=self.do_phase_1_monomer_a_dispense,
                                   next_phase=PC.PHASE_1_INFUSING_MONOMER_A)
            else:
                # if self._monomer_a_dispensed_ul_counter >= self.monomer_a_volume_to_dispense_ul
                # then we should continue to purge to waste, otherwise reload
                if self._monomer_a_dispensed_ul_counter >= self.monomer_a_volume_to_dispense_ul:
                    self._phase_helper(do_if_not_started=None,
                                       next_phase=PC.PHASE_1_OUTPUT_PURGE)
                # reload
                else:
                    self._phase_helper(do_if_not_started=None,
                                       next_phase=PC.PHASE_1_MONOMER_A_WITHDRAW)

        elif self.phase_setpoint.value == PC.PHASE_1_OUTPUT_PURGE.value:
            self._phase_helper(do_if_not_started=self.do_phase_1_output_purge,
                               next_phase=PC.PHASE_1_COMPLETE)

        elif self.phase_setpoint.value == PC.PHASE_1_COMPLETE.value:
            self._phase_helper(do_if_not_started=None,
                               next_phase=PC.PHASE_2_INITIALIZED)
            repeat = True

        elif self.phase_setpoint.value == PC.PHASE_2_INITIALIZED.value:
            self._phase_helper(do_if_not_started=None,
                               next_phase=PC.PHASE_2_PRIMING_INIT_PURGE_TO_WASTE)
            repeat = True

        elif self.phase_setpoint.value == PC.PHASE_2_PRIMING_INIT_PURGE_TO_WASTE.value:
            self._phase_helper(do_if_not_started=self.do_initial_purge_to_waste,
                               next_phase=PC.PHASE_2_PRIMING_WITHDRAW)

        elif self.phase_setpoint.value == PC.PHASE_2_PRIMING_WITHDRAW.value:
            self._phase_helper(do_if_not_started=self.do_phase_2_priming_withdraw,
                               next_phase=PC.PHASE_2_PRIMING_FINAL_PURGE_TO_WASTE)

        elif self.phase_setpoint.value == PC.PHASE_2_PRIMING_FINAL_PURGE_TO_WASTE.value:
            self._phase_helper(do_if_not_started=self.do_phase_2_priming_final_purge_to_waste,
                               next_phase=PC.PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW)

        elif self.phase_setpoint.value == PC.PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW.value:
            self._phase_helper(do_if_not_started=self.do_phase_2_monomer_b_and_initiator_b_withdraw,
                               next_phase=PC.PHASE_2_OUTPUT_PRIMING)

        elif self.phase_setpoint.value == PC.PHASE_2_OUTPUT_PRIMING.value:
            # on the first dispense we need to prime,
            # otherwise straight to dispense at dispense_rate
            if self._monomer_b_dispensed_ul_counter == 0 or self._initiator_b_dispensed_ul_counter == 0:
                self._phase_helper(do_if_not_started=self.do_phase_2_output_tubing_prime,
                                   next_phase=PC.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B)
            else:
                self._phase_helper(do_if_not_started=None,
                                   next_phase=PC.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B)
                repeat = True

        elif self.phase_setpoint.value == PC.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B.value:
            if self.current_phase_status == ReactionStation.CurrentPhaseStatus.NOT_STARTED.value:
                self._phase_helper(do_if_not_started=self.do_phase_2_monomer_b_and_initiator_b_dispense,
                                   next_phase=PC.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B)
            else:
                # if self._monomer_b_dispensed_ul_counter >= self.monomer_b_volume_to_dispense_ul
                # then we should continue to output purge, otherwise reload
                if self._monomer_b_dispensed_ul_counter >= self.monomer_b_volume_to_dispense_ul:
                    self._phase_helper(do_if_not_started=None,
                                       next_phase=PC.PHASE_2_OUTPUT_PURGE)
                # reload
                else:
                    self._phase_helper(do_if_not_started=None,
                                       next_phase=PC.PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW)
                    repeat = True

        elif self.phase_setpoint.value == PC.PHASE_2_OUTPUT_PURGE.value:
            self._phase_helper(do_if_not_started=self.do_phase_2_output_purge,
                               next_phase=PC.PHASE_2_COMPLETE)

        elif self.phase_setpoint.value == PC.PHASE_2_COMPLETE.value:
            if self._repeat is True:
                self.reset()
                self.phase_setpoint.update(PC.PHASE_1_INITIALIZED.value)
            else:
                self.enabled_setpoint.update(ReactionStation.Enabled.DISABLED.value)

        log_str += f"{ReactionStation.phase_to_str(self.phase_setpoint.value)}" \
                   f"({self.phase_setpoint.value}[{self.current_phase_status}])"

        print(log_str)

        if self.logging_enabled:
            self._aqueduct.log(log_str)
            self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

        if repeat is True:
            self.do_next_phase()

    def do_initial_purge_to_waste(self) -> None:
        """
        Purge both the monomer and initiator inputs.

        1) Set the monomer and initiator inputs to waste_port

        2) Set the plunger resolution of both pumps to N0 to allow for max velocity.

        3) Perform a full infuse at a maximum of 50 mL/min for each pump.

        :return:
        """

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.waste_port)
        initiator_valve_command_t = self._devices.PUMP.make_valve_command(position=self.initiator_input.waste_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        # we need to set the plunger resolution to N0 if it's been set to N2
        for pump_input, name in zip((self.monomer_input, self.initiator_input), ("monomer", "initiator")):
            self.set_plunger_mode(pump_input=pump_input, target_mode=0, pump_name=name)

        # limit purging rate to a max of 50 mL/min
        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.continuous,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=min(self._devices.PUMP.get_max_rate_ul_min(self.monomer_input.index), 50000)
        )

        # limit purging rate to a max of 50 mL/min
        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.continuous,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=min(self._devices.PUMP.get_max_rate_ul_min(self.initiator_input.index), 50000)
        )

        self._devices.PUMP.pump(**{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        time.sleep(0.5)

    def do_phase_1_priming_withdraw(self) -> None:
        """
        Prime the monomer pump_input with monomer A.

        1) Set the monomer input to the monomer_A_input_port

        2) Perform a finite withdraw at `monomer_a_withdraw_rate_ul_min` for `monomer_a_priming_volume_ul` uL

        :return:
        """

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.monomer_A_input_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_a_withdraw_rate_ul_min,
            finite_value=self.monomer_input.monomer_a_priming_volume_ul,
            finite_units=self._devices.PUMP.ul,
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{self.monomer_input.index}": pump_command_t})

        _ = f"Station {self.index}: priming wdrw {self.monomer_input.monomer_a_priming_volume_ul} " \
            f"uL mon. A at {self.monomer_a_withdraw_rate_ul_min} uL/min"
        print(_)

        if self.logging_enabled:
            self._aqueduct.log(_)

        time.sleep(0.5)

    def do_phase_1_priming_final_purge_to_waste(self) -> None:
        """
        After priming monomer A, purge any excess to waste.

        1) Set the monomer input to the waste_port

        2) Perform a full infusion at the pump inputs maximum rate.

        :return:
        """

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.waste_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        purge_rate_ul_min = min(self._devices.PUMP.get_max_rate_ul_min(self.monomer_input.index), 20000)

        pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.continuous,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=purge_rate_ul_min
        )

        self._devices.PUMP.pump(**{f"pump{self.monomer_input.index}": pump_command_t})

        time.sleep(0.5)

    def do_phase_1_monomer_a_withdraw(self) -> None:
        """
        Withdraw either enough monomer A to do the full dispense or as much as the syringe will allow.

        1) Set the monomer input to the monomer_A_input_port

        2) Set the plunger resolution to N0 mode to enable faster withdraw (we could be re-entering this method after
            doing a monomer dispense at a low flow rate, so the resolution may be N2)

        3) Withdraw the minimum of:
            -> `monomer_a_volume_to_dispense_ul` - `_monomer_a_dispensed_ul_counter` (the difference between target
                volume and the volume dispensed so far)
            -> the syringe volume

            at `monomer_a_withdraw_rate_ul_min`

        :return:
        """

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.monomer_A_input_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        # we need to set the plunger resolution to N0 if it's been set to N2
        self.set_plunger_mode(pump_input=self.monomer_input, target_mode=0, pump_name="monomer")

        withdraw_rate = self.monomer_a_withdraw_rate_ul_min

        withdraw_volume_ul = self.monomer_a_volume_to_dispense_ul - self._monomer_a_dispensed_ul_counter

        # if this is the first infusion, we need to withdraw extra to allow for priming the output tubing
        if self._monomer_a_infusions_counter == 0:
            withdraw_volume_ul += self.monomer_a_output_tubing_prime_volume_ul

        withdraw_volume_ul = min(withdraw_volume_ul, self.monomer_input.get_syringe_volume_ul())

        pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=withdraw_rate,
            finite_units=self._devices.PUMP.ul,
            finite_value=withdraw_volume_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{self.monomer_input.index}": pump_command_t})

        self._last_monomer_withdraw_volume_ul = withdraw_volume_ul

        _ = f"Station {self.index}: wdrw {withdraw_volume_ul} uL mon. A at {withdraw_rate} uL/min"
        print(_)
        if self.logging_enabled:
            self._aqueduct.log(_)

        time.sleep(0.5)

    def do_phase_1_output_tubing_prime(self) -> None:
        """
        Quickly infuse monomer A to the end of the output tubing. This is done to avoid dispensing slowly
        at the target dispense rate while no liquid has reached the end of the tubing.

        1) Set the monomer input to the output_port

        2) Infuse `monomer_a_output_tubing_prime_volume_ul` at `monomer_a_output_tubing_prime_rate_ul_min`

        :return:
        """

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.output_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_a_output_tubing_prime_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=self.monomer_a_output_tubing_prime_volume_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{self.monomer_input.index}": pump_command_t})

        time.sleep(0.5)

    def do_phase_1_monomer_a_dispense(self, monomer_a_to_dispense_ul: float = None, is_air: bool = False) -> None:
        """
        Now we begin dispensing monomer A at the target rate into the reaction vessel.

        1) Set the monomer input to the output_port (should already be there, but just to be safe...)

        2) Set the plunger resolution to N2 mode to enable slower infusion, if necessary

        3) Infuse `monomer_a_to_dispense_ul` at `monomer_a_dispense_rate_ul_min`

        :return:
        """

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.output_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        # we need to set the plunger resolution to N2 if the target rate is less than what's achievable
        # with N0 mode
        if self.monomer_a_dispense_rate_ul_min <= 8 * self.monomer_input.get_min_rate_ul_min():
            self.set_plunger_mode(pump_input=self.monomer_input, target_mode=2, pump_name="monomer")

        if monomer_a_to_dispense_ul is None:
            # account for plunger movement to prime output tubing if this is the first infusion
            if self._monomer_a_infusions_counter == 0:
                monomer_a_to_dispense_ul = (self._last_monomer_withdraw_volume_ul
                                            - self.monomer_a_output_tubing_prime_volume_ul)
            else:
                monomer_a_to_dispense_ul = self._last_monomer_withdraw_volume_ul

        pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_a_dispense_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=monomer_a_to_dispense_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{f"pump{self.monomer_input.index}": pump_command_t})

        self._monomer_a_dispensed_ul_counter += monomer_a_to_dispense_ul
        self._monomer_a_infusions_counter += 1

        if is_air is not True:

            _ = (f"Station {self.index}: inf {self._monomer_a_dispensed_ul_counter} of "
                 f"{self.monomer_a_volume_to_dispense_ul} uL mon. A at {self.monomer_a_dispense_rate_ul_min} uL/min")

        else:

            _ = (f"Station {self.index}: inf residual "
                 f"{self.monomer_a_volume_to_dispense_ul} uL mon. A at "
                 f"{self.monomer_a_dispense_rate_ul_min} uL/min with air")

        print(_)
        if self.logging_enabled:
            self._aqueduct.log(_)

        time.sleep(0.5)

    def do_phase_1_output_purge(self) -> None:
        """
        At this point, we've expelled the target volume of monomer A into the reaction vessel,
        so we need to withdraw the residual and expel it to waste.

        1) Set the plunger resolution to N0 mode to enable higher velocities

        2) Do a withdraw of 2 * (output_tubing_volume_ul + waste_tubing_volume_ul) at max of 50 mL/min

        3) Set the valve to waste

        4) do a full infusion at max of 50 mL/min

        :return:
        """

        # we need to set the plunger resolution to N0 if it's been set to N2
        self.set_plunger_mode(pump_input=self.monomer_input, target_mode=0, pump_name="monomer")

        withdraw_rate_ul_min = min(50000., self.monomer_input.get_max_rate_ul_min())
        withdraw_volume_ul = 2 * (
                self.monomer_input.output_tubing_volume_ul + self.monomer_input.output_tubing_volume_ul)

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=withdraw_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=withdraw_volume_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
        })

        # wait for completion
        while self._devices.PUMP.is_active(**{f"pump{self.monomer_input.index}": 1}):
            time.sleep(1)

        valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.waste_port)

        self._devices.PUMP.set_valves(**{f"pump{self.monomer_input.index}": valve_command_t})

        time.sleep(0.5)

        # switch the direction
        monomer_pump_command_t.direction = self._devices.PUMP.infuse

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
        })

        # wait for completion
        while self._devices.PUMP.is_active(**{f"pump{self.monomer_input.index}": 1}):
            time.sleep(1)

    def do_phase_2_priming_withdraw(self) -> None:
        """
        Prime the monomer pump_input with monomer B and the initiator_input with initiator B.

        1) Set the monomer input to the monomer_B_input_port and the initiator input to initiator_input_port

        2) Perform a finite withdraw of the monomer input at `monomer_b_withdraw_rate_ul_min` for
           `monomer_input.monomer_b_priming_volume_ul` uL and a finite withdraw of the initiator input
           at `initiator_b_withdraw_rate_ul_min` for `initiator_input.initiator_priming_volume_ul`

        :return:
        """

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(
            position=self.monomer_input.monomer_B_input_port)

        initiator_valve_command_t = self._devices.PUMP.make_valve_command(
            position=self.initiator_input.initiator_input_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_b_withdraw_rate_ul_min,
            finite_value=self.monomer_input.monomer_b_priming_volume_ul,
            finite_units=self._devices.PUMP.ul,
        )

        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.initiator_b_withdraw_rate_ul_min,
            finite_value=self.initiator_input.initiator_priming_volume_ul,
            finite_units=self._devices.PUMP.ul,
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        _ = f"Station {self.index}: Priming wdrw {self.monomer_input.monomer_b_priming_volume_ul} uL mon. B at " \
            f"{self.monomer_b_withdraw_rate_ul_min} " \
            f"uL/min and {self.initiator_input.initiator_priming_volume_ul} uL init. B " \
            f"at {self.initiator_b_withdraw_rate_ul_min} uL/min"

        print(_)

        time.sleep(0.5)

    def do_phase_2_priming_final_purge_to_waste(self) -> None:
        """
        After priming monomer B and initiator B, purge any excess to waste.

        1) Set the monomer input to the waste_port and the initiator input to the waste port

        2) Perform a full infusion of both pump inputs at each pump input's maximum rate.

        :return:
        """

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.waste_port)
        initiator_valve_command_t = self._devices.PUMP.make_valve_command(position=self.initiator_input.waste_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.continuous,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=min(self._devices.PUMP.get_max_rate_ul_min(self.monomer_input.index), 20000)
        )

        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.continuous,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=min(self._devices.PUMP.get_max_rate_ul_min(self.initiator_input.index), 20000)
        )

        self._devices.PUMP.pump(**{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        time.sleep(0.5)

    def do_phase_2_monomer_b_and_initiator_b_withdraw(self) -> None:
        """
        Withdraw either enough monomer B and initiator B to do the
        full dispense or as much as the syringes will allow.

        1) Check to see whether the monomer_input and/or the initiator_input are active (plunger moving). If an
            input is not active, then we need to reload the syringe by doing a withdrawal. Stop both
            inputs to ensure we're not dispensing one of the outputs while the other is being reloaded.

        2) If the monomer input is not active, set the monomer input to monomer_B_input_port. If the
            initiator input is not active, set the initiator input to the initiator_input_port.

        2) For the inactive inputs, set the plunger resolutions to N0 mode to enable faster withdraw
            (we could be re-entering this method after doing a dispense at a low flow rate, so the resolution may be N2)

        3) Calculate the monomer pump run time in seconds based on the:
             the minimum of:
                -> `monomer_b_volume_to_dispense_ul` - `_monomer_b_dispensed_ul_counter` (the difference between target
                    volume and the volume dispensed so far)
                -> the monomer syringe volume

                at `monomer_b_dispense_rate_ul_min`

        4) Calculate the initiator pump run time in seconds based on the:
            the minimum of:
                -> `calc_initiator_b_volume_to_dispense_ul()` - `_initiator_b_dispensed_ul_counter` (the difference
                    between the target volume and the volume dispensed so far)
                -> the initiator syringe volume

        5) Take the minimum of the monomer and initiator pump run times as the actual run time.

        6) Calculate the volumes of monomer B and initiator B needed to run at the target dispense rates for these
           times.

        7) If the monomer input is not active, withdraw `monomer_b_withdraw_volume_ul` at
            `monomer_b_dispense_rate_ul_min`. If the initiator input is not active, `init_b_withdraw_volume_ul`
            initiator B at `initiator_b_dispense_rate_ul_min`

        :return:
        """
        is_active = self._devices.PUMP.get_status()

        monomer_is_active = is_active[self.monomer_input.index]
        initiator_is_active = is_active[self.initiator_input.index]

        # stop both pumps
        if not monomer_is_active or not initiator_is_active:
            self._devices.PUMP.stop(**{
                f"pump{self.monomer_input.index}": True,
                f"pump{self.initiator_input.index}": True,
            })

        monomer_valve_command_t, initiator_valve_command_t = None, None

        if not monomer_is_active:
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.monomer_input.monomer_B_input_port)

        if not initiator_is_active:
            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.initiator_input.initiator_input_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        # we need to set the plunger resolution to N0 if it's been set to N2
        for pump_input, name, input_is_active in zip(
                (self.monomer_input, self.initiator_input),
                ("monomer", "initiator"),
                (monomer_is_active, initiator_is_active)
        ):
            if not input_is_active:
                self.set_plunger_mode(pump_input=pump_input, target_mode=0, pump_name=name)

        if not monomer_is_active:

            # we need to withdraw equal dispense-rate weighted volumes, taking into account the
            # syringe size that will be limiting the max time that we can infuse
            monomer_b_withdraw_vol_ul = self.monomer_b_volume_to_dispense_ul - self._monomer_b_dispensed_ul_counter

            # if this will be our first infusion, we need to withdraw extra to allow for
            # priming the tubing output
            if self._monomer_b_infusions_counter == 0:
                monomer_b_withdraw_vol_ul += self.monomer_b_output_tubing_prime_volume_ul

            self._last_monomer_withdraw_volume_ul = min(
                monomer_b_withdraw_vol_ul,
                self.monomer_input.get_syringe_volume_ul()
            )

        else:

            # set the _last_monomer_withdraw_volume_ul value to 0 as we're not withdrawing
            self._last_monomer_withdraw_volume_ul = 0

        if not initiator_is_active:

            initiator_b_withdraw_vol_ul = (self.calc_initiator_b_volume_to_dispense_ul() -
                                           self._initiator_b_dispensed_ul_counter)

            # if this will be our first infusion, we need to withdraw extra to allow for
            # priming the tubing output
            if self._initiator_b_infusions_counter == 0:
                initiator_b_withdraw_vol_ul += self.initiator_b_output_tubing_prime_volume_ul

            self._last_initiator_withdraw_volume_ul = min(
                initiator_b_withdraw_vol_ul,
                self.initiator_input.get_syringe_volume_ul()
            )

        else:

            # set the _last_initiator_withdraw_volume_ul value to 0 as we're not withdrawing
            self._last_initiator_withdraw_volume_ul = 0

        monomer_pump_command_t, initiator_pump_command_t = None, None

        if not monomer_is_active:
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.withdraw,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=self.monomer_b_withdraw_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=self._last_monomer_withdraw_volume_ul
            )

        if not initiator_is_active:
            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.withdraw,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=self.initiator_b_withdraw_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=self._last_initiator_withdraw_volume_ul
            )

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        _ = f"Station {self.index}: wdrw {self._last_monomer_withdraw_volume_ul} uL mon. B at " \
            f"{self.monomer_b_withdraw_rate_ul_min} " \
            f"uL/min and {self._last_initiator_withdraw_volume_ul} uL init. B " \
            f"at {self.initiator_b_withdraw_rate_ul_min} uL/min"

        print(_)
        if self.logging_enabled:
            self._aqueduct.log(_)

        time.sleep(0.5)

    def do_phase_2_output_tubing_prime(self) -> None:
        """
        Quickly infuse monomer B and initiator B to the end of their respective output tubing.
        This is done to avoid dispensing slowly at the target dispense rate while no liquid has reached the end of the tubing.

        1) Set the monomer input to the output_port and the initiator input to the output_port

        2) Infuse `monomer_b_output_tubing_prime_rate_ul_min` at `monomer_b_output_tubing_prime_rate_ul_min` and
           `initiator_b_output_tubing_prime_volume_ul` at `initiator_b_output_tubing_prime_rate_ul_min`

        :return:
        """

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.output_port)
        initiator_valve_command_t = self._devices.PUMP.make_valve_command(position=self.initiator_input.output_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_b_output_tubing_prime_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=self.monomer_b_output_tubing_prime_volume_ul
        )

        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.initiator_b_output_tubing_prime_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=self.initiator_b_output_tubing_prime_volume_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        time.sleep(0.5)

    def do_phase_2_monomer_b_and_initiator_b_dispense(
            self,
            monomer_b_to_dispense_ul: float = None,
            initiator_b_to_dispense_ul: float = None) -> None:
        """
        Now we begin dispensing monomer and initiator B at their respective target rates into the reaction vessel.

        1) Set the monomer input to the output_port (should already be there, but just to be safe...) and the
           initiator input to the output_port (should already be there, but just to be safe...)

        2) Set the plunger resolutions to N2 mode to enable slower infusion, if necessary

        3) Infuse `monomer_a_to_dispense_ul` at `monomer_a_dispense_rate_ul_min`

        :return:
        """

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.output_port)
        initiator_valve_command_t = self._devices.PUMP.make_valve_command(position=self.initiator_input.output_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t,
        })

        time.sleep(0.5)

        # we need to set the plunger resolution to N2 if the target rate is less than what's achievable
        # with N0 mode
        for pump_input, name, dispense_rate in zip(
                (self.monomer_input, self.initiator_input),
                ("monomer", "initiator"),
                (self.monomer_b_dispense_rate_ul_min, self.initiator_b_dispense_rate_ul_min),
        ):
            if dispense_rate <= 8 * pump_input.get_min_rate_ul_min():
                self.set_plunger_mode(pump_input=pump_input, target_mode=2, pump_name=name)

        if monomer_b_to_dispense_ul is None:
            if self._last_monomer_withdraw_volume_ul != 0:
                self._monomer_b_dispense_volume_ul = self._last_monomer_withdraw_volume_ul
            if self._monomer_b_infusions_counter == 0:
                self._monomer_b_dispense_volume_ul -= self.monomer_b_output_tubing_prime_volume_ul

        else:
            self._monomer_b_dispense_volume_ul = monomer_b_to_dispense_ul

        if initiator_b_to_dispense_ul is None:
            if self._last_initiator_withdraw_volume_ul != 0:
                self._initiator_b_dispense_volume_ul = self._last_initiator_withdraw_volume_ul
            else:
                self._initiator_b_dispense_volume_ul = self.initiator_input.get_syringe_volume_ul()
            if self._initiator_b_infusions_counter == 0:
                self._initiator_b_dispense_volume_ul -= self.initiator_b_output_tubing_prime_volume_ul

        else:
            self._initiator_b_dispense_volume_ul = initiator_b_to_dispense_ul

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.monomer_b_dispense_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=self._monomer_b_dispense_volume_ul
        )

        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.infuse,
            rate_units=self._devices.PUMP.ul_min,
            rate_value=self.initiator_b_dispense_rate_ul_min,
            finite_units=self._devices.PUMP.ul,
            finite_value=self._initiator_b_dispense_volume_ul
        )

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        if self._last_monomer_withdraw_volume_ul > 0:
            self._monomer_b_dispensed_ul_counter += self._monomer_b_dispense_volume_ul
            self._monomer_b_infusions_counter += 1

        if self._last_initiator_withdraw_volume_ul > 0:
            self._initiator_b_dispensed_ul_counter += self._initiator_b_dispense_volume_ul
            self._initiator_b_infusions_counter += 1

        _ = (f"Station {self.index}: inf {self._monomer_b_dispensed_ul_counter} "
             f"of {self.monomer_b_volume_to_dispense_ul} uL mon. B at "
             f"{self.monomer_b_dispense_rate_ul_min} uL/min and "
             f"{self._initiator_b_dispensed_ul_counter} of "
             f"{self.calc_initiator_b_volume_to_dispense_ul()} uL init. B at "
             f"{self.initiator_b_dispense_rate_ul_min} uL/min")

        print(_)
        if self.logging_enabled:
            self._aqueduct.log(_)

        time.sleep(0.5)

    def do_phase_2_output_purge(self, do_monomer: bool = True, do_initiator: bool = True,
                                wait_for_all: bool = False) -> None:
        """


        At this point, we've expelled the target volumes of monomer B and initiator B
        into the reaction vessel, so we need to withdraw the residuals and expel them to waste.

        1) Set the plunger resolutions to N0 mode to enable higher velocities

        2) Do a withdraw of 2 * (output_tubing_volume_ul + waste_tubing_volume_ul) at max of 50 mL/min
           for each input

        3) Set the valves to waste

        4) do a full infusion at max of 50 mL/min

        :return:
        """

        # we need to set the plunger resolution to N0 if it's been set to N2
        for pump_input, name in zip((self.monomer_input, self.initiator_input), ("monomer", "initiator")):
            self.set_plunger_mode(pump_input=pump_input, target_mode=0, pump_name=name)

        monomer_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            finite_units=self._devices.PUMP.ul,
        )

        initiator_pump_command_t = self._devices.PUMP.make_command(
            mode=self._devices.PUMP.finite,
            direction=self._devices.PUMP.withdraw,
            rate_units=self._devices.PUMP.ul_min,
            finite_units=self._devices.PUMP.ul,
        )

        # Do a withdraw of 2 * (output_tubing_volume_ul + waste_tubing_volume_ul) at max of 50 mL/min
        # for each input
        for pump_input, name, command in zip(
                (self.monomer_input, self.initiator_input),
                ("monomer", "initiator"),
                (monomer_pump_command_t, initiator_pump_command_t)
        ):
            withdraw_rate_ul_min = min(50000., pump_input.get_max_rate_ul_min())
            withdraw_volume_ul = 2 * (pump_input.output_tubing_volume_ul + pump_input.output_tubing_volume_ul)
            command.rate_value = withdraw_rate_ul_min
            command.finite_value = withdraw_volume_ul

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        # wait for completion
        while self._devices.PUMP.is_active(**{f"pump{self.monomer_input.index}": 1,
                                              f"pump{self.initiator_input.index}": 1}):
            time.sleep(1)

        monomer_valve_command_t = self._devices.PUMP.make_valve_command(position=self.monomer_input.waste_port)
        initiator_valve_command_t = self._devices.PUMP.make_valve_command(position=self.initiator_input.waste_port)

        self._devices.PUMP.set_valves(**{
            f"pump{self.monomer_input.index}": monomer_valve_command_t,
            f"pump{self.initiator_input.index}": initiator_valve_command_t
        })

        time.sleep(0.5)

        monomer_pump_command_t.direction = self._devices.PUMP.infuse
        initiator_pump_command_t.direction = self._devices.PUMP.infuse

        self._devices.PUMP.pump(wait_for_complete=False, **{
            f"pump{self.monomer_input.index}": monomer_pump_command_t,
            f"pump{self.initiator_input.index}": initiator_pump_command_t,
        })

        # wait for completion
        while self._devices.PUMP.is_active(**{f"pump{self.monomer_input.index}": 1,
                                              f"pump{self.initiator_input.index}": 1}):
            time.sleep(1)


class ReactionProcessHandler(object):
    """
    Class to handle processing each of the reaction stations
    as they proceed through the forumulation steps.

    """

    stations: Tuple[ReactionStation] = None

    # control the period in seconds at which
    # the process prints the status of all stations to screen
    status_print_interval_s: float = 360.
    last_status_print_time: float = None

    # the heartbeat interval in seconds to wait between processing
    # any events
    interval_s: int = 1

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

        _t = []

        for i in range(0, 4):
            _initiator_input = InitiatorPumpInput(index=2 * i, devices_obj=self._devices)
            _monomer_input = MonomerPumpInput(index=2 * i + 1, devices_obj=self._devices)

            _reaction_station = ReactionStation(
                index=i,
                devices_obj=devices_obj,
                aqueduct=aqueduct
            )

            _reaction_station.initiator_input = _initiator_input
            _reaction_station.monomer_input = _monomer_input

            _t.append(_reaction_station)

        self.stations = tuple(_t)

        del _t

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
        self._aqueduct.save_log_file(self.stations[0].log_file_name, overwrite=True)

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

    def get_active_pump_inputs(self) -> Tuple[bool]:
        """
        Method used to determine which stations are active, meaning the plunger is
        currently in motion. If the station is not active, then we'll check to see
        which of the steps needs to be performed next.

        :return:
        """

        # create a list of length stations and set all entries to False
        _s = len(self.stations) * [False]

        # get the status of all the pumps, this returns a tuple
        # of boolean values
        is_active = self._devices.PUMP.get_status()

        for _n, s in enumerate(self.stations):
            # for all but the co-dispense and phase 2 withdraw phases, either pump operating is enough to consider
            # the station active
            #
            # for the co-dispense phase, both pumps need to be operating
            if s.phase_setpoint.value in (
                    ReactionStation.Phase.PHASE_2_MONOMER_B_AND_INIT_B_WITHDRAW,
                    ReactionStation.Phase.PHASE_2_INFUSING_MONOMER_B_AND_INIT_B.value):
                condition = (is_active[s.monomer_input.index] and is_active[s.initiator_input.index])
            else:
                condition = (is_active[s.monomer_input.index] or is_active[s.initiator_input.index])
            if condition is True:
                _s[_n] = True
        return tuple(_s)

    def do_process(self):
        """
        The main function to run the process.

        :return:
        """
        # infinite loop
        while True:

            active_inputs = self.get_active_pump_inputs()
            for i, a in enumerate(active_inputs):
                if a is False and self.stations[i].enabled_setpoint.value == ReactionStation.Enabled.ENABLED.value:
                    self.stations[i].do_next_phase()

            self.print_station_status_at_interval()
            time.sleep(self.interval_s)

    def assign_novecare_process_params(self):
        """
        Stations 0 and 1 (pumps 0-3, all C24000)

        Pump 0, 2: C24000, 12.5mL for Sol 3
        Pump 1, 3: C24000, 5mL for Sol 1, 2

        Pump 0, 2 attainable rate: 109.375 uL/min
        Pump 1, 3 attainable rate: 93.75 uL/min

        Station 2 (pumps 4, 5, one C24000 and one C3000)

        Pump 4: C24000, 5mL for Sol 1, 2
        Pump 5: C3000, 12.5mL for Sol 3

        Pump 4 attainable rate: 109.375 uL/min
        Pump 5 attainable rate: 93.75 uL/min

        Station 3 (pumps 6, 7, two C3000s)

        Pump 6: C3000, 5mL for Sol 1, 2
        Pump 7: C3000, 5mL for Sol 3

        Pump 6 attainable rate: 109.375 uL/min
        Pump 7 attainable rate: 93.75 uL/min

        :return:
        """
        # round up when assigning flowrates

        # STATION 0
        # a C24000 pump with 5 mL syringe
        self.stations[0].monomer_input.index = 1
        # a C24000 pump with 12.5 mL syringe
        self.stations[0].initiator_input.index = 0

        self.stations[0].monomer_a_dispense_rate_ul_min = 15.7
        self.stations[0].monomer_a_volume_to_dispense_ul = 1000.

        # round up to the nearest decimal
        self.stations[0].monomer_b_dispense_rate_ul_min = 93.8
        self.stations[0].monomer_b_volume_to_dispense_ul = 17380.

        # round up to the nearest decimal
        self.stations[0].initiator_b_dispense_rate_ul_min = 109.4

        # STATION 1
        # a C24000 pump with 5 mL syringe
        self.stations[1].monomer_input.index = 3
        # a C24000 pump with 12.5 mL syringe
        self.stations[1].initiator_input.index = 2

        self.stations[1].monomer_a_dispense_rate_ul_min = 15.7
        self.stations[1].monomer_a_volume_to_dispense_ul = 1000.

        self.stations[1].monomer_b_dispense_rate_ul_min = 93.8
        self.stations[1].monomer_b_volume_to_dispense_ul = 17380.

        self.stations[1].initiator_b_dispense_rate_ul_min = 109.4

        # STATION 2
        # a C3000 pump with 5 mL syringe
        self.stations[2].monomer_input.index = 5
        # a C24000 pump with 12.5 mL syringe
        self.stations[2].initiator_input.index = 4

        self.stations[2].monomer_a_dispense_rate_ul_min = 13
        self.stations[2].monomer_a_volume_to_dispense_ul = 1000.

        self.stations[2].monomer_b_dispense_rate_ul_min = 93.8
        self.stations[2].monomer_b_volume_to_dispense_ul = 17380.

        self.stations[2].initiator_b_dispense_rate_ul_min = 109.4

        # STATION 3
        # a C3000 pump with 5 mL syringe
        self.stations[3].monomer_input.index = 7
        # a C3000 pump with 12.5 mL syringe
        self.stations[3].initiator_input.index = 6

        self.stations[3].monomer_a_dispense_rate_ul_min = 13
        self.stations[3].monomer_a_volume_to_dispense_ul = 1000.

        self.stations[3].monomer_b_dispense_rate_ul_min = 93.8
        self.stations[3].monomer_b_volume_to_dispense_ul = 17380.

        self.stations[3].initiator_b_dispense_rate_ul_min = 109.4

    def do_novecare_process(self):

        self.assign_novecare_process_params()
        self.do_process()

    def assign_techsol_process_params(self):
        """
        Stations 0 and 1 (pumps 0-3, all C24000)

        Pump 0, 2: C24000, 12.5mL for Sol 1
        Pump 1, 3: C24000, 5mL for Sol 2

        Pump 0, 2 attainable rate: 58.59375 uL/min
        Pump 1, 3 attainable rate: 18.75 uL/min

        Station 2 (pumps 4, 5, one C24000 and one C3000)

        Pump 4: C24000, 12.5mL for Sol 1
        Pump 5: C3000, 5mL for Sol 2

        Pump 4 attainable rate: 58.59375 uL/min
        Pump 5 attainable rate: 18.75 uL/min

        Station 3 (pumps 6, 7, two C3000s)

        Not active.

        :return:
        """
        # round up when assigning flowrates

        # STATION 0
        # a C24000 pump with 5 mL syringe, acrylic acid
        self.stations[0].monomer_input.index = 1
        # a C24000 pump with 5 mL syringe, H202
        self.stations[0].initiator_input.index = 0

        # round up to the nearest decimal
        self.stations[0].monomer_b_dispense_rate_ul_min = 18.8
        self.stations[0].monomer_b_volume_to_dispense_ul = 11600.

        # round up to the nearest decimal
        self.stations[0].initiator_b_dispense_rate_ul_min = 58.6

        # start the Tech Sol process at the co-dispense phase
        self.stations[0].phase_setpoint.update(ReactionStation.Phase.PHASE_2_INITIALIZED.value)

        # STATION 1
        # a C24000 pump with 5 mL syringe, acrylic acid
        self.stations[1].monomer_input.index = 3
        # a C24000 pump with 5 mL syringe, H202
        self.stations[1].initiator_input.index = 2

        self.stations[1].monomer_b_dispense_rate_ul_min = 18.8
        self.stations[1].monomer_b_volume_to_dispense_ul = 11600.

        self.stations[1].initiator_b_dispense_rate_ul_min = 58.6

        # start the Tech Sol process at the co-dispense phase
        self.stations[1].phase_setpoint.update(ReactionStation.Phase.PHASE_2_INITIALIZED.value)

        # STATION 2
        # a C3000 pump with 5 mL syringe, acrylic acid
        self.stations[2].monomer_input.index = 5
        # a C24000 pump with 5 mL syringe, H202
        self.stations[2].initiator_input.index = 4

        self.stations[2].monomer_b_dispense_rate_ul_min = 18.8
        self.stations[2].monomer_b_volume_to_dispense_ul = 11600.

        self.stations[2].initiator_b_dispense_rate_ul_min = 58.6

        # start the Tech Sol process at the co-dispense phase
        self.stations[2].phase_setpoint.update(ReactionStation.Phase.PHASE_2_INITIALIZED.value)

        # STATION 3
        # a C3000 pump with 5 mL syringe, acrylic acid
        self.stations[3].monomer_input.index = 7
        # a C3000 pump with 5 mL syringe, H202
        self.stations[3].initiator_input.index = 6

        self.stations[3].monomer_b_dispense_rate_ul_min = 18.8
        self.stations[3].monomer_b_volume_to_dispense_ul = 11600.

        self.stations[3].initiator_b_dispense_rate_ul_min = 62.5

        # start the Tech Sol process at the co-dispense phase
        self.stations[3].phase_setpoint.update(ReactionStation.Phase.PHASE_2_INITIALIZED.value)

    def do_techsol_process(self):

        self.assign_techsol_process_params()
        self.do_process()

    def do_cleaning_process(self, plunger_rate_ul_min: float = 50000):

        # configure with Tech Sol params
        self.assign_techsol_process_params()

        """
        Step 1:
        
        1) Set all valves to waste
        2) Do a full infuse of all plungers at 10 mL/min
        
        """
        valve_commands = {}

        for i, s in enumerate(self.stations):
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].monomer_input.waste_port)

            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].initiator_input.waste_port)

            valve_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
            })

        self._devices.PUMP.set_valves(**valve_commands)

        time.sleep(1)

        # run all syringes to full infuse at 10 mL/min
        pump_commands = {}

        for i, s in enumerate(self.stations):
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=10000,
            )

            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=10000,
            )

            pump_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
            })

        self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

        time.sleep(1)

        # this blocks while any of the inputs is active
        while any(a for a in self._devices.PUMP.get_status()):
            time.sleep(1)

        """
        Step 2:
        
        Do 3 cycles of:
            1) set monomer input valves to monomer input A
            2) do full withdraw at 50 mL/min
            3) set monomer input valves to waste
            4) do full infuse at 50 mL/min        
        
        """

        # we're going to do 3 withdraws from monomer A, infuse to waste
        for _ in range(0, 3):

            # set all monomer pump valves to monomer A
            valve_commands = {}

            for i, s in enumerate(self.stations):
                monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].monomer_input.monomer_A_input_port)

                valve_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                })

            self._devices.PUMP.set_valves(**valve_commands)

            time.sleep(1)

            # run all monomer syringes to full withdraw at 50 mL/min
            pump_commands = {}

            for i, s in enumerate(self.stations):
                monomer_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.withdraw,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                pump_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                })

            self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

            time.sleep(1)

            # this blocks while any of the inputs is active
            while any(a for a in self._devices.PUMP.get_status()):
                time.sleep(1)

            # set all monomer pump valves to waste
            valve_commands = {}

            for i, s in enumerate(self.stations):
                monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].monomer_input.waste_port)

                valve_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                })

            self._devices.PUMP.set_valves(**valve_commands)

            time.sleep(1)

            # run all monomer syringes to full infuse at 50 mL/min
            pump_commands = {}

            for i, s in enumerate(self.stations):
                monomer_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.infuse,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                pump_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                })

            self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

            time.sleep(1)

            # this blocks while any of the inputs is active
            while any(a for a in self._devices.PUMP.get_status()):
                time.sleep(1)

        """
        Step 3:
        
        Do 3 cycles of:
            1) set monomer input valves to monomer input B and initiator input valves to initiator input
            2) do full withdraw at 50 mL/min
            3) set monomer input and initiator input valves to output
            4) do full infuse at 50 mL/min        
        
        """

        # now we're going to do 3 withdraws from monomer B, initiator B, infuse to output
        for _ in range(0, 3):

            # set all monomer pump valves to monomer A
            valve_commands = {}

            for i, s in enumerate(self.stations):
                monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].monomer_input.monomer_B_input_port)

                initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].initiator_input.initiator_input_port)

                valve_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                    f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
                })

            self._devices.PUMP.set_valves(**valve_commands)

            time.sleep(1)

            # run all monomer syringes to full withdraw at 50 mL/min
            pump_commands = {}

            for i, s in enumerate(self.stations):
                monomer_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.withdraw,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                initiator_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.withdraw,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                pump_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                    f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
                })

            self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

            time.sleep(1)

            # this blocks while any of the inputs is active
            while any(a for a in self._devices.PUMP.get_status()):
                time.sleep(1)

            # set all monomer pump valves to waste
            valve_commands = {}

            for i, s in enumerate(self.stations):
                monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].monomer_input.output_port)

                initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                    position=self.stations[i].initiator_input.output_port)

                valve_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                    f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
                })

            self._devices.PUMP.set_valves(**valve_commands)

            time.sleep(1)

            # run all monomer syringes to full infuse at 50 mL/min
            pump_commands = {}

            for i, s in enumerate(self.stations):
                monomer_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.infuse,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                initiator_pump_command_t = self._devices.PUMP.make_command(
                    mode=self._devices.PUMP.continuous,
                    direction=self._devices.PUMP.infuse,
                    rate_units=self._devices.PUMP.ul_min,
                    rate_value=plunger_rate_ul_min,
                )

                pump_commands.update({
                    f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                    f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
                })

            self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

            time.sleep(1)

            # this blocks while any of the inputs is active
            while any(a for a in self._devices.PUMP.get_status()):
                time.sleep(1)

        """
        Step 4:
        
        1) Set valves to output   
        2) Do full withdraw at 50 mL/min
        3) Set valves to monomer A / initiator
        4) Do 1 mL infuse at 50 mL/min
        5) Set valves to monomer B / initiator   
        6) Do 1 mL infuse at 50 mL/min
        7) Set valves to waste   
        8) Do full infuse at 50 mL/min
        
        """

        # set all monomer pump valves to waste
        valve_commands = {}

        for i, s in enumerate(self.stations):
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].monomer_input.output_port)

            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].initiator_input.output_port)

            valve_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
            })

        self._devices.PUMP.set_valves(**valve_commands)

        time.sleep(1)

        # run all monomer syringes to full withdraw at 50 mL/min
        pump_commands = {}

        for i, s in enumerate(self.stations):
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.withdraw,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
            )

            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.withdraw,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
            )

            pump_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
            })

        self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

        time.sleep(1)

        # this blocks while any of the inputs is active
        while any(a for a in self._devices.PUMP.get_status()):
            time.sleep(1)

        # set all monomer pump valves to monomer A / initiator
        valve_commands = {}

        for i, s in enumerate(self.stations):
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].monomer_input.monomer_A_input_port)

            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].initiator_input.initiator_input_port)

            valve_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
            })

        self._devices.PUMP.set_valves(**valve_commands)

        time.sleep(1)

        # run all syringes 1 mL at 50 mL/min
        pump_commands = {}

        for i, s in enumerate(self.stations):
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=1000
            )

            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=1000
            )

            pump_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
            })

        self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

        time.sleep(1)

        # this blocks while any of the inputs is active
        while any(a for a in self._devices.PUMP.get_status()):
            time.sleep(1)

        # set all monomer pump valves to monomer B / initiator
        valve_commands = {}

        for i, s in enumerate(self.stations):
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].monomer_input.monomer_B_input_port)

            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].initiator_input.initiator_input_port)

            valve_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
            })

        self._devices.PUMP.set_valves(**valve_commands)

        time.sleep(1)

        # run all syringes 1 mL at 50 mL/min
        pump_commands = {}

        for i, s in enumerate(self.stations):
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=1000
            )

            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.finite,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
                finite_units=self._devices.PUMP.ul,
                finite_value=1000
            )

            pump_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
            })

        self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

        time.sleep(1)

        # this blocks while any of the inputs is active
        while any(a for a in self._devices.PUMP.get_status()):
            time.sleep(1)

        # set all monomer pump valves to waste
        valve_commands = {}

        for i, s in enumerate(self.stations):
            monomer_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].monomer_input.waste_port)

            initiator_valve_command_t = self._devices.PUMP.make_valve_command(
                position=self.stations[i].initiator_input.waste_port)

            valve_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_valve_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_valve_command_t
            })

        self._devices.PUMP.set_valves(**valve_commands)

        time.sleep(1)

        # run all syringes 1 mL at 50 mL/min
        pump_commands = {}

        for i, s in enumerate(self.stations):
            monomer_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
            )

            initiator_pump_command_t = self._devices.PUMP.make_command(
                mode=self._devices.PUMP.continuous,
                direction=self._devices.PUMP.infuse,
                rate_units=self._devices.PUMP.ul_min,
                rate_value=plunger_rate_ul_min,
            )

            pump_commands.update({
                f"pump{self.stations[i].monomer_input.index}": monomer_pump_command_t,
                f"pump{self.stations[i].initiator_input.index}": initiator_pump_command_t
            })

        self._devices.PUMP.pump(wait_for_complete=False, **pump_commands)

        time.sleep(1)

        # this blocks while any of the inputs is active
        while any(a for a in self._devices.PUMP.get_status()):
            time.sleep(1)

    def _test_novecare_station(self, stations: tuple = (), accel_factor: int = 32):
        """
        Internal testing method.

        Accelerate one of the reaction's stations process params to verify plunger logic.

        :param stations:
        :param accel_factor:
        :return:
        """

        self.assign_novecare_process_params()

        # disable all but the `station_index` station
        for index in stations:

            if index not in range(0, 4):
                print(f"Index: {index} not valid.")
                continue

            self.stations[index].enabled_setpoint.update(ReactionStation.Enabled.ENABLED.value)

            self.stations[index].monomer_a_dispense_rate_ul_min *= accel_factor
            self.stations[index].monomer_b_dispense_rate_ul_min *= accel_factor
            self.stations[index].initiator_b_dispense_rate_ul_min *= accel_factor

        self.do_process()

    def _test_techsol_station(self, station_index: int = 0, accel_factor: int = 32):
        """
        Internal testing method.

        Accelerate one of the reaction's stations process params to verify plunger logic.

        :param station_index:
        :param accel_factor:
        :return:
        """

        self.assign_techsol_process_params()

        # disable all but the `station_index` station
        for index in range(0, 4):
            if index != station_index:
                self.stations[index].enabled_setpoint.update(ReactionStation.Enabled.DISABLED.value)

        self.stations[station_index].monomer_b_dispense_rate_ul_min *= accel_factor
        self.stations[station_index].initiator_b_dispense_rate_ul_min *= accel_factor

        self.do_process()

    def do_accelerated_process(self):

        # disable all but the first (0th index) station
        for _ in (1, 2, 3):
            self.stations[_].enabled_setpoint.update(ReactionStation.Enabled.DISABLED.value)

        self.stations[0].monomer_a_dispense_rate_ul_min = 120.
        self.stations[0].monomer_a_volume_to_dispense_ul = 900.

        self.stations[0].monomer_b_dispense_rate_ul_min = 100.
        self.stations[0].monomer_b_volume_to_dispense_ul = 300.

        self.stations[0].initiator_b_dispense_rate_ul_min = 10.

        self.do_process()

    def csv_upload_with_header_row(self) -> list:
        """
        Prompt the user to upload a csv (comma separated values) file. Display the uploaded data for the
        user to confirm the uploaded data appears correct. Return a list of the user confirmed values.
        :return: new_list = a list of the user confirmed values
        """

        # prompt the user to upload a csv with the correct formatting.
        # Row 0 is the header row with data labels. Within a row the data (columns) are separated by commas.
        csv_ipt = self._aqueduct.input(
            message="Upload a CSV file. Within a row use commas to separate column entries from left to right. <br>"
                    "Each new line will be a new row.  <br>"
                    "Ensure row 0 is a header row (labels).  <br>",
            input_type="csv",
            dtype="str"
        )

        table_data = csv_ipt.get_value()
        as_list = json.loads(table_data)
        new_list = []
        labels = []

        # get the data labels and store in a list
        for column in as_list[0]:
            labels.append(column)

        # get the data starting at row index 1 (not row to omit the header row). Store the values in new_list.
        for i, r in enumerate(as_list[1::]):
            row_index = i
            row_contents = []
            for j, column in enumerate(r):
                row_contents.append(dict(
                    name=f"{labels[j]}", value=column))

            new_list.append(dict(
                hint=f"csv row: {row_index}",
                value=row_contents,
                dtype="list",
                name=f"data{i}"
            ))

        # prompt the user to confirm the uploaded csv data looks correct.
        tabular_ipt = self._aqueduct.input(
            message="Confirm the uploaded data.",
            input_type="table",
            dtype="str",
            rows=new_list,
        )

        # format the confirmed data (str) into a list and return the list new_rates.
        confirmed_values = json.loads(
            tabular_ipt.get_value())
        new_params = []

        for cv in confirmed_values:
            row = []
            for value in cv:
                try:
                    row.append(float((value.get('value'))))
                except ValueError:
                    row.append((value.get('value')))
            new_params.append(row)

        # params are a list of list with index row and columns:
        """
        Row 0 (Station 0)
            0: Reactor Index
            1: Temperature(C)
            2: Kettle_CTA(mL)
            3: Kettle_water(mL)
            4: Init_seed(mL)
            5: Mono_seed(mL)
            6: time_seed(h)
            7: Mono_seed_rate(uL / min)
            8: Init_polym(mL)
            9: Init_polym_rate(uL / min)
            10: Mono_polym(mL)
            11: Mono_polym_rate(uL / min)
            12: time_polym(h)
        Row 1 (Station 1) 
            ...
        """
        return new_params

    def do_novacare_with_csv_upload(self, column_mapping: enum.Enum = None):

        data = self.csv_upload_with_header_row()

        """
        `data` is a list of lists with format:
        
        [
            [ 
                0: Reactor Index
                1: Temperature(C)
                2: Kettle_CTA(mL)
                3: Kettle_water(mL)
                4: Init_seed(mL)
                5: Mono_seed(mL)
                6: time_seed(h)
                7: Mono_seed_rate(uL / min)
                8: Init_polym(mL)
                9: Init_polym_rate(uL / min)
                10: Mono_polym(mL)
                11: Mono_polym_rate(uL / min)
                12: time_polym(h)                
            ], 
            [ 
            ...
        ]
        
        so...
            data[0][0] is station 0 reactor index 
            data[1][0] is station 1 reactor index
            
            data[0][8] is init_polym(mL)
            etc.        
        """
        STATION_0_INDEX = 0
        STATION_1_INDEX = 1
        STATION_2_INDEX = 2
        STATION_3_INDEX = 3

        if not column_mapping:

            class ColumnMapping(enum.Enum):
                MONOMER_A_DISPENSE_RATE_UL_MIN_COL = 7
                MONOMER_A_VOLUME_TO_DISPENSE_COL = 5
                MONOMER_B_DISPENSE_RATE_UL_MIN_COL = 11
                MONOMER_B_VOLUME_TO_DISPENSE_COL = 10
                INITIATOR_B_DISPENSE_RATE_UL_MIN_COL = 9

            column_mapping = ColumnMapping

        # STATION 0
        # a C24000 pump with 5 mL syringe
        self.stations[0].monomer_input.index = 1
        # a C24000 pump with 12.5 mL syringe
        self.stations[0].initiator_input.index = 0

        self.stations[0].monomer_a_dispense_rate_ul_min = round(
            float(data[STATION_0_INDEX][column_mapping.MONOMER_A_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[0].monomer_a_volume_to_dispense_ul = round(
            float(data[STATION_0_INDEX][column_mapping.MONOMER_A_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[0].monomer_b_dispense_rate_ul_min = round(
            float(data[STATION_0_INDEX][column_mapping.MONOMER_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[0].monomer_b_volume_to_dispense_ul = round(
            float(data[STATION_0_INDEX][column_mapping.MONOMER_B_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[0].initiator_b_dispense_rate_ul_min = round(
            float(data[STATION_0_INDEX][column_mapping.INITIATOR_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)

        # STATION 1
        # a C24000 pump with 5 mL syringe
        self.stations[1].monomer_input.index = 3
        # a C24000 pump with 12.5 mL syringe
        self.stations[1].initiator_input.index = 2

        self.stations[1].monomer_a_dispense_rate_ul_min = round(
            float(data[STATION_1_INDEX][column_mapping.MONOMER_A_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[1].monomer_a_volume_to_dispense_ul = round(
            float(data[STATION_1_INDEX][column_mapping.MONOMER_A_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[1].monomer_b_dispense_rate_ul_min = round(
            float(data[STATION_1_INDEX][column_mapping.MONOMER_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[1].monomer_b_volume_to_dispense_ul = round(
            float(data[STATION_1_INDEX][column_mapping.MONOMER_B_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[1].initiator_b_dispense_rate_ul_min = round(
            float(data[STATION_1_INDEX][column_mapping.INITIATOR_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)

        # STATION 2
        # a C3000 pump with 5 mL syringe
        self.stations[2].monomer_input.index = 5
        # a C24000 pump with 12.5 mL syringe
        self.stations[2].initiator_input.index = 4

        self.stations[2].monomer_a_dispense_rate_ul_min = round(
            float(data[STATION_2_INDEX][column_mapping.MONOMER_A_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[2].monomer_a_volume_to_dispense_ul = round(
            float(data[STATION_2_INDEX][column_mapping.MONOMER_A_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[2].monomer_b_dispense_rate_ul_min = round(
            float(data[STATION_2_INDEX][column_mapping.MONOMER_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[2].monomer_b_volume_to_dispense_ul = round(
            float(data[STATION_2_INDEX][column_mapping.MONOMER_B_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[2].initiator_b_dispense_rate_ul_min = round(
            float(data[STATION_2_INDEX][column_mapping.INITIATOR_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)

        # STATION 3
        # a C3000 pump with 5 mL syringe
        self.stations[3].monomer_input.index = 7
        # a C3000 pump with 12.5 mL syringe
        self.stations[3].initiator_input.index = 6

        self.stations[3].monomer_a_dispense_rate_ul_min = round(
            float(data[STATION_3_INDEX][column_mapping.MONOMER_A_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[3].monomer_a_volume_to_dispense_ul = round(
            float(data[STATION_3_INDEX][column_mapping.MONOMER_A_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[3].monomer_b_dispense_rate_ul_min = round(
            float(data[STATION_3_INDEX][column_mapping.MONOMER_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)
        self.stations[3].monomer_b_volume_to_dispense_ul = round(
            float(data[STATION_3_INDEX][column_mapping.MONOMER_B_VOLUME_TO_DISPENSE_COL.value]) * 1000, 2)

        # round up to the nearest decimal
        self.stations[3].initiator_b_dispense_rate_ul_min = round(
            float(data[STATION_3_INDEX][column_mapping.INITIATOR_B_DISPENSE_RATE_UL_MIN_COL.value]), 2)

        self.do_process()
