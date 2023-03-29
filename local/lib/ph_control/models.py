import time
import random
import threading

import local.lib.ph_control.definitions
import local.lib.ph_control.classes


class ReactionModel(object):
    reaction_start_time: float = None

    change_start: float = .75  # pH/mL
    delta_change_s: float = -0.0001  # pH/ml*s
    delta_change_bounds: tuple = (0.05, 0.75)

    rate_of_change_start: float = -0.02  # pH/s
    delta_rate_of_change_s: float = 0.00001  # ph/s**2
    rate_of_change_bounds: tuple = (-0.02, -0.0005)

    def __init__(
            self,
            devices_obj: "local.lib.ph_control.classes.Devices" = None,
            aqueduct: "local.lib.ph_control.classes.Aqueduct" = None,
            data: "local.lib.ph_control.classes.Data" = None
    ):
        self._devices = devices_obj
        self._aqueduct = aqueduct
        self._data = data

    def start_reaction(self) -> None:
        self.reaction_start_time = time.time()

    def calc_rate_of_change(self) -> float:
        reaction_duration_s = time.time() - self.reaction_start_time
        roc = self.rate_of_change_start + reaction_duration_s * self.delta_rate_of_change_s
        roc = max(min(roc, self.rate_of_change_bounds[1]), self.rate_of_change_bounds[0])
        return round(roc, 4)

    def calc_change(self) -> float:
        reaction_duration_s = time.time() - self.reaction_start_time
        change = self.change_start + reaction_duration_s * self.delta_change_s
        change = max(min(change, self.delta_change_bounds[1]), self.delta_change_bounds[0])
        return round(change, 3)

    def add_dose(self, volume_ml, ph_index) -> float:
        pH_change = self.calc_change() * volume_ml
        roc = self.calc_rate_of_change()
        self._devices.PH_PROBE.set_sim_value(
            value=getattr(self._data, f"pH_{ph_index}") + pH_change,
            index=ph_index
        )
        self._devices.PH_PROBE.set_sim_rates_of_change(
            {str(ph_index): roc}
        )


class PidModel(object):
    reaction_start_time: float = None

    dpH_s_dmL_min_start: float = .095  # (pH/s)/(mL/min)
    delta_change_s: float = 0.000005  # (pH/s)/(mL/min*s)
    delta_change_bounds: tuple = (-.5, .5)
    roc_offset: float = None

    _last_roc = None

    time_constant_s: float = None

    pH_probe_index: int = 0

    def __init__(
            self,
            pH_probe_index: int = 0,
            devices_obj: "local.lib.ph_control.classes.Devices" = None,
            aqueduct: "local.lib.ph_control.classes.Aqueduct" = None,
            data: "local.lib.ph_control.classes.Data" = None
    ):
        self._devices = devices_obj
        self._aqueduct = aqueduct
        self._data = data

        self.pH_probe_index = pH_probe_index

        self.time_constant_s = round(random.uniform(2, 6), 3)
        # initialize the roc_offset value in a range between -1.95/60 and -.95/60
        self.roc_offset = round(random.uniform(-1.95 / 60, -.95 / 60), 4)

    def start_reaction(self) -> None:
        self.reaction_start_time = time.time()

    def calc_rate_of_change(self, ml_min) -> float:
        reaction_duration_s = time.time() - self.reaction_start_time
        roc = self.roc_offset + (self.dpH_s_dmL_min_start + reaction_duration_s * self.delta_change_s) * ml_min
        roc = max(min(roc, self.delta_change_bounds[1]), self.delta_change_bounds[0])
        roc = round(roc, 4)
        self._last_roc = roc
        return roc

    def change_rate(self, ml_min) -> float:
        def target():
            time.sleep(self.time_constant_s)
            roc = self.calc_rate_of_change(ml_min)
            vals = [None, None, None]
            vals[self.pH_probe_index] = roc
            self._devices.PH_PROBE.set_sim_rates_of_change(
                roc=vals
            )

        t = threading.Thread(target=target, daemon=True)
        t.start()
