import logging
import subprocess
import time


LOGGER = logging.getLogger(__name__)


class TimeoutExpiredError(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __str__(self):
        return f"Timed Out: {self.value}"


class TimeoutSampler(object):
    """
    Samples the function output.

    This is a generator object that at first yields the output of function
    `func`. After the yield, it either raises instance of `TimeoutExpiredError` or
    sleeps `sleep` seconds.

    Yielding the output allows you to handle every value as you wish.

    Feel free to set the instance variables.
    """

    def __init__(
        self, timeout, sleep, func, exceptions=None, *func_args, **func_kwargs
    ):
        self.timeout = timeout
        self.sleep = sleep
        self.func = func
        self.func_args = func_args
        self.func_kwargs = func_kwargs
        self.exception = exceptions if exceptions else Exception

    def __iter__(self):
        last_exception_log = ""
        timeout_watch = TimeoutWatch(timeout=self.timeout)
        func_log = (
            f"Function: {self.func} Args: {self.func_args} Kwargs: {self.func_kwargs}"
        )
        while True:
            try:
                yield self.func(*self.func_args, **self.func_kwargs)
            except self.exception as exp:
                last_exception_log = f"Last exception: {exp.__class__.__name__}: {exp}"

            _ = timeout_watch.remaining_time(
                log="{timeout}\n{func_log}\n{last_exception_log}".format(
                    timeout=self.timeout,
                    func_log=func_log,
                    last_exception_log=last_exception_log,
                )
            )
            time.sleep(self.sleep)


class TimeoutWatch:
    """
    A time counter allowing to determine the time remaining since the start
    of a given interval
    """

    def __init__(self, timeout):
        self.timeout = timeout
        self.start_time = time.time()

    def remaining_time(self, log=None):
        """
        Return the remaining part of timeout since the object was created.
        """
        new_timeout = self.start_time + self.timeout - time.time()
        if new_timeout > 0:
            return new_timeout
        raise TimeoutExpiredError(log or self.timeout)


# TODO: remove the nudge when the underlying issue with namespaces stuck in
# Terminating state is fixed.
# Upstream bug: https://github.com/kubernetes/kubernetes/issues/60807
def nudge_delete(name):
    LOGGER.info(f"Nudging namespace {name} while waiting for it to delete")
    try:
        # kube client is deficient so we have to use curl to kill stuck
        # finalizers
        subprocess.check_output(["./scripts/clean-namespace.sh", name])
    except subprocess.CalledProcessError as exp:
        # deliberately ignore all errors since an intermittent nudge
        # failure is not the end of the world
        LOGGER.error(f"Error happened while nudging namespace {name}: {exp}")
        raise
