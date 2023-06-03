"""
Name: recorded_counter.py

Description:

This demo illustrates creating a `Recordable`, which saves data
in a timeseries and makes it accessible in the user interface.


"""
import time

import aqueduct.aqueduct as aq_module

# a guard to make sure we have an Aqueduct instance "aqueduct" in scope
aqueduct: aq_module.Aqueduct
if not globals().get("aqueduct"):
    aqueduct = aq_module.Aqueduct("G", None, None, None)
else:
    aqueduct = globals().get("aqueduct")


my_recordable = aqueduct.recordable(
    name="my_recordable",
    value=0,
    dtype=int.__name__,
)

while True:
    my_recordable.update(my_recordable.value + 1)
    time.sleep(1)
