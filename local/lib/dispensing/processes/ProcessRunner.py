import time
import json
from typing import List, Tuple, Callable

import local.lib.dispensing.helpers
import local.lib.dispensing.methods
from local.lib.dispensing.classes import Devices, Data
from local.lib.dispensing.definitions import *

from aqueduct.core.aq import Aqueduct
from aqueduct.core.setpoint import Setpoint, ALLOWED_DTYPES


class ProcessRunner(object):
    """
    Class to handle processing each of the stations.
    """

    stations: list = []

    # control the period in seconds at which
    # the process prints the status of all stations to screen
    status_print_interval_s: float = 360.
    last_status_print_time: float = None

    # control the period in seconds at which
    # the process records all station data
    record_data_interval_s: float = 2.
    last_record_time: float = None

    # the heartbeat interval in seconds to wait between processing
    # any events
    interval_s: float = .2

    # reference to the Devices, Data, and Aqueduct classes
    _devices: Devices = None
    _data: Data = None
    _aqueduct: Aqueduct = None

    def __init__(
            self,
            devices_obj: Devices = None,
            aqueduct: Aqueduct = None,
            data: Data = None
    ):

        if isinstance(devices_obj, Devices):
            self._devices = devices_obj

        if isinstance(aqueduct, Aqueduct):
            self._aqueduct = aqueduct

        if isinstance(data, Data):
            self._data = data
            data._process = self

    def add_station(self, station):
        """
        Add a station to the ProcessRunner. The station should have the methods:

        `is_active`
        `is_enabled`
        `make_setpoints`

        and the attributes:

        `_aqueduct`
        `_devices`
        `index`

        """
        self.stations.append(station)
        station.index = len(self.stations) - 1
        station._aqueduct = self._aqueduct
        station._devices = self._devices

        make_setpoints_op = getattr(station, "make_setpoints", None)
        if callable(make_setpoints_op):
            make_setpoints_op()

    def print_all_stations(self):
        """
        Method to print the status of each station.

        :return:
        """
        for s in self.stations:
            print(s)

    def record_all_stations(self):
        """
        Method to call the record method of each station.

        :return:
        """
        all_positions = self._devices.PUMP.get_plunger_positions()
        for s in self.stations:
            record_op = getattr(s, "record", None)
            if callable(record_op):
                record_op(plunger_positions=all_positions)

    def save_log_file(self):
        self._aqueduct.save_log_file(self.stations[0].log_file_name, overwrite=True)

    def print_station_status_at_interval(self):
        """
        Method that prints the status of each station at the
        `status_print_interval_s` period.

        :return:
        """

        if self.last_status_print_time is None or \
                (time.time() > self.last_status_print_time + self.status_print_interval_s):
            self.print_all_stations()
            self.last_status_print_time = time.time()

    def record_station_data_at_interval(self):
        """
        Method that prints the status of each station at the
        `status_print_interval_s` period.

        :return:
        """

        if self.last_record_time is None or \
                (time.time() > self.last_record_time + self.record_data_interval_s):
            self.record_all_stations()
            self.last_record_time = time.time()

    def get_active_pump_inputs(self) -> Tuple[bool]:
        """
        Method used to determine which stations are active, meaning the plunger is
        currently in motion. If the station is not active, then we'll check to see
        which of the steps needs to be performed next.

        :return:
        """

        # create a list of length stations and set all entries to False
        active_stations = len(self.stations) * [False]

        # get the status of all the pumps, this returns a tuple
        # of boolean values
        active_pumps = self._devices.PUMP.get_status()

        # now loop through all of ProcessRunner's stations and 
        # call the station's `is_active` method (pass the active_pumps) 
        for i, s in enumerate(self.stations):
            active_stations[i] = s.is_active(active_pumps)
           
        return tuple(active_stations)

    def csv_upload_with_header_row(self) -> list:
        """
        Prompt the user to upload a csv (comma separated values) file. Display the uploaded data for the
        user to confirm the uploaded data appears correct. Return a list of the user confirmed values.
        :return: new_list = a list of the user confirmed values
        """

        # prompt the user to upload a csv with the correct formatting.
        # Row 0 is the header row with data labels. Within a row the data (columns) are separated by commas.
        csv_ipt = self._aqueduct.input(
            message="Upload a CSV file. Within a row use commas to separate column entries from left to right. <br>"
                    "Each new line will be a new row.  <br>"
                    "Ensure row 0 is a header row (labels).  <br>",
            input_type="csv",
            dtype="str"
        )

        table_data = csv_ipt.get_value()
        as_list = json.loads(table_data)
        new_list = []
        labels = []

        # get the data labels and store in a list
        for column in as_list[0]:
            labels.append(column)

        # get the data starting at row index 1 (not row to omit the header row). Store the values in new_list.
        for i, r in enumerate(as_list[1::]):
            row_index = i
            row_contents = []
            for j, column in enumerate(r):
                row_contents.append(dict(
                    name=f"{labels[j]}", value=column))

            new_list.append(dict(
                hint=f"csv row: {row_index}",
                value=row_contents,
                dtype="list",
                name=f"data{i}"
            ))

        # prompt the user to confirm the uploaded csv data looks correct.
        tabular_ipt = self._aqueduct.input(
            message="Confirm the uploaded data.",
            input_type="table",
            dtype="str",
            rows=new_list,
        )

        # format the confirmed data (str) into a list and return the list new_rates.
        confirmed_values = json.loads(
            tabular_ipt.get_value())
        new_params = []

        for cv in confirmed_values:
            row = []
            for value in cv:
                try:
                    row.append(float((value.get('value'))))
                except ValueError:
                    row.append((value.get('value')))
            new_params.append(row)

        # params are a list of list with index row and columns:
        """
        Row 0 (Station 0)
            0: Reactor Index
            1: Temperature(C)
            2: Kettle_CTA(mL)
            3: Kettle_water(mL)
            4: Init_seed(mL)
            5: Mono_seed(mL)
            6: time_seed(h)
            7: Mono_seed_rate(uL / min)
            8: Init_polym(mL)
            9: Init_polym_rate(uL / min)
            10: Mono_polym(mL)
            11: Mono_polym_rate(uL / min)
            12: time_polym(h)
        Row 1 (Station 1) 
            ...
        """
        return new_params

    def run(self):
        """
        The main function to run the process.

        :return:
        """
        # infinite loop
        while True:

            active_inputs = self.get_active_pump_inputs()

            for i, a in enumerate(active_inputs):
                if a is False and self.stations[i].is_enabled():
                    self.stations[i].do_next_phase()

            self.print_station_status_at_interval()
            self.record_station_data_at_interval()
            time.sleep(self.interval_s)

