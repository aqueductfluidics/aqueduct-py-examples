"""PID Controller Module"""
import time
from typing import Union, Tuple


def _clamp(value: Union[int, float], limits: Tuple[float, float]):
    lower, upper = limits
    if value is None:
        return None
    elif (upper is not None) and (value > upper):
        return upper
    elif (lower is not None) and (value < lower):
        return lower
    return value


class PID:
    """
    A simple PID controller.

    Credit to (Martin Lundberg) https://github.com/m-lundberg/simple-pid for the core of the code.
    """

    def __init__(
        self,
        k_p: float = 1.0,
        k_i: float = 0.0,
        k_d: float = 0.0,
        setpoint: float = 0,
        period_s: float = 0,
        output_limits: Tuple[float, float] = (None, None),
        controllable_limits: Tuple[float, float] = (None, None),
        controllable_region_count_thresh: int = 10,
    ):
        """
        Initialize a new PID controller.
        :param k_p: The value for the proportional gain k_p
        :param k_i: The value for the integral gain k_i
        :param k_d: The value for the derivative gain k_d
        :param setpoint: The target plant setpoint
        :param period_s: The update period of the controller, in seconds
        :param output_limits: the limiting output values of the control parameter
        :param controllable_limits: define a limited controllable region in which to calculate the integral term,
            this should be expressed as error from the setpoint, ie (1, 2) would set the controllable range
            to [setpoint - 1, setpoint + 2]
        :param controllable_region_count_thresh: define a threshold number of sequential control events
            for which the signal needs to be in the control region to be considered controllable and use
            calculate the integral
        """
        self.k_p, self.k_i, self.k_d = k_p, k_i, k_d
        self.setpoint = setpoint
        self.period_s: float = period_s

        self._min_output, self._max_output = None, None

        self._proportional = 0
        self._integral = 0
        self._derivative = 0

        self._last_time = None
        self._last_output = None
        self._last_input = None

        self._last_error = None
        self._in_controllable_region_count = 0

        self.output_limits = output_limits
        self.controllable_limits = controllable_limits
        self.controllable_region_count_thresh = controllable_region_count_thresh
        self.reset()

    def __call__(self, input_, dt=None) -> float:
        """
        Update the PID controller.
        """
        now = time.monotonic()
        if dt is None:
            dt = now - self._last_time if (now - self._last_time) else 1e-16
        elif dt <= 0:
            raise ValueError("dt has negative value {}, must be positive".format(dt))

        if (
            self.period_s is not None
            and dt < self.period_s
            and self._last_output is not None
        ):
            return self._last_output

        error = self.setpoint - input_
        delta_input = input_ - (
            self._last_input if (self._last_input is not None) else input_
        )

        # Compute proportional term
        self._proportional = self.k_p * error

        #
        in_controllable_region = True

        if self.controllable_limits[0] and self.controllable_limits[1]:
            if -1 * self.controllable_limits[0] < error < self.controllable_limits[1]:
                in_controllable_region = True
            else:
                in_controllable_region = False

        if in_controllable_region:
            self._in_controllable_region_count += 1
        else:
            self._in_controllable_region_count = 0

        # if the controllable count exceeds the threshold, compute the integral
        if self._in_controllable_region_count > self.controllable_region_count_thresh:

            # Compute integral term
            self._integral += self.k_i * error * dt
            self._integral = _clamp(
                self._integral, self.output_limits
            )  # Avoid integral windup

        # Compute derivative term
        self._derivative = -self.k_d * delta_input / dt

        # Compute final output
        output = self._proportional + self._integral + self._derivative
        output = _clamp(output, self.output_limits)

        # Keep track of state
        self._last_error = error
        self._last_output = output
        self._last_input = input_
        self._last_time = now

        return output

    def __repr__(self):
        return (
            "{self.__class__.__name__}("
            "k_p={self.k_p!r}, k_i={self.k_i!r}, k_d={self.k_d!r}, "
            "setpoint={self.setpoint!r}, period_s={self.period_s!r}, "
            "output_limits={self.output_limits!r},"
            ")"
        ).format(self=self)

    @property
    def components(self):
        """
        The P-, I- and D-terms from the last computation as separate components as a tuple. Useful
        for visualizing what the controller is doing or when tuning hard-to-tune systems.
        """
        return self._proportional, self._integral, self._derivative

    @property
    def tunings(self):
        """The tunings used by the controller as a tuple: (k_p, k_i, k_d)."""
        return self.k_p, self.k_i, self.k_d

    @tunings.setter
    def tunings(self, tunings):
        """Set the PID tunings."""
        self.k_p, self.k_i, self.k_d = tunings

    @property
    def output_limits(self):
        """
        The current output limits as a 2-tuple: (lower, upper).
        See also the *output_limits* parameter in :meth:`PID.__init__`.
        """
        return self._min_output, self._max_output

    @output_limits.setter
    def output_limits(self, limits):
        """Set the output limits."""
        if limits is None:
            self._min_output, self._max_output = None, None
            return

        min_output, max_output = limits

        if (None not in limits) and (max_output < min_output):
            raise ValueError("lower limit must be less than upper limit")

        self._min_output = min_output
        self._max_output = max_output

        self._integral = _clamp(self._integral, self.output_limits)
        self._last_output = _clamp(self._last_output, self.output_limits)

    def reset(self):
        """
        Reset the PID controller internals.
        This sets each term to 0 as well as clearing the integral, the last output and the last
        input (derivative calculation).
        """
        self._proportional = 0
        self._integral = 0
        self._derivative = 0

        self._integral = _clamp(self._integral, self.output_limits)
        self._in_controllable_region_count = 0

        self._last_time = time.monotonic()
        self._last_output = None
        self._last_input = None

    def get_last_error(self):
        return self._last_error
