import enum
import time
from typing import Callable
from typing import List
from typing import Tuple
from typing import Union

import dispensing.helpers
import dispensing.methods
from aqueduct.core.aq import Aqueduct
from aqueduct.core.recordable import Recordable
from aqueduct.core.setpoint import Setpoint
from aqueduct.devices.pump.syringe import ResolutionMode
from aqueduct.devices.pump.syringe import SyringePump
from dispensing.classes import Devices
from dispensing.processes.ProcessRunner import StationData


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

    # start of phase 1, Chemical 2 and chem1 co-dispense
    PHASE_1_INITIALIZED = 0

    # set Chemical 2 and chem1 valves to waste,
    # infuse both pumps completely at max rate
    PHASE_1_PRIMING_INIT_PURGE_TO_WASTE = 1

    # set Chemical 2 valve to input and chem1 valve to input
    # withdraw enough volume to fill input tubing + some volume in syringe,
    # infuse at priming_withdraw_rate_ml_min
    PHASE_1_PRIMING_WITHDRAW = 2

    # set Chemical 2 valve to waste and chem1 valve to waste
    # infuse pump completely at priming_infuse_rate_(pump)_ml_min
    PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE = 3

    # now we need to withdraw the volumes of Chemical 2 and
    # chem1 necessary to do the co-dispense,
    # which might include the output tubing volume
    PHASE_1_WITHDRAW = 4

    # now we set the Chemical 2 valve to output and
    # the chem1 valve to output and
    # begin infusing to quickly run the
    # liquid slugs to almost the end of the tubing
    PHASE_1_OUTPUT_PRIMING = 5

    # now we begin infusing at the specified
    # Chemical 2 addition rate and chem1 addition rate
    PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2 = 6

    # withdraw residual Chemical 2 and chem1
    # from the output lines and and send the liquids to waste
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


