# device names saved on Firmware
# aqueous input pump
AQ_PUMP = "AQ_PUMP"
# oil input pump
OIL_PUMP = "OIL_PUMP"
# diluent pump
DILUTION_PUMP = "DILUTION_PUMP"
# mass flow meter
MFM = "MFM"
# pressure transducers
SCIP = "PRES_TDCR"
# solenoid valves
SOL_VALVES = "SOL_VALVES"
# temperature probes
TEMP_PROBE = "TEMP_PROBE"

# aqueous feed indices
AQUEOUS_MFM_INDEX = 0
AQUEOUS_PRES_TDCR_INDEX = 0
AQUEOUS_TEMP_PROBE_INDEX = 0
AQUEOUS_VALVE_INDEX = 0

# oil feed indices
OIL_MFM_INDEX = 1
OIL_PRES_TDCR_INDEX = 1
OIL_TEMP_PROBE_INDEX = 1
OIL_VALVE_INDEX = 1

# product indices
PRODUCT_MFM_INDEX = 2
PRODUCT_PRES_TDCR_INDEX = 2
PRODUCT_TEMP_PROBE_INDEX = 2

# valve position constants
BYPASS_POSITION = 0
PRODUCT_POSITION = 1

# universal status code for OK
STATUS_OK = 0
# universal status code for a timeout
STATUS_TIMED_OUT = 1
