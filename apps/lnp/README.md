# TFF Process Control #

## Tangential Flow Filtration ## 

<b>Tangential Flow Filtration (TFF)</b> is a process used to separate or 
remove small solids from a feed liquid. The feed liquid is driven tangentially 
across the surface of the filter and the permeate (filtered stream) is collected 
continuously. 

TFF operating parameters, such as the liquid flux across the membrane and
trans-membrane pressure, are key to ensuring optimal sepearation performance. 
This control process involves the collection of in-line pressure data to 
adjust feed and permeate pump flow rates and a pinch valve
to maitain pressure targets. If the process is run in constant-volume diafiltration 
mode, the feed stock must be replinished using a buffer solution that necessitates
the addition of a third buffer pump. This Library contains a control algorithm to 
adjust the transfer rate of the buffer pump to maintain a constant weight of feed
stock, thereby eliminating the dependency on the buffer pump's nominal 
flow rate as the signal.

This Library contains Classes, Methods, and algorithms to add model and execute a multi-stage
TFF process, including initial concentration, diafiltation, and final concentration. 
Operating parameters, such as feed flow rates and target pressures may be adjusted to 
suit specific applications.

## Modeling the Process ##

The Aqueduct's platform ability to simulate the process prior to running 
in the laboratory with real reagents/equipment can be useful for validating
control algorithms. 

## Control ##

### Smart Dose Addition ###

### PID ###