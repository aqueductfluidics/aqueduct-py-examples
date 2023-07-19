import json
import time
from typing import Dict
from typing import List
from typing import Tuple

import dispensing.helpers
import dispensing.methods
from aqueduct.core.aq import Aqueduct
from aqueduct.core.input import UserInputTypes
from aqueduct.devices.pump.syringe import tricontinent
from dispensing.classes import Data
from dispensing.classes import Devices


class StationDataInner:
    """
    Represents data for a station, including a list of time and rate values and a data row.

    :param slots: The list of time and rate values.
    :type slots: List[TimeAndRate]
    :param data_row: The data row.
    :type data_row: DataRow
    """

    def __init__(
        self, slots: List[dispensing.helpers.TimeAndRate], data_row: dispensing.helpers.DataRow
    ):
        self.slots = slots
        self.data_row = data_row


class StationData:
    """
    Represents data for a station, including StationDataInner objects for chem1 and chem2.

    :param chem1: The data for chem1.
    :type chem1: StationDataInner
    :param chem2: The data for chem2.
    :type chem2: StationDataInner
    """

    def __init__(self, chem1: StationDataInner, chem2: StationDataInner):
        self.chem1 = chem1
        self.chem2 = chem2


class ProcessRunner:
    """
    Class to handle processing each of the stations.
    """

    stations: list = []

    # control the period in seconds at which
    # the process prints the status of all stations to screen
    status_print_interval_s: float = 360.0
    last_status_print_time: float = None

    # control the period in seconds at which
    # the process records all station data
    record_data_interval_s: float = 1.0
    last_record_time: float = None

    # control the period in seconds at which
    # the process logs (permanently) plunger positions
    log_data_interval_s: float = 30.0
    last_log_time: float = None
    log_data: bool = True

    # the heartbeat interval in seconds to wait between processing
    # any events
    interval_s: float = 0.5

    # reference to the Devices, Data, and Aqueduct classes
    _devices: Devices = None
    _data: Data = None
    _aqueduct: Aqueduct = None

    def __init__(
        self, devices_obj: Devices = None, aqueduct: Aqueduct = None, data: Data = None
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
        station._aqueduct = self._aqueduct  # pylint: disable=protected-access
        station._devices = self._devices  # pylint: disable=protected-access

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
        all_positions = self._devices.PUMP.get_plunger_position_volume()
        for s in self.stations:
            record_op = getattr(s, "record", None)
            if callable(record_op):
                record_op(plunger_positions=all_positions)
        if self.log_data is True:
            if self.last_log_time is None or (
                time.time() > self.last_log_time + self.log_data_interval_s
            ):
                log_str = f"Plgr Pos: {all_positions}"
                self._aqueduct.log(log_str)
                self.last_log_time = time.time()

    def log_station_errors(self):
        """
        Method that prints the error status of each station.

        :return:
        """
        errors = dispensing.methods.has_error(self._devices.PUMP)

        pumps_used = []
        station_map: Dict[int, Tuple[int, any]] = {}

        for i, station in enumerate(self.stations):
            if callable(station.inputs):
                for p in station.inputs():
                    pumps_used.append(p)
                    station_map[p] = (i, station)

        for i, err in enumerate(errors):

            if err.missing and i in pumps_used and station_map[i][1].is_enabled():
                log_str = f"Station {station_map[i][0]}: Missing Pump: {i}"
                print(log_str)
                self._aqueduct.error(log_str)
                if callable(station_map[i][1].disable):
                    station_map[i][1].disable()

            if (
                err.c_series_error
                in (
                    tricontinent.CSeriesError.PlungerOverload,
                    tricontinent.CSeriesError.ValveOverload,
                )
                and i in pumps_used
                and station_map[i][1].is_enabled()
            ):
                log_str = f"Station {station_map[i][0]}: CSeries Error Pump: {i}, {err.c_series_error}"
                print(log_str)
                self._aqueduct.error(log_str)
                if callable(station_map[i][1].disable):
                    station_map[i][1].disable()

    def print_station_status_at_interval(self):
        """
        Method that prints the status of each station at the
        `status_print_interval_s` period.

        :return:
        """

        if self.last_status_print_time is None or (
            time.time() > self.last_status_print_time + self.status_print_interval_s
        ):
            self.print_all_stations()
            self.last_status_print_time = time.time()

    def record_station_data_at_interval(self):
        """
        Method that prints the status of each station at the
        `status_print_interval_s` period.

        :return:
        """

        if self.last_record_time is None or (
            time.time() > self.last_record_time + self.record_data_interval_s
        ):
            self.record_all_stations()
            self.log_station_errors()
            self.last_record_time = time.time()

    def get_active_stations(self) -> Tuple[bool]:
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
        active_pumps = self._devices.PUMP.get_active()

        # now loop through all of ProcessRunner's stations and
        # call the station's `is_active` method (pass the active_pumps)
        for i, s in enumerate(self.stations):
            active_stations[i] = s.is_active(active_pumps)

        return tuple(active_stations)

    def prompt_csv_upload_and_return_data(self) -> list:
        """
        Prompt the user to upload a csv (comma separated values) file. Display the uploaded data for the
        user to confirm the uploaded data appears correct.
        """

        # prompt the user to upload a csv with the correct formatting.
        # Row 0 is the header row with data labels. Within a row the data (columns) are separated by commas.
        csv_ipt = self._aqueduct.input(
            message="Upload a CSV file. Within a row use commas to separate column entries from left to right. <br>"
            "Each new line will be a new row.  <br>"
            "Ensure row 0 is a header row (labels).  <br>",
            input_type=UserInputTypes.CSV_UPLOAD.value,
            dtype=str.__name__,
        )

        as_list = csv_ipt.get_value()
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
                row_contents.append(dict(name=f"{labels[j]}", value=column))

            new_list.append(
                dict(
                    hint=f"csv row: {row_index}",
                    value=row_contents,
                    dtype="list",
                    name=f"data{i}",
                )
            )

        # prompt the user to confirm the uploaded csv data looks correct.
        tabular_ipt = self._aqueduct.input(
            message="Confirm the uploaded data.",
            input_type=UserInputTypes.TABLE.value,
            dtype="str",
            rows=new_list,
        )

        # format the confirmed data (str) into a list and return the list new_rates.
        confirmed_values = json.loads(tabular_ipt.get_value())

        return confirmed_values

    def csv_upload_with_header_row(self) -> list:
        """
        Prompt the user to upload a csv (comma separated values) file. Display the uploaded data for the
        user to confirm the uploaded data appears correct. Return a list of the user confirmed values.
        :return: new_list = a list of the user confirmed values

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
        confirmed_values = self.prompt_csv_upload_and_return_data()
        new_params = []

        for cv in confirmed_values:
            row = []
            for value in cv:
                try:
                    row.append(float(value.get("value")))
                except ValueError:
                    row.append(value.get("value"))
            new_params.append(row)

        # params are a list of list with index row and columns:
        return new_params

    def multi_rate_csv_upload_with_header_row(self) -> List[StationData]:
        """
        Confirmed values as follows:

        [
            [
                {'value': 'R1-A', 'name': 'ELN', 'index': 0},
                {'value': '1', 'name': 'Reactor', 'index': 1},
                {'value': '80', 'name': 'Temp(C)', 'index': 2},
                {'value': '2', 'name': 'time_polym(h)', 'index': 3},
                {'value': '5', 'name': 'Heel_Chem(g)', 'index': 4},
                {'value': '25', 'name': 'Heel_Water(mL)', 'index': 5},
                {'value': 'Initiator1', 'name': 'Chem1', 'index': 6},
                {'value': '6', 'name': 'Pump_Chem1', 'index': 7},
                {'value': '12.5', 'name': 'Syringe_Chem1(mL)', 'index': 8},
                {'value': '6', 'name': 'Chem1(mL)', 'index': 9},
                {'value': '1', 'name': 'Chem1_time1(min)', 'index': 10},
                {'value': '600', 'name': 'Chem1_rate1(uL/min)', 'index': 11},
                {'value': '60', 'name': 'Chem1_time2(min)', 'index': 12},
                {'value': '80', 'name': 'Chem1_rate2(uL/min)', 'index': 13},
                {'value': '30', 'name': 'Chem1_time3(min)', 'index': 14},
                {'value': '20', 'name': 'Chem1_rate3(uL/min)', 'index': 15},
                {'value': '1', 'name': 'Chem1_time4(min)', 'index': 16},
                {'value': '600', 'name': 'Chem1_rate4(uL/min)', 'index': 17},
                {'value': '60', 'name': 'Chem1_time5(min)', 'index': 18},
                {'value': '80', 'name': 'Chem1_rate5(uL/min)', 'index': 19},
                {'value': '30', 'name': 'Chem1_time6(min)', 'index': 20},
                {'value': '20', 'name': 'Chem1_rate6(uL/min)', 'index': 21},
                {'value': '1', 'name': 'Chem1_time7(min)', 'index': 22},
                {'value': '600', 'name': 'Chem1_rate7(uL/min)', 'index': 23},
                {'value': '60', 'name': 'Chem1_time8(min)', 'index': 24},
                {'value': '80', 'name': 'Chem1_rate8(uL/min)', 'index': 25},
                {'value': '30', 'name': 'Chem1_time9(min)', 'index': 26},
                {'value': '20', 'name': 'Chem1_rate9(uL/min)', 'index': 27},
                {'value': '30', 'name': 'Chem1_time10(min)', 'index': 28},
                {'value': '20', 'name': 'Chem1_rate10(uL/min)', 'index': 29},
                {'value': 'MonomerA', 'name': 'Chem2', 'index': 30},
                {'value': '0', 'name': 'Pump_Chem2', 'index': 31},
                {'value': '12.5', 'name': 'Syringe_Chem2(mL)', 'index': 32},
                {'value': '40', 'name': 'Chem2(mL)', 'index': 33},
                {'value': '1', 'name': 'Chem2_time1(min)', 'index': 34},
                {'value': '4000', 'name': 'Chem2_rate1(uL/min)', 'index': 35},
                ...
            ]
            ,
        ]


        Output station_slots:

            list of dictionaries, length 6 - one per station

            each dictionary has two keys: "chem1", "chem2" - chem1
                - list of tuples of (time(min), rate(ul/min))

           [
                {
                    "chem1": [
                        (1.0, 600.0),
                        (60.0, 80.0),
                        (30.0, 20.0),
                        (1.0, 600.0),
                        (60.0, 80.0),
                        (30.0, 20.0),
                        (1.0, 600.0),
                        (60.0, 80.0),
                        (30.0, 20.0),
                        (30.0, 20.0),
                    ],
                    "chem2": [
                        (1.0, 4000.0),
                        (60.0, 533.3),
                        (30.0, 133.3),
                        (1.0, 600.0),
                        (60.0, 80.0),
                        (30.0, 20.0),
                        (1.0, 600.0),
                        (60.0, 80.0),
                        (30.0, 20.0),
                        (30.0, 20.0),
                    ],
                },
                {
                    "chem1": [
                        (2.0, 800.0),
                        (60.0, 106.7),
                        (30.0, 26.7),
                        (1.0, 800.0),
                        (60.0, 106.7),
                        (30.0, 26.7),
                        (1.0, 800.0),
                        (60.0, 106.7),
                        (30.0, 26.7),
                        (30.0, 26.7),
                    ],
                    "chem2": [
                        (1.0, 5000.0),
                        (60.0, 666.7),
                        (30.0, 166.7),
                        (1.0, 800.0),
                        (60.0, 106.7),
                        (30.0, 26.7),
                        (1.0, 800.0),
                        (60.0, 106.7),
                        (30.0, 26.7),
                        (30.0, 26.7),
                    ],
                },
               ...
            ]
        """

        confirmed_values = self.prompt_csv_upload_and_return_data()

        station_slots: List[StationData] = []

        for station in [0, 1, 2, 3, 4, 5]:

            temp: List[StationDataInner] = []

            for chem in [1, 2]:

                slots = []

                try:
                    data_row = dispensing.helpers.extract_total_volume_and_pump_index(
                        confirmed_values, station, chem
                    )
                except BaseException as err:  # pylint: disable=broad-except
                    print(f"Station {station}: Chem {chem}, error: {err}")

                for slot in range(1, 11):
                    try:
                        time_and_rate = dispensing.helpers.extract_time_and_rate(
                            confirmed_values, station, chem, slot
                        )
                        slots.append(time_and_rate)

                    except BaseException as err:  # pylint: disable=broad-except
                        print(
                            f"Station {station}: Chem {chem}, Slot {slot} error: {err}"
                        )
                        slots.append(dispensing.helpers.TimeAndRate(0, 0))

                temp.append(StationDataInner(slots, data_row))

            station_data = StationData(temp[0], temp[1])

            station_slots.append(station_data)

        return station_slots

    def run(self):
        """
        The main function to run the process.

        :return:
        """
        # infinite loop
        while True:

            active_stations = self.get_active_stations()

            for i, active in enumerate(active_stations):
                if active is False and self.stations[i].is_enabled():
                    self.stations[i].do_next_phase()

            self.print_station_status_at_interval()
            self.record_station_data_at_interval()
            time.sleep(self.interval_s)

            if all(s.complete() for s in self.stations):
                log_str = "All stations complete."
                print(log_str)
                self._aqueduct.log(log_str)
                break
