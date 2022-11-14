from typing import Union

import aqueduct.core.aq
import aqueduct.devices.mfm.constants
import aqueduct.devices.mfm.obj
import aqueduct.devices.mfpp.constants
import aqueduct.devices.mfpp.obj
import aqueduct.devices.scip.constants
import aqueduct.devices.scip.obj
import aqueduct.devices.sol4.constants
import aqueduct.devices.sol4.obj
import aqueduct.devices.tempx.constants
import aqueduct.devices.tempx.obj
from local.lib.lnp.definitions import *


class Devices(object):
    """

    """
    AQ_PUMP: aqueduct.devices.mfpp.obj.MFPP = None
    OIL_PUMP: aqueduct.devices.mfpp.obj.MFPP = None
    DILUTION_PUMP: aqueduct.devices.mfpp.obj.MFPP = None
    MFM: aqueduct.devices.mfm.obj.MFM = None
    SCIP: aqueduct.devices.scip.obj.SCIP = None
    SOL_VALVES: aqueduct.devices.sol4.obj.SOL4 = None
    TEMP_PROBE: aqueduct.devices.tempx.obj.TEMPX = None

    def __init__(self, aq: aqueduct.core.aq.Aqueduct):
        self.AQ_PUMP = aq.devices.get(AQ_PUMP)
        self.OIL_PUMP = aq.devices.get(OIL_PUMP)
        self.DILUTION_PUMP = aq.devices.get(DILUTION_PUMP)
        self.MFM = aq.devices.get(MFM)
        self.SCIP = aq.devices.get(SCIP)
        self.SOL_VALVES = aq.devices.get(SOL_VALVES)
        self.TEMP_PROBE = aq.devices.get(TEMP_PROBE)
