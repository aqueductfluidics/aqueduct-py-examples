import datetime
import time
import enum
import json

import local.lib.dispensing.helpers
import local.lib.dispensing.methods
from local.lib.dispensing.classes import Devices
from local.lib.dispensing.definitions import *

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import Setpoint, ALLOWED_DTYPES
from aqueduct.core.recordable import Recordable

import aqueduct.devices.trcx.obj
import aqueduct.devices.trcx.constants

from typing import List, Tuple, Callable

DELAY_S = 0.2


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
    # start of phase 1
    PHASE_1_INITIALIZED = 0

    # set both pumps valves to waste,
    # infuse both pumps completely at max rate
    PHASE_1_PRIMING_INIT_PURGE_TO_WASTE = 1

    # set both pumps to input ports
    # withdraw enough volume to fill input tubing + some volume in syringe,
    # infuse at priming_withdraw_rate_ml_min
    PHASE_1_PRIMING_WITHDRAW = 2

    # set both pumps to waste 
    # infuse pump completely at priming_infuse_rate_(pump)_ml_min
    PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE = 3

    # now we need to withdraw the volumes necessary to do the co-dispense,
    # which might include the output tubing volume
    PHASE_1_FINAL_WITHDRAW = 4

    # now we set both pumps valves to output and
    # begin infusing to quickly run the
    # liquid slugs to almost the end of the tubing
    PHASE_1_OUTPUT_PRIMING = 5

    # now we begin infusing at the specified
    # addition rates
    PHASE_1_INFUSING = 6

    # withdraw residual volumes from the output lines and and send the liquids to waste
    PHASE_1_OUTPUT_PURGE = 7

    # phase 1 complete!
    PHASE_1_COMPLETE = 99


class CurrentPhaseStatus(enum.Enum):
    """
    Track the status of the current phase.
    """
    NOT_STARTED = 0
    STARTED = 1
    COMPLETE = 2