class CoDispenseStationPump:
    dispensed_recordable: Recordable = None
    name: str = ""
    input: int = 0

    input_port: int = 1
    output_port: int = 3
    waste_port: int = 4

    output_tubing_volume_ul: float = 350.0
    priming_volume_ul: float = 151.0 + 300.0 + 200

    volume_to_dispense_ul: List[float] = [1000, 36500]
    dispense_rate_ul_min: List[float] = [500, 50.0]
    dispense_time_min: List[Union[float, None]] = [None, None]

    wait_start: Union[None, float] = None

    dispense_param_index: int = 0

    output_tubing_prime_volume_ul: float = 315.0
    output_tubing_prime_rate_ul_min: float = 2000.0

    withdraw_rate_ul_min: float = 25000.0

    last_position_ul: float = None
    infusions_counter: int = 0
    dispense_volume_ul: float = 0
    start_dispense_ul: Union[None, float] = None
    end_dispense_ul: Union[None, float] = None

    has_primed_output: bool = False

    realtime_dispensed_ul_counter: float = 0.0
    last_withdraw_volume_ul: float = 0.0
    dispense_complete: bool = False

    def __str__(self):
        return f"{self.__dict__}"

    def record(self, plunger_positions: Tuple[float]) -> None:
        """
        Method used to generate the enable_setpoint and phase_setpoint.

        :return:
        """
        current_position_ul = plunger_positions[self.input]

        if self.last_position_ul is None:
            self.last_position_ul = current_position_ul
        else:
            delta_ul = self.last_position_ul - current_position_ul
            if delta_ul > 0:
                self.realtime_dispensed_ul_counter += round(delta_ul, 2)
                self.dispensed_recordable.update(
                    round(self.realtime_dispensed_ul_counter, 2)
                )
            self.last_position_ul = current_position_ul

    def check_lengths(self):
        if len(self.dispense_rate_ul_min) != len(self.volume_to_dispense_ul):
            raise ValueError(
                f"{self.name} dispense_rate_ul_min length must equal {self.name} volume_to_dispense_ul length"
            )

    def reset_phase_1(self) -> None:
        """
        Reset the dispense counters for Chemical 2 and Chemical 1.

        """
        self.realtime_dispensed_ul_counter: float = 0.0
        self.infusions_counter: int = 0

    def record_input_position(
        self, plunger_positions: Tuple[float], calc_delta: bool = False
    ):
        """
        Records the plunger position of the input for the syringe pump.

        Args:
            calc_delta (bool): Whether to calculate the change in plunger position. Default is False.

        Returns:
            float: The change in plunger position in microliters if calc_delta is True.

        """
        delta_ul = None

        if calc_delta:
            if isinstance(self.last_position_ul, float):
                delta_ul = self.last_position_ul - plunger_positions[self.input]
            else:
                delta_ul = 0.0

        self.last_position_ul = plunger_positions[self.input]

        if calc_delta:
            return delta_ul

    def wait_expired(self, now: float) -> bool:
        """
        Checks if the waiting period for has expired.

        Args:
            now (float): The current timestamp.

        Returns:
            bool: True if the waiting period has expired, False otherwise.

        """
        has_expired = (
            self.wait_start is not None
            and now > self.wait_start + self.get_dispense_time_minutes() * 60
        )

        return has_expired

    def reset_wait(self):
        """
        Resets the Chem1 wait start time.

        Args:
            None

        Returns:
            None

        """
        self.wait_start = None

    def total_to_dispense_ul(self) -> float:
        """
        Calculate the total volume (in uL) of to dispense.

        """
        return sum(self.volume_to_dispense_ul)

    def total_left_to_dispense_ul(self) -> float:
        """
        Calculate the total volume (in uL) remaining to dispense.

        """
        return sum(self.volume_to_dispense_ul[self.dispense_param_index : :])

    def phase_complete(self, now: float) -> bool:
        """
        Checks if the phase is complete.

        Args:
            now (float): The current timestamp.

        Returns:
            bool: True if the phase is complete, False otherwise.

        """
        if self.wait_start is not None:
            return self.wait_expired(now)

        else:
            target = sum(self.volume_to_dispense_ul[0 : self.dispense_param_index + 1])

            done = self.realtime_dispensed_ul_counter
            return (
                done > target
                and self.dispense_param_index != len(self.volume_to_dispense_ul) - 1
            )

    def get_dispense_time_minutes(self) -> float:
        """
        Get the current target dispense time in minutes.

        """
        return self.dispense_time_min[self.dispense_param_index]

    def get_dispense_rate_ul_min(self) -> float:
        """
        Get the current target dispense rate (in uL/min).

        """
        return self.dispense_rate_ul_min[self.dispense_param_index]

    def is_idle(self) -> bool:
        """
        Return whether the station is idle.
        """
        return self.dispense_complete or self.wait_start is not None

    def start_withdraw(self, plunger_positions_ul: Tuple[float]) -> float:
        """
        Start the withdrawal process by setting the end dispense volume and updating the dispensed volume counter.

        :param plunger_positions_ul: Tuple of plunger positions in microliters.
        :type plunger_positions_ul: Tuple[float]
        :return: The end dispense volume in microliters.
        :rtype: float
        """
        self.end_dispense_ul = plunger_positions_ul[self.input]

        if self.realtime_dispensed_ul_counter >= self.total_to_dispense_ul() - 1:
            self.dispense_complete = True

    def calc_volume_to_withdraw(self, syringe_volume_ul: float):
        """
        Calculate the volume to be withdrawn based on the remaining dispense volume and syringe size.

        :param syringe_volume_ul: The volume of the syringe in microliters.
        :type syringe_volume_ul: float
        """
        # we need to withdraw equal dispense-rate weighted volumes, taking into account the
        # syringe size that will be limiting the max time that we can infuse
        to_withdraw_vol_ul = (
            self.total_to_dispense_ul() - self.realtime_dispensed_ul_counter
        )

        # if this will be our first infusion, we need to withdraw extra to allow for
        # priming the tubing output
        if self.infusions_counter == 0:
            to_withdraw_vol_ul += self.output_tubing_prime_volume_ul

        # save the amount withdrawn to our class member
        self.last_withdraw_volume_ul = min(
            to_withdraw_vol_ul,
            syringe_volume_ul,
        )

    def calc_volume_to_dispense(self, to_dispense: Union[float, None]):
        """
        Calculate the volume to be dispensed based on the given value or remaining dispense volume.

        :param to_dispense: The volume to be dispensed in microliters, or None to calculate based on remaining dispense volume.
        :type to_dispense: Union[float, None]
        """
        if to_dispense is None:
            self.dispense_volume_ul = max(
                0,
                min(
                    self.start_dispense_ul,
                    self.total_to_dispense_ul() - self.realtime_dispensed_ul_counter,
                ),
            )

        else:
            self.dispense_volume_ul = to_dispense

    def check_complete(self):
        if self.total_left_to_dispense_ul() < 0.1:
            self.dispense_complete = True

    def advance_rate(self, station_index: int, pump: SyringePump) -> str:
        """
        Advance the dispense rate to the next step and perform the necessary actions.

        :param station_index: The index of the station.
        :type station_index: int
        :param pump: The syringe pump object.
        :type pump: SyringePump
        :return: A log string indicating the advancement.
        :rtype: str
        """
        dispensing.methods.stop_pumps(
            pump=pump,
            pump_indices=[self.input],
        )

        time.sleep(1)

        self.dispense_param_index += 1

        if self.total_left_to_dispense_ul() < 0.1:
            self.dispense_complete = True
            self.reset_wait()

        self.dispense_param_index = min(
            self.dispense_param_index,
            len(self.dispense_rate_ul_min) - 1,
        )

        if not self.dispense_complete:

            # check if we have a zero rate step
            if self.get_dispense_rate_ul_min() == 0.0:
                self.wait_start = time.monotonic()

                log_string = f"Station {station_index}: Advancing {self.name} to wait step for: {self.get_dispense_time_minutes()} minutes. "

            else:
                self.set_target_mode(pump=pump)
                self.last_position_ul = None

                # now begin infusing
                dispensing.methods.infuse(
                    pump=pump,
                    pump_indices=[self.input],
                    infuse_rates_ul_min=[
                        self.get_dispense_rate_ul_min(),
                    ],
                    infuse_volumes_ul=[
                        self.dispense_volume_ul,
                    ],
                )

                log_string = f"Station {station_index}: Advancing {self.name} to next target rate: {self.get_dispense_rate_ul_min()} uL/min for {self.get_dispense_time_minutes()} minutes. "

        else:

            log_string = f"Station {station_index}: {self.name} dispense complete. "

        return log_string

    def after_infuse_started(self):
        """
        Perform necessary actions after the infusion is started, such as updating the infusions counter.

        If it is the first infusion, it checks if there is a zero rate step and sets the wait start time if applicable.

        If the dispense volume is greater than zero, it increments the infusions counter.
        """
        if self.infusions_counter == 0:
            # check if we have a zero rate step
            if (
                self.get_dispense_rate_ul_min() == 0.0
                and self.get_dispense_time_minutes() > 0
            ):
                self.wait_start = time.monotonic()

        if self.dispense_volume_ul > 0 and self.get_dispense_rate_ul_min() > 0:
            self.infusions_counter += 1

        self.last_position_ul = None

    def after_infuse_complete(self, plunger_positions: Tuple[float]):
        """
        Perform necessary actions after the infusion is completed, including updating the dispensed volume counter.

        :param plunger_positions: Tuple of plunger positions in microliters.
        :type plunger_positions: Tuple[float]
        """
        delta_ul = self.record_input_position(plunger_positions, calc_delta=True)

        self.realtime_dispensed_ul_counter += round(delta_ul, 2)

        self.dispensed_recordable.update(round(self.realtime_dispensed_ul_counter, 2))

        if self.realtime_dispensed_ul_counter >= self.total_to_dispense_ul() - 1:
            self.dispense_complete = True

    def set_target_mode(self, pump: SyringePump):
        # we need to set the plunger resolution to N2 if the target rate is less than what's achievable
        # with N0 mode
        if (
            0
            <= self.get_dispense_rate_ul_min()
            <= 8 * dispensing.methods.get_min_rate_ul_min(pump=pump, index=self.input)
        ):
            dispensing.methods.set_plunger_mode(
                pump=pump,
                index=self.input,
                mode=ResolutionMode.N2,
            )

    def assign_params_from_csv(
        self,
        slots: List[dispensing.helpers.TimeAndRate],
        pump_index: int,
        chemical_name: str,
    ):
        """
        Assigns parameters from a CSV file to the object.

        :param station_slots: List of StationData objects.
        :type station_slots: List[StationData]
        """

        def calculate_volume_to_dispense(
            slots: List[dispensing.helpers.TimeAndRate],
        ) -> List[float]:
            volume_to_dispense_ul = []
            ml_sum = 0

            for slot in slots:
                ml_sum += round(slot.minutes * slot.ul_min, 3) / 1000.0
                volume_to_dispense_ul.append(round(slot.minutes * slot.ul_min, 3))

            return volume_to_dispense_ul

        def calculate_dispense_rate(
            slots: List[dispensing.helpers.TimeAndRate],
        ) -> List[float]:
            dispense_rate_ul_min = []

            for slot in slots:
                dispense_rate_ul_min.append(slot.ul_min)

            return dispense_rate_ul_min

        def calculate_dispense_time(
            slots: List[dispensing.helpers.TimeAndRate],
        ) -> List[float]:
            dispense_time_min = []

            for slot in slots:
                dispense_time_min.append(slot.minutes)

            return dispense_time_min

        self.input = pump_index
        self.name = chemical_name

        self.volume_to_dispense_ul = calculate_volume_to_dispense(slots)

        self.dispense_rate_ul_min = calculate_dispense_rate(slots)

        self.dispense_time_min = calculate_dispense_time(slots)

    def calculate_dispense_volumes(self):
        """
        Calculate the volumes to dispense for each dispense step.
        """
        self.volume_to_dispense_ul = []
        for (ul_min, minutes) in zip(self.dispense_rate_ul_min, self.dispense_time_min):
            self.volume_to_dispense_ul.append(round(minutes * ul_min, 3))



