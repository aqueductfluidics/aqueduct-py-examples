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

import aqueduct.devices.trcx.obj
import aqueduct.devices.trcx.constants


from typing import List, Tuple, Callable


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

    # add rest of your phases here
    STEP_ONE = 1

    # phase upon completion
    COMPLETE = 99


def phase_to_str(phase: int) -> str:
    """
    Helper method to convert the Phase Enum number to a readable string.

    :param phase:
    :return: human readable phase description
    """
    if phase == Phase.INITIALIZED.value:
        return "initialized"


    elif phase == Phase.COMPLETE.value:
        return "complete"


class ProcessTemplate(object):
    """
    Class to contain all relevant parameters for executing a generic process with one
    or more syringe pumps.
    """

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

    # add relevant process params here, such as 
    # port indices, target volumes, target flowrates, 
    # counters, etc.


    
    
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
        return f"Station {self.index} (mon. {self.monomer_input}, init. {self.initiator_input}): " \
               f"enabled={self.enabled_setpoint.value}, phase={self.phase_setpoint.value}"

    def make_setpoints(self) -> None:
        """
        Method used to generate the enable_setpoint and phase_setpoint and any other 
        setpoints useful for the specific process

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

    def is_active(self, active_inputs: Tuple[bool]) -> bool:
        """
        Method to determine whether the station is active or needs to be moved on to the
        next phase in the process.

        :param active_inputs:
        :return:
        """
        is_active = active_inputs[self.pump_input]

        return is_active

    def is_enabled(self) -> bool:
        """
        Method to determine whether the station is enabled.

        :return:
        """
        return self.enabled_setpoint.value == self.Enabled.ENABLED.value

    def set_current_phase_status(self, phase_status: CurrentPhaseStatus) -> None:
        self.current_phase_status = phase_status.value

    def _phase_helper(
            self,
            do_if_not_started: Callable = None,
            next_phase: Phase = None,
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
        if self.current_phase_status == Phase.CurrentPhaseStatus.NOT_STARTED.value:
            self.set_current_phase_status(Phase.CurrentPhaseStatus.STARTED)
            if do_if_not_started is not None:
                if do_if_not_started_kwargs is not None:
                    do_if_not_started(**do_if_not_started_kwargs)
                else:
                    do_if_not_started()
        elif self.current_phase_status == Phase.CurrentPhaseStatus.STARTED.value:
            self.set_current_phase_status(Phase.CurrentPhaseStatus.NOT_STARTED)
            self.phase_setpoint.update(next_phase.value)

    def do_next_phase(self):

        # flag to repeat the method after printing the status update
        # initialized to False
        repeat: bool = False

        # start of a logging string that tracks the phase and status change
        log_str: str = f"Station {self.index}: {self.phase_to_str(self.phase_setpoint.value)}" \
                       f"({self.phase_setpoint.value}[{self.current_phase_status}]) -> "

        if self.phase_setpoint.value == Phase.INITIALIZED.value:

            self._phase_helper(
                do_if_not_started=None,
                next_phase=Phase.STEP_ONE,
            )
            
            # setting repeat = True means we'll run through the `do_next_phase` function again
            repeat = True

        elif self.phase_setpoint.value == Phase.STEP_ONE.value:

            def to_do():
                """
                Define what actions the station should take during this step, 
                such as: 
                    starting plunger movement(s) 
                    actuating a valve(s) 
                    starting a timer
                """
                # add actions here

                return

            self._phase_helper(
                do_if_not_started=to_do,
                next_phase=Phase.COMPLETE
            )

        elif self.phase_setpoint.value == Phase.COMPLETE.value:
            if self._repeat is True:
                self.reset()
                self.phase_setpoint.update(Phase.COMPLETE.value)
            else:
                self.enabled_setpoint.update(self.Enabled.DISABLED.value)

        log_str += f"{self.phase_to_str(self.phase_setpoint.value)}" \
                   f"({self.phase_setpoint.value}[{self.current_phase_status}])"

        print(log_str)

        if self.logging_enabled:
            self._aqueduct.log(log_str)
            self._aqueduct.save_log_file(self.log_file_name, overwrite=True)

        if repeat is True:
            self.do_next_phase()
