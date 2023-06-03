"""
Name: counter.py

Description:

This demo illustrates creating a `Setpoint` named
`counter` that increments itself forever in an
infinite while loop.

The counter value can be modified from the Aqueduct
user interface.

This is a simple example, but it illustrates the general
process of creating an externally modifiable value
that can be used in your Recipe logic.
"""
import time

import aqueduct.aqueduct as aq_module

# a guard to make sure we have an Aqueduct instance "aqueduct" in scope
aqueduct: aq_module.Aqueduct
if not globals().get("aqueduct"):
    aqueduct = aq_module.Aqueduct("G", None, None, None)
else:
    aqueduct = globals().get("aqueduct")

# create the counter with the name "my_counter"
my_counter = aqueduct.setpoint(
    name="my_counter",
    value=0,
    dtype=int.__name__,
)

while True:
    print(f"Setpoint value: {my_counter.value}")
    # increment the counter by 1
    my_counter.update(my_counter.value + 1)
    time.sleep(1)