class CoDispenseStation:
    """
    Class to contain all relevant parameters for executing a 1 Phase Chemical 1 + Chemical 2 reaction.

    Phase 1: (12hrs) dispensing 36.5 mL Chemical 2 at 50 uL/min + 11.6 mL Chemical 1 at 15 uL/min for 12 hours
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
    # process for Chemical 1 and Chemical 2, to enable toggling of station's
    # current phase we use an Aqueduct Setpoint
    phase_setpoint: Setpoint = None

    # track the status of the current phase using one of the CurrentPhaseStatus
    # enum's members
    current_phase_status: int = CurrentPhaseStatus.NOT_STARTED.value

    skip_withdraw: bool = False

    # logging
    logging_enabled: bool = True
    log_file_name: str = "codispense_"

    chem1: CoDispenseStationPump
    chem2: CoDispenseStationPump

    _repeat: bool = False

    # reference to the Global aqueduct instance
    _devices: Devices = None
    _aqueduct: Aqueduct = None

    def __init__(
        self, index: int = 0, devices_obj: Devices = None, aqueduct: Aqueduct = None
    ):

        self.index = index

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

        self.chem1 = CoDispenseStationPump()
        self.chem2 = CoDispenseStationPump()

        self.chem1.check_lengths()
        self.chem2.check_lengths()

    def __str__(self):
        return (
            f"Station {self.index} (chem 1: {self.chem1.input}, chem 2: {self.chem2.input}): "
            f"enabled={self.enabled_setpoint.value}, phase={self.phase_setpoint.value}"
        )

    def make_setpoints(self) -> None:
        """
        Method used to generate the:
            - enable_setpoint
            - phase_setpoint
            - chem2.dispensed_recordable
            - chem1.dispensed_recordable

        :return:
        """

        self.enabled_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_enabled",
            value=Enabled.ENABLED.value,
            dtype=int.__name__,
        )

        self.phase_setpoint = self._aqueduct.setpoint(
            name=f"station_{self.index}_phase",
            value=Phase.PHASE_1_INITIALIZED.value,
            dtype=int.__name__,
        )

        self.chem2.dispensed_recordable = self._aqueduct.recordable(
            name=f"station_{self.index}_chem2_disp.",
            value=0.0,
            dtype=float.__name__,
        )

        self.chem2.dispensed_recordable.clear()

        self.chem1.dispensed_recordable = self._aqueduct.recordable(
            name=f"station_{self.index}_chem1_disp.", value=0.0, dtype=float.__name__
        )

        self.chem1.dispensed_recordable.clear()

    def record(self, plunger_positions: Tuple[float]) -> None:
        """
        Method used to generate the enable_setpoint and phase_setpoint.

        :return:
        """
        if (
            self.phase_setpoint.value
            == Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2.value
        ):
            if plunger_positions:
                self.chem1.record(plunger_positions)
                self.chem2.record(plunger_positions)

    def assign_params_from_csv(self, station_slots: List[StationData]):
        """
        Assigns parameters from a CSV file to the object.

        :param station_slots: List of StationData objects.
        :type station_slots: List[StationData]
        """
        self.chem1.assign_params_from_csv(
            station_slots[self.index].chem1.slots,
            station_slots[self.index].chem1.data_row.pump_index,
            station_slots[self.index].chem1.data_row.chemical_name,
        )

        self.chem2.assign_params_from_csv(
            station_slots[self.index].chem2.slots,
            station_slots[self.index].chem2.data_row.pump_index,
            station_slots[self.index].chem2.data_row.chemical_name,
        )

        total_chem1_volume_ml = float(
            station_slots[self.index].chem1.data_row.total_volume_ml
        )
        total_chem2_volume_ml = float(
            station_slots[self.index].chem2.data_row.total_volume_ml
        )

        def log_volume_difference(volume_ml: float, ml_sum: float, name: str):
            volume_difference = abs((ml_sum - volume_ml) / ml_sum)
            if volume_difference > 0.2:
                log_string = f"Station {self.index}: Warning: volume difference ({name}), entered: {volume_ml} mL, sum: {ml_sum} mL"
                print(log_string)

        log_volume_difference(
            total_chem1_volume_ml, total_chem1_volume_ml, self.chem1.name
        )
        log_volume_difference(
            total_chem2_volume_ml, total_chem2_volume_ml, self.chem2.name
        )

    def inputs(self) -> tuple:
        """
        Return the pump indices used.

        """
        return (self.chem1.input, self.chem2.input)

    def disable(self) -> tuple:
        """
        Dsiable the station. For use after an error

        """
        self.enabled_setpoint.update(Enabled.DISABLED.value)

    def is_active(self, active_inputs: Tuple[bool]) -> bool:
        """
        Method to determine whether the station is active or needs to be moved on to the
        next phase in the process.

        :param active_inputs:
        :return:
        """
        chem2_is_active = active_inputs[self.chem2.input]
        chem1_is_active = active_inputs[self.chem1.input]

        now = time.monotonic()

        if (
            self.phase_setpoint.value
            == Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2.value
        ):
            self.chem1.check_complete()
            self.chem2.check_complete()

            if not self.chem2.dispense_complete and self.chem2.phase_complete(now):
                self.chem2.reset_wait()
                self.advance_rate(self.chem2)

            chem2_active = chem2_is_active or self.chem2.is_idle()

            if not self.chem1.dispense_complete and self.chem1.phase_complete(now):
                self.chem1.reset_wait()
                self.advance_rate(self.chem1)

            chem1_active = chem1_is_active or self.chem1.is_idle()

            # we should skip the withdraw if both pumps are:
            #   - idle
            if self.chem1.is_idle() and self.chem2.is_idle():
                self.skip_withdraw = True

            # we should skip the withdraw if one pump is active and the other is idle:
            if (self.chem1.is_idle() and chem2_is_active) or (
                self.chem2.is_idle() and chem1_is_active
            ):
                self.skip_withdraw = True

            is_active = chem2_active and chem1_active

            # if both pumps are complete, where not active
            if self.chem1.dispense_complete and self.chem2.dispense_complete:
                is_active = False

        # otherwise, only one pump must be active
        else:
            is_active = chem2_is_active or chem1_is_active

        return is_active

    def is_enabled(self) -> bool:
        """
        Method to determine whether the station is enabled.

        :return:
        """
        return self.enabled_setpoint.value == Enabled.ENABLED.value

    def complete(self) -> bool:
        """
        Method to determine whether the station has completed the process.

        :return:
        """
        return self.phase_setpoint.value == Phase.PHASE_1_COMPLETE.value

    def reset(self) -> None:
        """
        Reset both Phase 1 and Phase 2 counters.

        """
        self.chem1.reset_phase_1()
        self.chem2.reset_phase_1()

    def infused_log_string(self) -> str:
        """
        Log string to track volumen infused.

        """
        return (
            f"Infused {self.chem2.realtime_dispensed_ul_counter:.2f} "
            f"of {self.chem2.total_to_dispense_ul():.2f} uL {self.chem2.name} and "
            f"{self.chem1.realtime_dispensed_ul_counter:.2f} of "
            f"{self.chem1.total_to_dispense_ul():.2f} uL {self.chem1.name}."
        )

    def advance_rate(self, chem: CoDispenseStationPump):
        """
        Advance the dispense rate to the next target
        1) Stop the pump
        2) Increment the target param index
        :return:
        """
        plunger_positions = self._devices.PUMP.get_plunger_position_volume()
        chem.record_input_position(plunger_positions)

        log_string = (
            chem.advance_rate(self.index, self._devices.PUMP)
            + self.infused_log_string()
        )

        print(log_string)
        if self.logging_enabled:
            self._aqueduct.log(log_string)

    def log_params(self) -> bool:
        """
        Method to determine whether the station is enabled.

        :return:
        """
        self._aqueduct.log(
            f"Station {self.index}: chem1: {self.chem1}, chem2: {self.chem2}"
        )

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
        elif phase == Phase.PHASE_1_WITHDRAW.value:
            return "wdrw"
        elif phase == Phase.PHASE_1_OUTPUT_PRIMING.value:
            return "output priming"
        elif phase == Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2.value:
            return "infuse"
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
        do_if_not_started_kwargs: dict = None,
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
        log_str: str = (
            f"Station {self.index}: {self.phase_to_str(self.phase_setpoint.value)}"
            f"({self.phase_setpoint.value}[{self.current_phase_status}]) -> "
        )

        if self.phase_setpoint.value == Phase.PHASE_1_INITIALIZED.value:
            self._phase_helper(
                do_if_not_started=None,
                next_phase=Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE,
            )

            # no action here, we just move on to the next phase
            repeat = True

        elif (
            self.phase_setpoint.value == Phase.PHASE_1_PRIMING_INIT_PURGE_TO_WASTE.value
        ):

            def to_do():
                """
                Purge both the Chemical 2 and Chemical 1 inputs.
                1) Set the plunger resolution of both pumps to N0 to allow for max velocity.
                2) Set the Chemical 2 and Chemical 1 inputs to waste_port
                3) Perform a full infuse at a maximum of 50 mL/min for each pump.
                :return:
                """
                dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    modes=[ResolutionMode.N0, ResolutionMode.N0],
                )

                time.sleep(1)

                dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.waste_port, self.chem1.waste_port],
                    infuse_rates_ul_min=[
                        min(
                            dispensing.methods.get_max_rate_ul_min(
                                self._devices.PUMP, self.chem2.input
                            ),
                            50000,
                        ),
                        min(
                            dispensing.methods.get_max_rate_ul_min(
                                self._devices.PUMP, self.chem1.input
                            ),
                            50000,
                        ),
                    ],
                    # larger than any syringe to ensure full infuse
                    infuse_volumes_ul=[20000, 20000],
                )

                log_string = f"Station {self.index}: Purging {self.chem1.name} and {self.chem2.name} pumps to waste"

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do, next_phase=Phase.PHASE_1_PRIMING_WITHDRAW
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_PRIMING_WITHDRAW.value:

            def to_do():
                """
                Prime the Chemical 2 pump_input with Chemical 2 and the chem1_input with Chemical 1.
                1) Set the Chemical 2 input to the chem2_input_port and the chem1 input to chem1_input_port
                2) Perform a finite withdraw of the Chemical 2 input at `chem2.withdraw_rate_ul_min` for
                   `chem2.priming_volume_ul` uL and a finite withdraw of the chem1 input
                   at `chem1.withdraw_rate_ul_min` for `chem1.priming_volume_ul`

                :return:
                """
                dispensing.methods.set_valves_and_withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.input_port, self.chem1.input_port],
                    withdraw_rates_ul_min=[
                        self.chem2.withdraw_rate_ul_min,
                        self.chem1.withdraw_rate_ul_min,
                    ],
                    withdraw_volumes_ul=[
                        self.chem2.priming_volume_ul,
                        self.chem1.priming_volume_ul,
                    ],
                )

                log_string = (
                    f"Station {self.index}: Priming wdrw {self.chem2.priming_volume_ul} uL {self.chem2.name} at "
                    f"{self.chem2.withdraw_rate_ul_min} "
                    f"uL/min and {self.chem1.priming_volume_ul} uL {self.chem1.name} "
                    f"at {self.chem1.withdraw_rate_ul_min} uL/min"
                )

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do,
                next_phase=Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE,
            )

        elif (
            self.phase_setpoint.value
            == Phase.PHASE_1_PRIMING_FINAL_PURGE_TO_WASTE.value
        ):

            def to_do():
                """
                After priming Chemical 2 and Chemical 1, purge any excess to waste.
                1) Set the Chemical 2 input to the waste_port and the chem1 input to the waste port
                2) Perform a full infusion of both pump inputs at each pump input's maximum rate.

                :return:
                """
                dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.waste_port, self.chem1.waste_port],
                    infuse_rates_ul_min=[
                        min(
                            dispensing.methods.get_max_rate_ul_min(
                                self._devices.PUMP, self.chem2.input
                            ),
                            20000,
                        ),
                        min(
                            dispensing.methods.get_max_rate_ul_min(
                                self._devices.PUMP, self.chem1.input
                            ),
                            20000,
                        ),
                    ],
                    infuse_volumes_ul=[20000, 20000],
                )

                log_string = f"Station {self.index}: Phase 1 final purge to waste"

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

            self._phase_helper(
                do_if_not_started=to_do, next_phase=Phase.PHASE_1_WITHDRAW
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_WITHDRAW.value:

            def to_do():
                """
                Withdraw either enough Chemical 2 and Chemical 1 to do the
                full dispense or as much as the syringes will allow.

                1) Check to see whether the chem2_input and/or the chem1_input are active (plunger moving). If an
                    input is not active, then we need to reload the syringe by doing a withdrawal. Stop both
                    inputs to ensure we're not dispensing one of the outputs while the other is being reloaded.

                2) If the Chemical 2 input is not active, set the Chemical 2 input to chem2_input_port. If the
                    chem1 input is not active, set the chem1 input to the chem1_input_port.

                2) For the inactive inputs, set the plunger resolutions to N0 mode to enable faster withdraw
                    (we could be re-entering this method after doing a dispense at a low flow rate,
                    so the resolution may be N2)

                3) Calculate the Chemical 2 pump run time in seconds based on the:
                     the minimum of:
                        -> `chem2_volume_to_dispense_ul` - `chem2._dispensed_ul_counter` (the difference
                            between target volume and the volume dispensed so far)
                        -> the Chemical 2 syringe volume

                        at `chem2_dispense_rate_ul_min`

                4) Calculate the chem1 pump run time in seconds based on the:
                    the minimum of:
                        -> `chem1_volume_to_dispense_ul` - `chem1._dispensed_ul_counter` (the difference
                            between the target volume and the volume dispensed so far)
                        -> the chem1 syringe volume

                5) Take the minimum of the Chemical 2 and chem1 pump run times as the actual run time.

                6) Calculate the volumes of Chemical 2 and Chemical 1 needed to run at the
                    target dispense rates for these times.

                7) If the Chemical 2 input is not active, withdraw `chem2_withdraw_volume_ul` at
                    `chem2_dispense_rate_ul_min`. If the chem1 input is not active, `init_b_withdraw_volume_ul`
                    Chemical 1 at `chem1_dispense_rate_ul_min`

                :return:
                """
                # stop both pumps
                dispensing.methods.stop_pumps(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                )

                # get the end-of-infusion plunger positions before withdrawing
                plunger_positions = self._devices.PUMP.get_plunger_position_volume()

                self.chem1.start_withdraw(plunger_positions)
                self.chem2.start_withdraw(plunger_positions)

                log_string = f"Station {self.index}: {self.infused_log_string()}"

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

                pump_indices = []
                ports = []
                target_modes = []
                withdraw_rates_ul_min = []
                withdraw_volumes_ul = []

                if not self.chem2.dispense_complete:

                    self.chem2.calc_volume_to_withdraw(
                        syringe_volume_ul=dispensing.methods.get_syringe_volume_ul(
                            self._devices.PUMP, index=self.chem2.input
                        )
                    )

                    pump_indices.append(self.chem2.input)
                    ports.append(self.chem2.input_port)
                    target_modes.append(ResolutionMode.N0)
                    withdraw_rates_ul_min.append(self.chem2.withdraw_rate_ul_min)
                    withdraw_volumes_ul.append(self.chem2.last_withdraw_volume_ul)

                else:
                    self.chem2.last_withdraw_volume_ul = 0.0

                if not self.chem1.dispense_complete:

                    self.chem1.calc_volume_to_withdraw(
                        syringe_volume_ul=dispensing.methods.get_syringe_volume_ul(
                            self._devices.PUMP, index=self.chem1.input
                        )
                    )

                    pump_indices.append(self.chem1.input)
                    ports.append(self.chem1.input_port)
                    target_modes.append(ResolutionMode.N0)
                    withdraw_rates_ul_min.append(self.chem1.withdraw_rate_ul_min)
                    withdraw_volumes_ul.append(self.chem1.last_withdraw_volume_ul)

                else:
                    self.chem1.last_withdraw_volume_ul = 0.0

                # send the command to set the valves
                dispensing.methods.set_valves(
                    pump=self._devices.PUMP, pump_indices=pump_indices, ports=ports
                )

                # send the command to set the plunger resolutions
                dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=pump_indices,
                    modes=target_modes,
                )

                # send the command to do the withdraw
                dispensing.methods.withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=pump_indices,
                    withdraw_rates_ul_min=withdraw_rates_ul_min,
                    withdraw_volumes_ul=withdraw_volumes_ul,
                )

                log_string = (
                    f"Station {self.index}: wdrw {self.chem2.last_withdraw_volume_ul:.2f} uL {self.chem2.name} at "
                    f"{self.chem2.withdraw_rate_ul_min} "
                    f"uL/min and {self.chem1.last_withdraw_volume_ul:.2f} uL {self.chem1.name} "
                    f"at {self.chem1.withdraw_rate_ul_min} uL/min"
                )

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

                self.chem1.record_input_position(plunger_positions)
                self.chem2.record_input_position(plunger_positions)

            if not self.skip_withdraw:

                self._phase_helper(
                    do_if_not_started=to_do, next_phase=Phase.PHASE_1_OUTPUT_PRIMING
                )

            else:

                repeat = True

                if self.current_phase_status == CurrentPhaseStatus.NOT_STARTED.value:
                    self._phase_helper()

                else:
                    self.skip_withdraw = False
                    self._phase_helper(
                        do_if_not_started=None,
                        next_phase=Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2,
                    )

        elif self.phase_setpoint.value == Phase.PHASE_1_OUTPUT_PRIMING.value:
            # on the first dispense we need to prime,
            # otherwise straight to dispense at dispense_rate
            def prime():
                """
                Quickly infuse Chemical 2 and Chemical 1 to the end of their respective output tubing.
                This is done to avoid dispensing slowly at the target dispense rate
                while no liquid has reached the end of the tubing.

                1) Set the Chemical 2 input to the output_port and the chem1 input to the output_port

                2) Infuse `chem2.output_tubing_prime_rate_ul_min` at `chem2.output_tubing_prime_rate_ul_min` and
                   `chem1.output_tubing_prime_volume_ul` at `chem1.output_tubing_prime_rate_ul_min`

                :return:
                """
                dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.output_port, self.chem1.output_port],
                    infuse_rates_ul_min=[
                        self.chem2.output_tubing_prime_rate_ul_min,
                        self.chem1.output_tubing_prime_rate_ul_min,
                    ],
                    infuse_volumes_ul=[
                        self.chem2.output_tubing_prime_volume_ul,
                        self.chem1.output_tubing_prime_volume_ul,
                    ],
                )

                log_string = f"Station {self.index}: priming output tubing with {self.chem1.name}."

                self.chem2.has_primed_output = True
                self.chem1.has_primed_output = True

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

            # get the end-of-infusion plunger positions before withdrawing
            plunger_positions = self._devices.PUMP.get_plunger_position_volume()

            # record Chemical 1 and Chemical 2 input position
            self.chem1.record_input_position(plunger_positions)
            self.chem2.record_input_position(plunger_positions)

            # if this is the first time that we've dispensing Chemical 1 or Chemical 2, we need to do the
            # output tubing prime
            if not self.chem2.has_primed_output and not self.chem1.has_primed_output:
                self._phase_helper(
                    do_if_not_started=prime,
                    next_phase=Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2,
                )

            # otherwise, resume dispensing
            else:
                self._phase_helper(
                    do_if_not_started=None,
                    next_phase=Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2,
                )
                repeat = True

        elif (
            self.phase_setpoint.value
            == Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2.value
        ):

            def to_do(
                chem2_to_dispense_ul: float = None,
                chem1_to_dispense_ul: float = None,
            ):
                """
                Now we begin dispensing Chemical 2 and Chemical 1 at their
                respective target rates into the reaction vessel.

                1) Set the Chemical 2 input to the output_port (should already be there, but just to be safe...) and the
                   chem1 input to the output_port (should already be there, but just to be safe...)
                2) Set the plunger resolutions to N2 mode to enable slower infusion, if necessary
                3) Infuse `chem2_to_dispense_ul` at `chem2_dispense_rate_ul_min` and
                    `chem1_to_dispense_ul` at `chem1_dispense_rate_ul_min`

                :return:
                """
                if (
                    self.chem2.get_dispense_rate_ul_min() > 0.0
                    or self.chem1.get_dispense_rate_ul_min() > 0.0
                ):

                    # we need to set the plunger resolution to N2 if the target rate is less than what's achievable
                    # with N0 mode
                    self.chem2.set_target_mode(pump=self._devices.PUMP)
                    self.chem1.set_target_mode(pump=self._devices.PUMP)

                    # record the starting positions
                    plunger_positions = self._devices.PUMP.get_plunger_position_volume()

                    self.chem2.start_dispense_ul = plunger_positions[self.chem2.input]
                    self.chem1.start_dispense_ul = plunger_positions[self.chem1.input]

                    self.chem2.calc_volume_to_dispense(chem2_to_dispense_ul)
                    self.chem1.calc_volume_to_dispense(chem1_to_dispense_ul)

                    pump_indices = []
                    output_ports = []
                    infuse_rates_ul_min = []
                    infuse_volumes_ul = []

                    if self.chem2.get_dispense_rate_ul_min() > 0.0:
                        pump_indices.append(self.chem2.input)
                        output_ports.append(self.chem2.output_port)
                        infuse_rates_ul_min.append(
                            self.chem2.get_dispense_rate_ul_min()
                        )
                        infuse_volumes_ul.append(self.chem2.dispense_volume_ul)

                    if self.chem1.get_dispense_rate_ul_min() > 0.0:
                        pump_indices.append(self.chem1.input)
                        output_ports.append(self.chem1.output_port)
                        infuse_rates_ul_min.append(
                            self.chem1.get_dispense_rate_ul_min()
                        )
                        infuse_volumes_ul.append(self.chem1.dispense_volume_ul)

                    # now set the valves to the output ports and begin infusing
                    dispensing.methods.set_valves_and_infuse(
                        pump=self._devices.PUMP,
                        pump_indices=pump_indices,
                        ports=output_ports,
                        infuse_rates_ul_min=infuse_rates_ul_min,
                        infuse_volumes_ul=infuse_volumes_ul,
                    )

                self.chem1.after_infuse_started()
                self.chem2.after_infuse_started()

                log_string = (
                    f"Station {self.index}: infusing {self.chem2.dispense_volume_ul:.2f} uL {self.chem2.name} at "
                    f"{self.chem2.get_dispense_rate_ul_min()} uL/min and {self.chem1.dispense_volume_ul:.2f} uL "
                    f"{self.chem1.name} at {self.chem1.get_dispense_rate_ul_min()} uL/min"
                )

                print(log_string)
                if self.logging_enabled:
                    self._aqueduct.log(log_string)

            plunger_positions = self._devices.PUMP.get_plunger_position_volume()

            # if this is the first time we've started this phase, begin infusing
            if self.current_phase_status == CurrentPhaseStatus.NOT_STARTED.value:

                # record chem2 and chem1 input position
                self.chem1.record_input_position(plunger_positions)
                self.chem2.record_input_position(plunger_positions)

                self._phase_helper(
                    do_if_not_started=to_do,
                    next_phase=Phase.PHASE_1_INFUSING_CHEMICAL_1_AND_CHEMICAL_2,
                )

            else:

                self.chem1.after_infuse_complete(plunger_positions)
                self.chem2.after_infuse_complete(plunger_positions)

                # we're done, proceed to purge
                if self.chem2.dispense_complete and self.chem1.dispense_complete:

                    self._phase_helper(
                        do_if_not_started=None, next_phase=Phase.PHASE_1_OUTPUT_PURGE
                    )

                # reload
                else:
                    if self.skip_withdraw:
                        log_str = None

                    self._phase_helper(
                        do_if_not_started=None, next_phase=Phase.PHASE_1_WITHDRAW
                    )
                    repeat = True

        elif self.phase_setpoint.value == Phase.PHASE_1_OUTPUT_PURGE.value:

            def to_do():
                """
                At this point, we've expelled the target volumes of Chemical 2 and Chemical 1
                into the reaction vessel, so we need to withdraw the residuals and expel them to waste.
                1) Set the plunger resolutions to N0 mode to enable higher velocities
                2) Do a withdraw of 2 * (output_tubing_volume_ul + waste_tubing_volume_ul) at max of 50 mL/min
                   for each input
                3) Set the valves to waste
                4) do a full infusion at max of 50 mL/min

                :return:
                """
                dispensing.methods.set_plunger_modes(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    modes=[ResolutionMode.N0, ResolutionMode.N0],
                )

                self.chem2.withdraw_rate_ul_min = min(
                    50000.0,
                    dispensing.methods.get_max_rate_ul_min(
                        pump=self._devices.PUMP, index=self.chem2.input
                    ),
                )

                chem2_withdraw_volume_ul = 2 * (
                    self.chem2.output_tubing_volume_ul
                    + self.chem2.output_tubing_volume_ul
                )

                self.chem1.withdraw_rate_ul_min = min(
                    50000.0,
                    dispensing.methods.get_max_rate_ul_min(
                        pump=self._devices.PUMP, index=self.chem1.input
                    ),
                )

                chem1_withdraw_volume_ul = 2 * (
                    self.chem1.output_tubing_volume_ul
                    + self.chem1.output_tubing_volume_ul
                )

                dispensing.methods.set_valves_and_withdraw(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.input_port, self.chem1.input_port],
                    withdraw_rates_ul_min=[
                        self.chem2.withdraw_rate_ul_min,
                        self.chem1.withdraw_rate_ul_min,
                    ],
                    withdraw_volumes_ul=[
                        chem2_withdraw_volume_ul,
                        chem1_withdraw_volume_ul,
                    ],
                )

                # wait for completion
                while dispensing.methods.is_active(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                ):
                    time.sleep(1)

                dispensing.methods.set_valves_and_infuse(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                    ports=[self.chem2.waste_port, self.chem1.waste_port],
                    infuse_rates_ul_min=[
                        min(
                            50000,
                            50000,
                        ),
                        min(
                            50000,
                            50000,
                        ),
                    ],
                    # larger than any syringe to ensure full infuse
                    infuse_volumes_ul=[20000, 20000],
                )

                # wait for completion
                while dispensing.methods.is_active(
                    pump=self._devices.PUMP,
                    pump_indices=[self.chem2.input, self.chem1.input],
                ):
                    time.sleep(1)

            self._phase_helper(
                do_if_not_started=to_do, next_phase=Phase.PHASE_1_COMPLETE
            )

        elif self.phase_setpoint.value == Phase.PHASE_1_COMPLETE.value:
            if self._repeat is True:
                self.reset()
                self.phase_setpoint.update(Phase.PHASE_1_INITIALIZED.value)
            else:
                self.enabled_setpoint.update(Enabled.DISABLED.value)

        if log_str is not None:

            log_str += (
                f"{self.phase_to_str(self.phase_setpoint.value)}"
                f"({self.phase_setpoint.value}[{self.current_phase_status}])"
            )

            print(log_str)

            if self.logging_enabled:
                self._aqueduct.log(log_str)

        if repeat is True:
            self.do_next_phase()
