"""
Name: text_input.py

Description:

This demo illustrates creating a text `Input` named
`text_input` that expects a numeric value. 

We'll pause the Recipe while waiting for the Input to receive
data by setting `pause_recipe=True` when we create the input.
"""
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
    pause_recipe=True,
    dtype=float.__name__,
)

print(f"Input has received data: {text_input.get_value()}")

