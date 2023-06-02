# pH Control & Monitoring Library #

- [Introduction](#introduction)
- [Modeling the Reaction](#modeling-the-reaction)
    - [Constant Rate Kinetic Decay](#constant-rate-model)
    - [Base Addition Rate Dependent](#rate-dependent-model)
- [Control](#control)
    - [Smart Dose Addition (On/Off)](#smart-dose-control)
    - [Base Addition Rate Dependent](#pid-control)
- [Contribution Opportunities](#contribution-opportunities)

## Introduction ##

**pH** is a measure of the concentration of H+ ions in a solution. Many
reactions are sensitive to pH, so controlling it with the use of a buffer
solution or the periodic addition of acids or bases is common in many
laboratory workflows.

This Library contains classes, methods, and algorithms to add pH control
to a reaction using one or more peristaltic pumps and pH probes. It was
developed for a specific reaction - the methacrylation of hyaluronic acid (HA).
During this reaction, methacrylic anhydride (MA) is added to an aqueous solution
of hyaluronic acid. The MA reacts with water and HA to form methacrylic acid, which
increases the concentration of H+ and lowers the pH. To maintain a pH that
drives the reaction forward, a base - typically NaOH - must be added continuously
as the reaction proceeds.

See more here:

[Schuurmans, Carl CL, et al. "Hyaluronic acid and chondroitin sulfate (meth) acrylate-based hydrogels
for tissue engineering: Synthesis, characteristics and pre-clinical evaluation."
Biomaterials 268 (2021): 120602.](https://www.sciencedirect.com/science/article/pii/S0142961220308486)

[Tsanaktsidou, Evgenia, Olga Kammona, and Costas Kiparissides. "On the synthesis and characterization
of biofunctional hyaluronic acid based injectable hydrogels for the repair of cartilage lesions."
European Polymer Journal 114 (2019): 47-56.](https://www.sciencedirect.com/science/article/pii/S001430571831677X)

[Burdick, Jason A., and Glenn D. Prestwich. "Hyaluronic acid hydrogels for biomedical applications."
Advanced materials 23.12 (2011): H41-H56.](https://pubmed.ncbi.nlm.nih.gov/21394792/)

The kinetics of the reaction evolve with time, so typically the rate of NaOH addition is higher
during the early part of the reaction.

## Modeling the Reaction ##

The Aqueduct's platform ability to simulate the process prior to running
in the laboratory with real reagents/equipment can be useful for validating
control algorithms.

### <a id="constant-rate-model"></a>Constant Rate Kinetic Decay (Smart Dose)

For the Smart Dose control algorithm, we model the decay in pH rate-of-change
with time using a linear expression. At early time, the rate of decrease
(dpH/dt) is negative and the magnitude is large. As the reaction proceeds, dpH/dt
becomes smaller in magnitude but remains negative.

We can model this behavior with the expression:

`dpH_dt(t) = ROC_start + (t_now - t_start) * delta_ROC_dt`

where:

`dpH_dt` == rate of change in pH as a function of time

`ROC_start` == rate of change in pH at t_start, reaction start

`t_now` == current time

`t_start` == reaction start time

`delta_ROC_dt` == decay in reaction kinetics with time

The `ReactionModel` Class in the `models.py` file encapsulates this behavior.

### <a id="rate-dependent-model"></a>Base Addition Rate Dependent (PID)

For the PID control algorithm, we model the pH rate-of-change as a function of the
base addition rate. As the reaction proceeds, the sensitiviy of the pH rate-of-change to base
addition rate increases.

We can model this behavior with the expression:

`dpH_dt(t, base_addition_rate) = ROC_offset + (ROC_init + (t_now - t_start) * delta_ROC_dt) * base_addition_rate`

`dpH_dt` == rate of change in pH as a function of time and base additon rate

`ROC_offset` == rate of change in pH intrinsic to the reaction

`ROC_init` == rate of change in pH at t_start, reaction start

`t_now` == current time

`t_start` == reaction start time

`delta_ROC_dt` == decay in reaction kinetics with time

`base_addition_rate` == rate of addition of base in mL/min

The `PidModel` Class in the `models.py` file encapsulates this behavior.

## Control ##

### <a id="smart-dose-control"></a>Smart Dose Addition (On/Off)

The Smart Dose Addtion algorithm adds base to the reaction vessel
in finite doses when the pH drops below the setpoint value. To calculate
the volume of dose, the algorithm calculates the effect of the previous
dose (change in pH per added volume) and adjusts the next dose volume
to hit the setpoint.

The algorithm limits the maximum change in addition dose volume
for sequential doses.

### <a id="pid-control"></a>PID

The PID Control algorithm adds base continuously to the reaction
vessel to achieve the target pH setpoint. The rate of addition is calculated
by the PID controller, which constantly calculates the error (setpoint - current value of pH),
cumulative error (sum of errors), and time rate of change of the error (d_error/dt).
