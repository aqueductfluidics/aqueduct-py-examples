"""
Name: text_input_no_pause.py

Description:

This demo illustrates creating a text `Input` named
`text_input` that expects a numeric value. 

In this demo, we won't pause the recipe while waiting for 
the Input to receive data - we'll just print out the number 
of times we've waited...
"""
import time
import aqueduct.aqueduct as aq_module

# a guard to make sure we have an Aqueduct instance "aqueduct" in scope
aqueduct: aq_module.Aqueduct
if not globals().get("aqueduct"):
    aqueduct = aq_module.Aqueduct("G", None, None, None)
else:
    aqueduct = globals().get("aqueduct")


print("Input not yet created...")

# create the input
text_input = aqueduct.input(
    message="Enter a numeric value!",
    input_type=aq_module.UserInputTypes.TEXT_INPUT.value,
    pause_recipe=False,
    dtype=float.__name__,
)

i = 0

while not text_input.is_set():
    print(f"Waiting on input for the {i}th time...")
    time.sleep(1)
    i += 1

print(f"Input has received data: {text_input.get_value()}")

