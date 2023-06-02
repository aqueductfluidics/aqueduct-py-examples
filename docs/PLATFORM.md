# The Aqueduct Fluidics Platform #

- [Introduction](#introduction)
- [Modeling the Reaction](#modeling-the-reaction)
    - [Constant Rate Kinetic Decay](#constant-rate-model)
    - [Base Addition Rate Dependent](#rate-dependent-model)
- [Control](#control)
    - [Smart Dose Addition (On/Off)](#smart-dose-control)
    - [Base Addition Rate Dependent](#pid-control)
- [Contribution Opportunities](#contribution-opportunities)

Aqueduct Fluidics' mission is to make automation more accessible
for benchtop applications in research and development and
small scale production.

Our platform enables users to conceive of, design, simulate, and
deploy complex systems with confidence.

## Envisioning Your Solution ##

We believe that an expansive selection of

## Designing Your System and Protocols ##

## Simulating Your Process ##

## Deploying to the Real World ##

# Applications #

# Platform Architecture #

The core of the platform is a single-board computer that runs Aqueduct's
core software. The Hub can be connected to a local network via ethernet
or Wifi or directly to a PC/Mac via ethernet.


Current Nodes:
4 x RS232
    Compatible with
        Ohaus Adventurer/Scout balances
        Parker SciLog pressure transducers
        New Era Syringe Pumps
        Dobot Magician robotic arm


Mixed Signal Digital/Analog
    Compatible with
        MasterFlex 07552 peristaltic pump


2 x CANBus, 2 x RS485
    Compatible with
        Aqueduct 6 x Peristaltic Pump, Aqueduct 12 x Peristaltic Pump
        TriContinent C(X) Series Syringe Pumps


Motor Driver +
    Compatible with
        Aqueduct Peristaltic Pump
        Aqueduct Rotary Selector Valve
        Aqueduct Pinch Valve


3 x pH Probe
    Compatible with
        Aqueduct 3x pH Probe (compatible with most BNC termintated electrodes)

# FAQ #

## Nomenclature

* What is a Setup?

    A: A **Setup** file contains the type and number of Devices (such as pumps, valves, or sensors),
    Containers (such as beakers, vials, or other labware), Connections (a representation of tubing,
    both external and internal to Devices or Containers), and Inserts (alignment guides for
    robotic arms). It also contains the layout of the Device icons to generate the user interface.

* What is a Recipe?

    A: A **Recipe** file contains a Recipe Script, a Setup, and (optionally) a Layout. It contains
    all of the data necessary to recreate a user interface (Device icons and Widget arrangement) and
    the logic (contained in the Recipe Script) to execute a protocol or processs.


* What is a Layout?

    A: A **Layout** file contains arrangement of Widgets and Widget metadata that generate the
    user interface. For instance, which data series are plotted on the Chart Widget on Tab 1
    is stored in the Layout file.

* What is a Library?

    A: A **Library** is a collection of related Python classes and methods. We've grouped the
    libraries by application (for instance, `ph_control` or `filtration`). Libraries
    are intended to allow for reuse of common methods and classes across multiple Recipes.

* What is the Hub?
* What is a Device?
* What is a Container?
* What is a Connection?
* What is an Insert?

* What is Sim Mode?
* What is Lab Mode?

## Setups

## Recipes

* What happens when I queue a Recipe?
* What's the difference between `pausing` and `e-stopping` a Recipe?
* Do Device control buttons work when a Recipe is running?
* Can I run a simulated Recipe and lab-mode Recipe simultaneously?

## Logging

## Hardware Questions

* What is the Hub?

    The Aqueduct Hub houses a computer and the electronics necessary to communicate with Device Nodes.
    The Hub computer runs a server that can be accessed from a browser like Google Chrome, Mozilla Firefox, or Apple Safari.
    To access the Aqueduct application, the Hub computer needs to be
    powered-on and connected to a local network, computer, or monitor.

* What types of Device Nodes are available?

* How much latency is there when communicating with Devices?
