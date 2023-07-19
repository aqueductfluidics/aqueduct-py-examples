"""Definitions Module"""

FEED_PUMP_NAME = "FEED PUMP"  # feed pump, Scale1 container to TFF feed
# buffer pump, Scale2 container to Scale1 container
BUFFER_PUMP_NAME = "BUFFER PUMP"
# permeate pump, TFF Perm2 output to Scale3 container
PERMEATE_PUMP_NAME = "PERMEATE PUMP"
BALANCE_NAME = "BALANCES"
PRES_XDCRS_NAME = "PRES XDCRS"
PINCH_VALVE_NAME = "PINCH VALVE"  # inline between Txdcr2 and Scale1 container

SCALE1_INDEX = 2  # feed balance, bottom right connector on Device Node
SCALE2_INDEX = 1  # buffer balance, top right connector on Device Node
SCALE3_INDEX = 0  # permeate balance, bottom left connector on Device Node

SCIP_INDEX = 0  # bottom left connector on Device Node
TXDCR1_INDEX = 0  # inline between Pump1 and TFF feed
TXDCR2_INDEX = 1  # inline between TFF retentate and pinch valve
TXDCR3_INDEX = 2  # inline between TFF Perm2 and Pump3

STATUS_OK = 0  # universal status code for OK
STATUS_TIMED_OUT = 1  # universal status code for a timeout
STATUS_TARGET_MASS_HIT = 2  # universal status code for a target mass hit
