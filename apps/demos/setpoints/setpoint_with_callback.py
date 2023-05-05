"""
Name: setpoint_with_callback.py

Description:

This demo illustrates executing a **callback** function
when a Setpoint is modified externally.

Here, we create two Setpoints, `my_counter` and `print_on_demand`.

After creating the `print_on_demand` Setpoint, we define 
a function named `print_the_counter` and assign the function 
to the `print_on_demand` Setpoint's `on_change` member. We also 
assign a dictionary, `dict(sp=print_on_demand)`, as the kwargs 
to be passed to the `on_change` method when it's executed. The 
`print_on_demand` function takes a kwarg (read, "key word arg") `sp`. 

When the "print_me" Setpoint value is changed, the `print_the_counter`
function will be executed and {sp: print_on_demand} will be passed 
as kwargs.

The `my_counter` Setpoint increments itself by 1 in an infinite while loop.

"""

import time
import aqueduct.aqueduct as aq_module

# a guard to make sure we have an Aqueduct instance "aqueduct" in scope
aqueduct: aq_module.Aqueduct
if not globals().get("aqueduct"):
    aqueduct = aq_module.Aqueduct("G", None, None, None)
else:
    aqueduct = globals().get("aqueduct")


my_counter = aqueduct.setpoint(
    name="my_counter",
    value=0,
    dtype=int.__name__,
)

print_on_demand = aqueduct.setpoint(
    name="print_me",
    value="",
    dtype=str.__name__,
)

def print_the_counter(sp):
    print(f"Hey, {sp.value}, the current counter value is {my_counter.value}...")

# notice we assign `print_the_counter`, not `print_the_counter()`, which 
# would call the function
print_on_demand.on_change = print_the_counter
print_on_demand.kwargs = dict(sp=print_on_demand)

while True:
    v = my_counter.get()
    print(f"Setpoint value: {v}")
    my_counter.update(v+1)
    time.sleep(1)