class CoDispenseStation(object):
    """
    Class to contain all relevant parameters for executing a 1 Phase codispense.
    """

    # each ReactionProcess has an index for the ReactionProcessHandler
    # list of stations
    index: int = 0

    # each ReactionProcess can be set to active or inactive
    # when the ProcessHandler encounters an inactive process
    # it won't take any action, to enable toggling of station's
    # enabled state we use an Aqueduct Setpoint
    enabled_setpoint: Setpoint = None

    # each ReactionProcess has a phase that tracks the infusion
    # process for pump0 and pump1, to enable toggling of station's
    # current phase we use an Aqueduct Setpoint
    phase_setpoint: Setpoint = None

    # make an Aqueduct Recordable to record/visualize pump0 dispensed
    pump0_dispensed_recordable: Recordable = None

    # make an Aqueduct Recordable to record/visualize pump1 dispensed
    pump1_dispensed_recordable: Recordable = None

    # track the status of the current phase using one of the CurrentPhaseStatus
    # enum's members
    current_phase_status: int = CurrentPhaseStatus.NOT_STARTED.value

    # logging
    logging_enabled: bool = True
    log_file_name: str = "codispense_"

    # each station must be assigned a pump index (0-11) for the two pumps
    pump0_input: int = 0
    pump1_input: int = 1

    _pump0_input_last_position_ul: float = None
    _pump1_input_last_position_ul: float = None

    pump0_input_port: int = 1
    pump0_output_port: int = 3
    pump0_waste_port: int = 4

    pump0_output_tubing_volume_ul: float = 350.
    pump0_priming_volume_ul: float = 151. + 300. + 200.

    pump1_input_port: int = 1
    pump1_output_port: int = 2
    pump1_waste_port: int = 3

    pump1_output_tubing_volume_ul: float = 350.
    pump1_priming_volume_ul: float = 151. + 300. + 200

    # pump 0 process params
    pump0_volume_to_dispense_ul: float = 36500
    pump0_dispense_rate_ul_min: float = 50.

    # volume and rate used to quickly prime to the end of the output
    # tubing line for the first dispense
    pump0_output_tubing_prime_volume_ul: float = 315.
    pump0_output_tubing_prime_rate_ul_min: float = 2000.

    # rate to use when withdrawing pump0
    pump0_withdraw_rate_ul_min: float = 25000.

    _pump0_dispensed_ul_counter: float = 0.
    _pump0_infusions_counter: int = 0
    _pump0_dispense_volume_ul: float = 0

    _realtime_pump0_dispensed_ul_counter: float = 0.

    # pump 1 process params
    pump1_volume_to_dispense_ul: float = 11600
    pump1_dispense_rate_ul_min: float = 15

    pump1_output_tubing_prime_volume_ul: float = 315.
    pump1_output_tubing_prime_rate_ul_min: float = 2000.

    # rate to use when withdrawing pump1
    pump1_withdraw_rate_ul_min: float = 25000.

    _pump1_dispensed_ul_counter: float = 0.
    _pump1_infusions_counter: int = 0
    _pump1_dispense_volume_ul: float = 0

    _last_pump0_withdraw_volume_ul: float = 0.
    _last_pump1_withdraw_volume_ul: float = 0.

    _pump0_dispense_complete: bool = False
    _pump1_dispense_complete: bool = False

    _realtime_pump1_dispensed_ul_counter: float = 0.

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
        return f"Station {self.index} (mon. {self.pump0_input}, init. {self.pump1_input}): " \
               f"enabled={self.enabled_setpoint.value}, phase={self.phase_setpoint.value}"

    def make_setpoints(self) -> None:
        """
        Method used to generate the:
            - enable_setpoint 
            - phase_setpoint
            - pump0_dispensed_recordable
            - pump1_dispensed_recordable

        :return:
        """

        self.enabled_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_enabled",
            value=Enabled.ENABLED.value,
            dtype=int.__name__
        )

        self.phase_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_phase",
            value=Phase.PHASE_1_INITIALIZED.value,
            dtype=int.__name__
        )

        self.pump0_dispensed_recordable = self._aqueduct.recordable(
            name=f"station_{self.index}_pump0_disp.",
            value=0.,
            dtype=float.__name__
        )

        self.pump1_dispensed_recordable = self._aqueduct.recordable(
            name=f"station_{self.index}_pump1_disp.",
            value=0.,
            dtype=float.__name__
        )

    def record(self, plunger_positions: Tuple[Tuple[int, any, any]]) -> None:
        """
        Method used to generate the enable_setpoint and phase_setpoint.

        :return:
        """
        if self.phase_setpoint.value == Phase.PHASE_1_INFUSING.value:
            if plunger_positions:

                position, status, resolution = plunger_positions[self.pump0_input]
                current_position_ul = local.lib.dispensing.methods.get_current_position_ul(
                    self._devices.PUMP,
                    index=self.pump0_input,
                    plunger_position=position,
                    plunger_resolution=resolution
                )
                
                if self._pump0_input_last_position_ul is None:
                    self._pump0_input_last_position_ul = current_position_ul
                else:
                    delta_ul = self._pump0_input_last_position_ul - current_position_ul
                    self._realtime_pump0_dispensed_ul_counter += round(delta_ul, 2)
                    self.pump0_dispensed_recordable.update(
                        round(self._realtime_pump0_dispensed_ul_counter, 2)
                    )
                    self._pump0_input_last_position_ul = current_position_ul

                position, status, resolution = plunger_positions[self.pump1_input]
                current_position_ul = local.lib.dispensing.methods.get_current_position_ul(
                    self._devices.PUMP,
                    index=self.pump1_input,
                    plunger_position=position,
                    plunger_resolution=resolution
                )
                
                if self._pump1_input_last_position_ul is None:
                    self._pump1_input_last_position_ul = current_position_ul
                else:
                    delta_ul = self._pump1_input_last_position_ul - current_position_ul
                    self._realtime_pump1_dispensed_ul_counter += round(delta_ul, 2)
                    self.pump1_dispensed_recordable.update(
                        round(self._realtime_pump1_dispensed_ul_counter, 2))
                    self._pump1_input_last_position_ul = current_position_ul

    def record_pump0_input_position(self, calc_delta: bool = False) -> float:
        plunger_positions = self._devices.PUMP.get_plunger_positions(
            # include_status=True,
            # include_resolution=True,
        )

        position, status, resolution = plunger_positions[self.pump0_input]
        current_position_ul = local.lib.dispensing.methods.get_current_position_ul(
            self._devices.PUMP,
            index=self.pump0_input,
            plunger_position=position,
            plunger_resolution=resolution
        )

        delta_ul = None

        if calc_delta:
            delta_ul = self._pump0_input_last_position_ul - current_position_ul

        self._pump0_input_last_position_ul = current_position_ul

        if calc_delta:
            return delta_ul

    def record_pump1_input_position(self, calc_delta: bool = False):
        plunger_positions = self._devices.PUMP.get_plunger_positions(
            # include_status=True,
            # include_resolution=True,
        )

        position, status, resolution = plunger_positions[self.pump1_input]
        current_position_ul = local.lib.dispensing.methods.get_current_position_ul(
            self._devices.PUMP,
            index=self.pump1_input,
            plunger_position=position,
            plunger_resolution=resolution
        )

        delta_ul = None

        if calc_delta:
            delta_ul = self._pump1_input_last_position_ul - current_position_ul

        self._pump1_input_last_position_ul = current_position_ul

        if calc_delta:
            return delta_ul

    def is_active(self, active_inputs: Tuple[bool]) -> bool:
        """
        Method to determine whether the station is active or needs to be moved on to the
        next phase in the process.

        :param active_inputs:
        :return:
        """
        pump0_is_active = active_inputs[self.pump0_input]
        pump1_is_active = active_inputs[self.pump1_input]

        # if we're in the PHASE_1_FINAL_WITHDRAW or PHASE_1_INFUSING
        # phases, both pumps must be active for the station to be considered active
        if self.phase_setpoint.value in (
                Phase.PHASE_1_FINAL_WITHDRAW,
                Phase.PHASE_1_INFUSING.value
        ):
            pump0_active = pump0_is_active or self._pump0_dispense_complete
            pump1_active = pump1_is_active or self._pump1_dispense_complete
            is_active = (pump0_active and pump1_active)
        # otherwise, only one pump must be active
        else:
            is_active = (pump0_is_active or pump1_is_active)

        return is_active

    def is_enabled(self) -> bool:
        """
        Method to determine whether the station is enabled.

        :return:
        """
        return self.enabled_setpoint.value == Enabled.ENABLED.value

    def reset_phase_1(self) -> None:
        """
        Reset the dispense counters for pump0 and pump1.

        """
        self._pump0_dispensed_ul_counter: float = 0.
        self._pump1_dispensed_ul_counter: float = 0.
        self._pump0_infusions_counter: int = 0
        self._pump1_infusions_counter: int = 0

    def reset(self) -> None:
        """
        Reset both Phase 1 and Phase 2 counters.

        """
        self.reset_phase_1()

    @staticmethod
    def phase_to_str(phase: int) -> str:
        """
        Helper method to convert the Phase Enum number to a readable string.

        :param phase:
        :return: human readable phase description
        """
        if phase == Phase.PHASE_1_INITIALIZED.value:
            return "initialized"
        elif phase == Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE.value:
            return "initial purge to waste"
        elif phase == Phase.PHASE_1_PRIMING_WITHDRAW.value:
            return "priming wdrw"
        elif phase == Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE.value:
            return "purge to waste"
        elif phase == Phase.PHASE_1_FINAL_WITHDRAW.value:
            return "final wdrw"
        elif phase == Phase.PHASE_1_OUTPUT_PRIMING.value:
            return "output priming"
        elif phase == Phase.PHASE_1_INFUSING.value:
            return "infusing"
        elif phase == Phase.PHASE_1_OUTPUT_PURGE.value:
            return "output purging"
        elif phase == Phase.PHASE_1_COMPLETE.value:
            return "phase 1 complete"

    def set_current_phase_status(self, phase_status: CurrentPhaseStatus) -> None:
        self.current_phase_status = phase_status.value

    def _phase_helper(
            self,
            do_if_not_started: Callable = None,
            next_phase: Phase = None,
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
        if self.current_phase_status == CurrentPhaseStatus.NOT_STARTED.value:
            self.set_current_phase_status(CurrentPhaseStatus.STARTED)
            if do_if_not_started is not None:
                if do_if_not_started_kwargs is not None:
                    do_if_not_started(**do_if_not_started_kwargs)
                else:
                    do_if_not_started()
        elif self.current_phase_status == CurrentPhaseStatus.STARTED.value:
            self.set_current_phase_status(CurrentPhaseStatus.NOT_STARTED)
            self.phase_setpoint.update(next_phase.value)

    def do_next_phase(self):

        # flag to repeat the method after printing the status update
        # initialized to False
        repeat: bool = False

        # start of a logging string that tracks the phase and status change
        log_str: str = f"Station {self.index}: {self.phase_to_str(self.phase_setpoint.value)}" \
                       f"({self.phase_setpoint.value}[{self.current_phase_status}]) -> "

        if self.phase_setpoint.value == Phase.PHASE_1_INITIALIZED.value:
            self._phase_helper(
                do_if_not_started=None,
                next_phase=Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE
            )

            # no action here, we just move on to the next phase
            repeat = True

        elif self.phase_setpoint.value == Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE.value:
            def to_do():
                """
                Purge both the pump0 and pump1 inputs.
                1) Set the plunger resolution of both pumps to N0 to allow for max velocity.
                2) Set the pump0 and pump1 inputs to waste_port
                3) Perform a full infuse at a maximum of 50 mL/min for each pump.
                :return:
                """
                local.lib.dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    target_modes=[0, 0],
                )

                time.sleep(DELAY_S)

                local.lib.dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_waste_port, self.pump1_waste_port],
                    infuse_rates_ul_min=[
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump0_input), 50000),
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump1_input), 50000)
                    ],
                    infuse_volumes_ul=[20000, 20000]  # larger than any syringe to ensure full infuse
                )

                log_string = f"Station {self.index}: Purging pumps to waste"

                print(log_string)
                # if self.logging_enabled:
                    # self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do,
                next_phase=Phase.PHASE_1_PRIMING_WITHDRAW
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_PRIMING_WITHDRAW.value:
            def to_do():
                """
                Prime the pump0 pump_input with pump0 and the pump1_input with pump1.
                1) Set the pump0 input to the pump0_input_port and the pump1 input to pump1_input_port
                2) Perform a finite withdraw of the pump0 input at `pump0_withdraw_rate_ul_min` for
                   `pump0_priming_volume_ul` uL and a finite withdraw of the pump1 input
                   at `pump1_withdraw_rate_ul_min` for `pump1_priming_volume_ul`

                :return:
                """
                local.lib.dispensing.methods.set_valves_and_withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_input_port, self.pump1_input_port],
                    withdraw_rates_ul_min=[self.pump0_withdraw_rate_ul_min, self.pump1_withdraw_rate_ul_min],
                    withdraw_volumes_ul=[self.pump0_priming_volume_ul, self.pump1_priming_volume_ul]
                )

                log_string = f"Station {self.index}: Priming wdrw {self.pump0_priming_volume_ul} uL pump0 at " \
                             f"{self.pump0_withdraw_rate_ul_min} " \
                             f"uL/min and {self.pump1_priming_volume_ul} uL pump1 " \
                             f"at {self.pump1_withdraw_rate_ul_min} uL/min"

                print(log_string)
                # if self.logging_enabled:
                #     self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do,
                next_phase=Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE.value:
            def to_do():
                """
                After priming pump0 and pump1, purge any excess to waste.
                1) Set the pump0 input to the waste_port and the pump1 input to the waste port
                2) Perform a full infusion of both pump inputs at each pump input's maximum rate.

                :return:
                """
                local.lib.dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_waste_port, self.pump1_waste_port],
                    infuse_rates_ul_min=[
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump0_input), 20000),
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump1_input), 20000),
                    ],
                    infuse_volumes_ul=[20000, 20000]
                )

                log_string = f"Station {self.index}: Phase 1 final purge to waste"

                print(log_string)
                # if self.logging_enabled:
                #     self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do,
                next_phase=Phase.PHASE_1_FINAL_WITHDRAW
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_FINAL_WITHDRAW.value:
            def to_do():
                """
                Withdraw either enough pump0 and pump1 to do the
                full dispense or as much as the syringes will allow.

                1) Check to see whether the pump0_input and/or the pump1_input are active (plunger moving). If an
                    input is not active, then we need to reload the syringe by doing a withdrawal. Stop both
                    inputs to ensure we're not dispensing one of the outputs while the other is being reloaded.

                2) If the pump0 input is not active, set the pump0 input to pump0_input_port. If the
                    pump1 input is not active, set the pump1 input to the pump1_input_port.

                2) For the inactive inputs, set the plunger resolutions to N0 mode to enable faster withdraw
                    (we could be re-entering this method after doing a dispense at a low flow rate,
                    so the resolution may be N2)

                3) Calculate the pump0 pump run time in seconds based on the:
                     the minimum of:
                        -> `pump0_volume_to_dispense_ul` - `_pump0_dispensed_ul_counter` (the difference
                            between target volume and the volume dispensed so far)
                        -> the pump0 syringe volume

                        at `pump0_dispense_rate_ul_min`

                4) Calculate the pump1 pump run time in seconds based on the:
                    the minimum of:
                        -> `pump1_volume_to_dispense_ul()` - `_pump1_dispensed_ul_counter` (the difference
                            between the target volume and the volume dispensed so far)
                        -> the pump1 syringe volume

                5) Take the minimum of the pump0 and pump1 pump run times as the actual run time.

                6) Calculate the volumes of pump0 and pump1 needed to run at the
                    target dispense rates for these times.

                7) If the pump0 input is not active, withdraw `pump0_withdraw_volume_ul` at
                    `pump0_dispense_rate_ul_min`. If the pump1 input is not active, `init_b_withdraw_volume_ul`
                    pump1 at `pump1_dispense_rate_ul_min`

                :return:
                """
                is_active = self._devices.PUMP.get_status()

                pump0_is_active = is_active[self.pump0_input]
                pump1_is_active = is_active[self.pump1_input]

                # stop both pumps if either is INactive
                if not pump0_is_active or not pump1_is_active:
                    local.lib.dispensing.methods.stop_pumps(
                        pump=self._devices.PUMP,
                        pump_indices=[self.pump0_input, self.pump1_input]
                    )

                # for the inactive pumps, set the valves to the input port and 
                # the plunger resolution to N0
                pump_indices = []
                ports = []
                target_modes = []

                if not pump0_is_active:
                    pump_indices.append(self.pump0_input)
                    ports.append(self.pump0_input_port)
                    target_modes.append(0)

                if not pump1_is_active:
                    pump_indices.append(self.pump1_input)
                    ports.append(self.pump1_input_port)
                    target_modes.append(0)

                # send the command to set the valves
                local.lib.dispensing.methods.set_valves(
                    pump=self._devices.PUMP,
                    pump_indices=pump_indices,
                    ports=ports
                )

                # send the command to set the plunger resolutions
                local.lib.dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=pump_indices,
                    target_modes=target_modes,
                )

                if not pump0_is_active:
                    # we need to withdraw equal dispense-rate weighted volumes, taking into account the
                    # syringe size that will be limiting the max time that we can infuse
                    pump0_to_withdraw_vol_ul = (
                            self.pump0_volume_to_dispense_ul - self._pump0_dispensed_ul_counter)

                    # if this will be our first infusion, we need to withdraw extra to allow for
                    # priming the tubing output
                    if self._pump0_infusions_counter == 0:
                        pump0_to_withdraw_vol_ul += self.pump0_output_tubing_prime_volume_ul

                    self._last_pump0_withdraw_volume_ul = min(
                        pump0_to_withdraw_vol_ul,
                        local.lib.dispensing.methods.get_syringe_volume_ul(
                            self._devices.PUMP, index=self.pump0_input
                        )
                    )

                else:

                    # set the _last_pump0_withdraw_volume_ul value to 0 as we're not withdrawing
                    self._last_pump0_withdraw_volume_ul = 0

                if not pump1_is_active:

                    pump1_withdraw_vol_ul = (
                            self.pump1_volume_to_dispense_ul - self._pump1_dispensed_ul_counter)

                    # if this will be our first infusion, we need to withdraw extra to allow for
                    # priming the tubing output
                    if self._pump1_infusions_counter == 0:
                        pump1_withdraw_vol_ul += self.pump1_output_tubing_prime_volume_ul

                    self._last_pump1_withdraw_volume_ul = min(
                        pump1_withdraw_vol_ul,
                        local.lib.dispensing.methods.get_syringe_volume_ul(self._devices.PUMP, index=self.pump1_input)
                    )

                else:

                    # set the _last_pump1_withdraw_volume_ul value to 0 as we're not withdrawing
                    self._last_pump1_withdraw_volume_ul = 0

                # now do the appropriate withdraws
                pump_indices = []
                withdraw_rates_ul_min = []
                withdraw_volumes_ul = []

                if not pump0_is_active:
                    pump_indices.append(self.pump0_input)
                    withdraw_rates_ul_min.append(self.pump0_withdraw_rate_ul_min)
                    withdraw_volumes_ul.append(self._last_pump0_withdraw_volume_ul)

                if not pump1_is_active:
                    pump_indices.append(self.pump1_input)
                    withdraw_rates_ul_min.append(self.pump1_withdraw_rate_ul_min)
                    withdraw_volumes_ul.append(self._last_pump1_withdraw_volume_ul)

                # send the command to set the plunger resolutions
                local.lib.dispensing.methods.withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=pump_indices,
                    withdraw_rates_ul_min=withdraw_rates_ul_min,
                    withdraw_volumes_ul=withdraw_volumes_ul,
                )

                log_string = f"Station {self.index}: wdrw {self._last_pump0_withdraw_volume_ul} pump0 at " \
                             f"{self.pump0_withdraw_rate_ul_min} " \
                             f"uL/min and {self._last_pump1_withdraw_volume_ul} uL pump1 " \
                             f"at {self.pump1_withdraw_rate_ul_min} uL/min"

                print(log_string)
                # if self.logging_enabled:
                #     self._aqueduct.log(log_string)

                self.record_pump0_input_position()
                self.record_pump1_input_position()

            self._phase_helper(do_if_not_started=to_do,
                               next_phase=Phase.PHASE_1_OUTPUT_PRIMING)

        elif self.phase_setpoint.value == Phase.PHASE_1_OUTPUT_PRIMING.value:
            # on the first dispense we need to prime,
            # otherwise straight to dispense at dispense_rate
            def to_do():
                """
                Quickly infuse pump0 and pump1 to the end of their respective output tubing.
                This is done to avoid dispensing slowly at the target dispense rate
                while no liquid has reached the end of the tubing.

                1) Set the pump0 input to the output_port and the pump1 input to the output_port

                2) Infuse `pump0_output_tubing_prime_rate_ul_min` at `pump0_output_tubing_prime_rate_ul_min` and
                   `pump1_output_tubing_prime_volume_ul` at `pump1_output_tubing_prime_rate_ul_min`

                :return:
                """
                local.lib.dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_output_port, self.pump1_output_port],
                    infuse_rates_ul_min=[
                        self.pump0_output_tubing_prime_rate_ul_min,
                        self.pump1_output_tubing_prime_rate_ul_min
                    ],
                    infuse_volumes_ul=[
                        self.pump0_output_tubing_prime_volume_ul,
                        self.pump1_output_tubing_prime_volume_ul
                    ]
                )

                log_string = f"Station {self.index}: priming output tubing with mon. B and pump1."

                print(log_string)
                # if self.logging_enabled:
                #     self._aqueduct.log(log_string)

            # record pump0 and pump1 input position
            self.record_pump0_input_position()
            self.record_pump1_input_position()

            # if this is the first time that we've dispensing pump0 or init B, we need to do the 
            # output tubing prime
            if self._pump0_infusions_counter == 0 or self._pump1_dispensed_ul_counter == 0:
                self._phase_helper(
                    do_if_not_started=to_do,
                    next_phase=Phase.PHASE_1_INFUSING)
            # otherwise, resume dispensing
            else:
                self._phase_helper(
                    do_if_not_started=None,
                    next_phase=Phase.PHASE_1_INFUSING)
                repeat = True

        elif self.phase_setpoint.value == Phase.PHASE_1_INFUSING.value:
            def to_do(
                    pump0_to_dispense_ul: float = None,
                    pump1_to_dispense_ul: float = None):
                """
                Now we begin dispensing pump0 and pump1 at their
                respective target rates into the reaction vessel.
                
                1) Set the pump0 input to the output_port (should already be there, but just to be safe...) and the
                   pump1 input to the output_port (should already be there, but just to be safe...)
                2) Set the plunger resolutions to N2 mode to enable slower infusion, if necessary
                3) Infuse `pump0_to_dispense_ul` at `pump0_dispense_rate_ul_min` and 
                    `pump1_to_dispense_ul` at `pump1_dispense_rate_ul_min`

                :return:
                """
                # we need to set the plunger resolution to N2 if the target rate is less than what's achievable
                # with N0 mode
                if self.pump0_dispense_rate_ul_min <= 8 * local.lib.dispensing.methods.get_min_rate_ul_min(
                        pump=self._devices.PUMP,
                        index=self.pump0_input
                ):
                    local.lib.dispensing.methods.set_plunger_mode(
                        pump=self._devices.PUMP,
                        index=self.pump0_input,
                        target_mode=2,
                    )

                if self.pump1_dispense_rate_ul_min <= 8 * local.lib.dispensing.methods.get_min_rate_ul_min(
                        pump=self._devices.PUMP,
                        index=self.pump1_input
                ):
                    local.lib.dispensing.methods.set_plunger_mode(
                        pump=self._devices.PUMP,
                        index=self.pump1_input,
                        target_mode=2,
                    )

                if pump0_to_dispense_ul is None:
                    if self._last_pump0_withdraw_volume_ul != 0:
                        self._pump0_dispense_volume_ul = self._last_pump0_withdraw_volume_ul
                    else:
                        self._pump0_dispense_volume_ul = local.lib.dispensing.methods.get_syringe_volume_ul(
                            pump=self._devices.PUMP, index=self.pump0_input)
                    if self._pump0_infusions_counter == 0:
                        self._pump0_dispense_volume_ul -= self.pump0_output_tubing_prime_volume_ul

                else:
                    self._pump0_dispense_volume_ul = pump0_to_dispense_ul

                if pump1_to_dispense_ul is None:
                    if self._last_pump1_withdraw_volume_ul != 0:
                        self._pump1_dispense_volume_ul = self._last_pump1_withdraw_volume_ul
                    else:
                        self._pump1_dispense_volume_ul = local.lib.dispensing.methods.get_syringe_volume_ul(
                            pump=self._devices.PUMP, index=self.pump1_input)
                    if self._pump1_infusions_counter == 0:
                        self._pump1_dispense_volume_ul -= self.pump1_output_tubing_prime_volume_ul

                else:
                    self._pump1_dispense_volume_ul = pump1_to_dispense_ul

                # now set the valves to the output ports and begin infusing
                local.lib.dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_output_port, self.pump1_output_port],
                    infuse_rates_ul_min=[self.pump0_dispense_rate_ul_min, self.pump1_dispense_rate_ul_min],
                    infuse_volumes_ul=[self._pump0_dispense_volume_ul, self._pump1_dispense_volume_ul]
                )

                if self._last_pump0_withdraw_volume_ul > 0:
                    self._pump0_dispensed_ul_counter += self._pump0_dispense_volume_ul
                    self._pump0_infusions_counter += 1

                if self._last_pump1_withdraw_volume_ul > 0:
                    self._pump1_dispensed_ul_counter += self._pump1_dispense_volume_ul
                    self._pump1_infusions_counter += 1

                log_string = (f"Station {self.index}: inf {self._pump0_dispensed_ul_counter} "
                              f"of {self.pump0_volume_to_dispense_ul} pump0 at "
                              f"{self.pump0_dispense_rate_ul_min} uL/min and "
                              f"{self._pump1_dispensed_ul_counter} of "
                              f"{self.pump1_volume_to_dispense_ul} uL pump1 at "
                              f"{self.pump1_dispense_rate_ul_min} uL/min")

                print(log_string)
                # if self.logging_enabled:
                #     self._aqueduct.log(log_string)

            # if this is the first time we've started this phase, begin infusing
            if self.current_phase_status == CurrentPhaseStatus.NOT_STARTED.value:

                # record pump0 and pump1 input position
                self.record_pump0_input_position()
                self.record_pump1_input_position()

                self._phase_helper(do_if_not_started=to_do,
                                   next_phase=Phase.PHASE_1_INFUSING)
            else:

                # record the pump0 volume dispensed
                delta_ul = self.record_pump0_input_position(calc_delta=True)
                self._realtime_pump0_dispensed_ul_counter += round(delta_ul, 2)
                self.pump0_dispensed_recordable.update(round(self._realtime_pump0_dispensed_ul_counter, 2))

                # record the pump1 volume dispensed
                delta_ul = self.record_pump1_input_position(calc_delta=True)
                self._realtime_pump1_dispensed_ul_counter += round(delta_ul, 2)
                self.pump1_dispensed_recordable.update(round(self._realtime_pump1_dispensed_ul_counter, 2))

                # check to see if the pump0 and pump1 are complete
                if self._pump0_dispensed_ul_counter >= self.pump0_volume_to_dispense_ul:
                    self._pump0_dispense_complete = True

                if self._pump1_dispensed_ul_counter >= self.pump1_volume_to_dispense_ul:
                    self._pump1_dispense_complete = True

                # we're done, proceed to purge
                if self._pump0_dispense_complete and self._pump1_dispense_complete:

                    self._phase_helper(do_if_not_started=None,
                                       next_phase=Phase.PHASE_1_OUTPUT_PURGE)
                # reload
                else:
                    self._phase_helper(
                        do_if_not_started=None,
                        next_phase=Phase.PHASE_1_FINAL_WITHDRAW
                    )

                    repeat = True

        elif self.phase_setpoint.value == Phase.PHASE_1_OUTPUT_PURGE.value:
            def to_do():
                """
                At this point, we've expelled the target volumes of pump0 and pump1
                into the reaction vessel, so we need to withdraw the residuals and expel them to waste.
                1) Set the plunger resolutions to N0 mode to enable higher velocities
                2) Do a withdraw of 2 * (output_tubing_volume_ul + waste_tubing_volume_ul) at max of 50 mL/min
                   for each input
                3) Set the valves to waste
                4) do a full infusion at max of 50 mL/min

                :return:
                """
                local.lib.dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    target_modes=[0, 0],
                )

                pump0_withdraw_rate_ul_min = min(
                    50000.,
                    local.lib.dispensing.methods.get_max_rate_ul_min(pump=self._devices.PUMP, index=self.pump0_input)
                )
                pump0_withdraw_volume_ul = 2 * (
                        self.pump0_output_tubing_volume_ul + self.pump0_output_tubing_volume_ul)

                pump1_withdraw_rate_ul_min = min(
                    50000.,
                    local.lib.dispensing.methods.get_max_rate_ul_min(pump=self._devices.PUMP, index=self.pump1_input)
                )
                pump1_withdraw_volume_ul = 2 * (
                        self.pump1_output_tubing_volume_ul + self.pump1_output_tubing_volume_ul)

                local.lib.dispensing.methods.set_valves_and_withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_input_port, self.pump1_input_port],
                    withdraw_rates_ul_min=[pump0_withdraw_rate_ul_min, pump1_withdraw_rate_ul_min],
                    withdraw_volumes_ul=[pump0_withdraw_volume_ul, pump1_withdraw_volume_ul]
                )

                # wait for completion
                while local.lib.dispensing.methods.is_active(
                        pump=self._devices.PUMP,
                        pump_indices=[self.pump0_input, self.pump1_input]
                ):
                    time.sleep(DELAY_S)

                local.lib.dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.pump0_input, self.pump1_input],
                    ports=[self.pump0_waste_port, self.pump1_waste_port],
                    infuse_rates_ul_min=[
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump0_input), 50000),
                        min(self._devices.PUMP.get_max_rate_ul_min(self.pump1_input), 50000)
                    ],
                    infuse_volumes_ul=[20000, 20000]  # larger than any syringe to ensure full infuse
                )

                # wait for completion
                while local.lib.dispensing.methods.is_active(
                        pump=self._devices.PUMP,
                        pump_indices=[self.pump0_input, self.pump1_input]
                ):
                    time.sleep(DELAY_S)

            self._phase_helper(do_if_not_started=to_do,
                               next_phase=Phase.PHASE_1_COMPLETE)

        elif self.phase_setpoint.value == Phase.PHASE_1_COMPLETE.value:
            if self._repeat is True:
                self.reset()
                self.phase_setpoint.update(Phase.PHASE_1_INITIALIZED.value)
            else:
                self.enabled_setpoint.update(Enabled.DISABLED.value)

        log_str += f"{self.phase_to_str(self.phase_setpoint.value)}" \
                   f"({self.phase_setpoint.value}[{self.current_phase_status}])"

        print(log_str)

        # if self.logging_enabled:
            # self._aqueduct.log(log_str)
            # self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

        if repeat is True:
            self.do_next_phase()
