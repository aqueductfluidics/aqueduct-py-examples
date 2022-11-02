## Processes Directory 

### Usage

When creating a new process, the files in this directory are
intended to serve as building blocks.

The `ProcessRunner.py` file contains the code for the main loop, which checks 
on the status of one or more stations. 

The `run` method of the ProcessRunner class:
    1. checks for inactive stations
    2. if it finds an inactive station, it calls the stations `do_next_phase` method if it's enabled
    3. it then prints station status and records data
    4. it sleeps for a second

With this approach, writing a new method comes down to defining Phases and `do_next_phase` methods.

See `Novecare.py` as a complete example and `ProcessTemplate.py` as a template to add functionality to.