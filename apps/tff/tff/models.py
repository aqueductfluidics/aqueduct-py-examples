"""Simulated Process Model Module"""


class PressureModel(object):
    """
    This simple model estimates the pressures:
        - P1, feed
        - P2, retentate (between TFF ret. and PV)
        - P3, permeate
    using the current pump flow rates and pinch valve position
    as input parameters.

    Procedure:
        1. model Cv of the pass through (feed-retentate) leg of the TFF filter using
           P1 - P2 for known flow rates
        2. model Cv of the pinch valve using a non-linear expression that decreases
           as ~(% open)**-2 with an onset pct open of 0.3 (30%)
        3. calculate P2 assuming atmospheric output pressure and using Cv pinch valve
        4. calculate P1 using P2 and Cv TFF pass through
        5. calculate P3 (permeate) using the expression for TMP

    PUMP1_NAME = "MFPP000001"           # feed pump, Scale1 container to TFF feed
    PUMP2_NAME = "MFPP000002"           # buffer pump, Scale2 container to Scale1 container
    PUMP3_NAME = "MFPP000003"           # permeate pump, TFF Perm2 output to Scale3 container
    OHSA_NAME = "OHSA000001"
    SCIP_NAME = "SCIP000001"
    PV_NAME = "PV000001"                # inline between Txdcr2 and Scale1 container

    SCALE1_INDEX = 2                    # feed balance, bottom right connector on Device Node
    SCALE2_INDEX = 1                    # buffer balance, top right connector on Device Node
    SCALE3_INDEX = 0                    # permeate balance, bottom left connector on Device Node

    SCIP_INDEX = 0                      # bottom left connector on Device Node
    TXDCR1_INDEX = 0                    # inline between Pump1 and TFF feed
    TXDCR2_INDEX = 1                    # inline between TFF retentate and pinch valve
    TXDCR3_INDEX = 2                    # inline between TFF Perm2 and Pump3

    :ivar filtration_start_time: Start time of the filtration process.
    :vartype filtration_start_time: float

    :ivar filter_cv_retentate: Cv value of the retentate leg of the TFF filter.
    :vartype filter_cv_retentate: float

    :param devices_obj: The Devices object containing the Aqueduct devices.
    :type devices_obj: tff.classes.Devices

    :param aqueduct: The Aqueduct object for communication with the Aqueduct system.
    :type aqueduct: tff.classes.Aqueduct

    :param data: The Data object for storing and retrieving data.
    :type data: tff.classes.Data
    """

    filtration_start_time: float = None

    filter_cv_retentate: float = 60

    def __init__(
            self,
            devices_obj: "tff.classes.Devices" = None,
            aqueduct: "tff.classes.Aqueduct" = None,
            data: "tff.classes.Data" = None
    ):
        self._devices = devices_obj
        self._aqueduct = aqueduct
        self._data = data

    def calc_delta_p_feed_rententate(self, R1) -> float:
        """
        Calculate the pressure drop between feed and retentate.

        :param R1: Flow rate in the pass-through leg of the TFF filter.
        :type R1: float

        :return: Pressure drop between feed and retentate.
        :rtype: float
        """
        try:
            return 1 / (self.filter_cv_retentate * 0.865 / R1)**2
        except ZeroDivisionError:
            return 0

    @staticmethod
    def calc_pv_cv(PV) -> float:
        """
        Calculate the Cv of the pinch valve.

        :param PV: Pinch valve position.
        :type PV: float

        :return: Cv of the pinch valve.
        :rtype: float
        """
        if PV < .30:
            return max(100 - (1/PV**2), 1)
        else:
            return 100

    @staticmethod
    def calc_delta_p_rententate(R1, PV) -> float:
        """
        Calculate the pressure drop between retentate and permeate.

        :param R1: Flow rate in the pass-through leg of the TFF filter.
        :type R1: float

        :param PV: Pinch valve position.
        :type PV: float

        :return: Pressure drop between retentate and permeate.
        :rtype: float
        """
        try:
            return 1 / (PressureModel.calc_pv_cv(PV) * 0.865 / R1)**2
        except ZeroDivisionError:
            return 0

    def calc_p1(self, R1, PV, P2) -> float:
        """
        Calculate the P1 pressure.

        :param R1: Flow rate in the pass-through leg of the TFF filter.
        :type R1: float

        :param PV: Pinch valve position.
        :type PV: float

        :param P2: P2 pressure.
        :type P2: float

        :return: P1 pressure.
        :rtype: float
        """
        return P2 + self.calc_delta_p_rententate(R1, PV)

    @staticmethod
    def calc_p2(R1, PV) -> float:
        """
        Calculate the P2 pressure.

        :param R1: Flow rate in the pass-through leg of the TFF filter.
        :type R1: float

        :param PV: Pinch valve position.
        :type PV: float

        :return: P2 pressure.
        :rtype: float
        """
        return PressureModel.calc_delta_p_rententate(R1, PV)

    @staticmethod
    def calc_p3(P1, P2, R1, R3) -> float:
        """
        Calculate the P3 pressure.

        https://aiche.onlinelibrary.wiley.com/doi/epdf/10.1002/btpr.3084

        :param P1: P1 pressure.
        :type P1: float

        :param P2: P2 pressure.
        :type P2: float

        :param R1: Flow rate in the pass-through leg of the TFF filter.
        :type R1: float

        :param R3: Flow rate in the permeate leg of the TFF filter.
        :type R3: float

        :return: P3 pressure.
        :rtype: float
        """
        try:
            return (P1 + P2) / 2 - R3**2 / R1 * 3.9
        except ZeroDivisionError:
            return 0

    def calc_pressures(self):
        """
        Calculate and update the pressures using the model equations.
        """
        p2 = PressureModel.calc_p2(self._data.R1, self._data.PV)
        p1 = self.calc_p1(self._data.R1, self._data.PV, p2)
        p3 = PressureModel.calc_p3(p1, p2, self._data.R1, self._data.R3)
        p1, p2, p3 = min(p1, 50), min(p2, 50), min(p3, 50)
        self._devices.SCIP.set_sim_values(values=(p1, p2, p3,))
