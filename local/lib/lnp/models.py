import time

import local.lib.lnp.classes
import local.lib.lnp.data
import local.lib.lnp.devices


class MassFlowModel(object):
    """
    
    """

    filtration_start_time: float = None

    filter_cv_retentate: float = 60

    def __init__(
            self,
            devices_obj: "local.lib.lnp.classes.Devices" = None,
            aqueduct: "local.lib.lnp.classes.Aqueduct" = None,
            data: "local.lib.lnp.classes.Data" = None
    ):
        self._devices = devices_obj
        self._aqueduct = aqueduct
        self._data = data

    def calc_delta_p_feed_rententate(self, R1) -> float:
        try:
            return 1 / (self.filter_cv_retentate * 0.865 / R1)**2
        except ZeroDivisionError:
            return 0

    @staticmethod
    def calc_pv_cv(PV) -> float:
        if PV < .30:
            return max(100 - (1/PV**2), 1)
        else:
            return 100

    @staticmethod
    def calc_delta_p_rententate(R1, PV) -> float:
        try:
            return 1 / (MassFlowModel.calc_pv_cv(PV) * 0.865 / R1)**2
        except ZeroDivisionError:
            return 0

    def calc_p1(self, R1, PV, P2) -> float:
        return P2 + self.calc_delta_p_rententate(R1, PV)

    @staticmethod
    def calc_p2(R1, PV) -> float:
        return MassFlowModel.calc_delta_p_rententate(R1, PV)

    @staticmethod
    def calc_p3(P1, P2, R1, R3) -> float:
        """
        https://aiche.onlinelibrary.wiley.com/doi/epdf/10.1002/btpr.3084

        P1: 9.500, P2: 6.840, P3: 3.360, W1: -0.800, W2: -1.300, W3: 1.200, R1: 19.975, R2: 4.991, R3: 4.986, PV: 0.2575
        """
        try:
            return (P1 + P2) / 2 - R3**2 / R1 * 3.9
        except ZeroDivisionError:
            return 0

    def calc_pressures(self):
        p2 = MassFlowModel.calc_p2(self._data.R1, self._data.PV)
        p1 = self.calc_p1(self._data.R1, self._data.PV, p2)
        p3 = MassFlowModel.calc_p3(p1, p2, self._data.R1, self._data.R3)
        p1, p2, p3 = min(p1, 50), min(p2, 50), min(p3, 50)
        self._devices.SCIP.set_sim_pressures(values=(p1, p2, p3,))
