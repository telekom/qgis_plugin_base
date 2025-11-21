# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import time
import logging

from typing import Callable, Optional
from functools import partial


class Connection:
    """ Internal use only in ModuleBase in connect method.

        Read priority for name-attribute (set in __init__-method):

            1. try to get `name` attribute (if value is str type)
            2. try to get `__qualname__` attribute
            3. try to get `__name__` attribute
            4. str wrapped callable object

        :param callable_: Callable function/object, simple call with `callable(*args, **kwargs)` will be made.
        :param logger: Logger to log to
        :param log_hint: Small hint, what this connection call seems to be
        :param log_recursing_active: Set to True, to activate recursion and small run time logging in ns
        :param log_recursion_counter: Current recursion counter.
                                      If the current call reached is greater than `current + 1 > maximum`,
                                      then some details will be logged.
        :param log_recursion_time: Time in nanoseconds between calls, before increase current counter

    """

    def __init__(self, callable_: Callable, logger: Optional[logging.Logger] = None,
                 log_hint: Optional[str] = None,
                 log_recursing_active: bool = True,
                 log_recursion_counter: int = 5,
                 log_recursion_time: float = 15_000_000):

        self.callable = callable_
        if (name := getattr(self.callable, "name", None)) and isinstance(name, str):
            # get name attribute
            self.__name = name
        elif isinstance(self.callable, partial):
            # get name from the callable behind the partial
            self.__name = (getattr(self.callable.func, "__qualname__", None)
                           or getattr(self.callable.func, "__name__", None)
                           or f"functools.partial({self.callable.func})")
        else:
            # get default stuff
            self.__name = self.callable.__qualname__ or self.callable.__name__ or str(self.callable)

        self.logger = logger

        # save some options here
        self.log_recursing_active = log_recursing_active
        self.log_recursion_counter = log_recursion_counter
        self.log_recursion_time = log_recursion_time
        self.__log_hint = log_hint

        self.__last_call = time.perf_counter_ns()
        self.__current_counter = 0

    @property
    def name(self):
        """ Returns assigned callable's name.
        """
        return self.__name

    def call(self, *args, **kwargs):

        parent_name = self.logger.name if self.logger else "< unknown parent >"

        # performance in ns
        current_nanoseconds = time.time_ns()
        result = self.callable(*args, **kwargs)

        if self.log_recursing_active:
            # possible log recursion warning
            diff_time = current_nanoseconds - self.__last_call

            # if diff time is lower than expected value and logging counter > n, then log it
            if diff_time > self.log_recursion_time:
                if self.__current_counter + 1 > self.log_recursion_counter:
                    # reset counter and add warning to logging
                    msg = f"pyqtSignal|RECURSION_WARNING"
                    if self.logger:
                        self.logger.debug(
                            msg,
                            extra={'signal_name': self.name,
                                   "signal_args": args,
                                   'signal_kwargs': kwargs,
                                   'signal_hint': self.__log_hint,
                                   'signal_callable': self.callable,
                                   'signal_parent_name': parent_name,
                                   'diff_time_nanoseconds': diff_time,
                                   'current_nanoseconds': current_nanoseconds,
                                   'last_call_nanoseconds': self.__last_call})
                    self.__current_counter = 0

                else:
                    # just increase counter
                    self.__current_counter += 1
            else:
                # set counter back to zero, too much time gone
                self.__current_counter = 0

        self.__last_call = time.time_ns()

        return result

    def __repr__(self):
        return f"Connection({self.name}, '{self.__log_hint}')"
