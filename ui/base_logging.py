# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import json
import logging
import datetime as dt

from pathlib import Path

from typing import Union, override

# https://docs.python.org/3/library/logging.html#logrecord-attributes
LOG_RECORD_BUILTIN_ATTRIBUTES = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


# The format keys also define the key order for the log dict
FMT_KEYS = {
    "level": "levelname",
    "timestamp": "timestamp",
    "logger": "name",
    "message": "message",
    "function": "funcName",
    "line": "lineno"
}


class _JsonLinesLogger(logging.Formatter):
    """ LogRecord formatter to log the LogRecords as JSONLines to the log file. """
    def __init__(self, *, fmt_keys: dict[str, str] | None = None):
        super().__init__()
        # set the format text keys
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord) -> dict:
        """ Prepare the log dict and add additional information,
            e.g., if the record has an exception.
        """
        # values to write always
        fields = {
            "message": record.getMessage(),  # might be empty
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if record.exc_info is not None:
            # add formatted exception
            fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            # add stack info
            fields["stack_info"] = self.formatStack(record.stack_info)

        # create the message dict to log
        message = {
            key: msg_val  # prefer value from the always-dict
            if (msg_val := fields.pop(val, None)) is not None  # pop the item from the always-dict
            else getattr(record, val)  # if the always-value is evaluated like False, use the attribute from the fmt_keys
            for key, val in self.fmt_keys.items()
        }
        # update message with the remaining fields from the always-dict
        message.update(fields)

        # add additional data, e.g., given with the extra keyword argument to logging
        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRIBUTES:
                # add only values if the key is not attribute from the LogRecord from logging
                message[key] = val

        return message


class Logging:
    """ Logging for modules (inheriting ModuleBase)

        :param name: Name of the logger to create or to use
        :param file_path: Filepath to write the logs to.
                          If it is evaluated as False (empty string), is will not create a log file.
    """

    def __init__(self, name: str, file_path: Union[str, Path]):
        self.__logger_file_path = file_path
        self.__logger_name = name  # optional logging name

        # disable global stdout / print of text
        logging.propagate = False

        # create a new logger
        self.__logger = logging.getLogger(self.__logger_name)
        # disable current logger stdout / print of text
        self.logger.propagate = False

        # remove all old handlers
        self.remove_all_logging_handlers()

        if self.__logger_file_path:

            # create the parent logging path, if needed
            Path(self.__logger_file_path).parent.mkdir(parents=True, exist_ok=True)

            # create the file handler, where to write the logs to (append mode)
            file_handler = logging.FileHandler(self.__logger_file_path, mode="a", encoding="utf-8")
            formatter = _JsonLinesLogger(fmt_keys=FMT_KEYS)

            file_handler.setFormatter(formatter)

            # add the new handler
            self.logger.addHandler(file_handler)

    def get_logger_name(self) -> str:
        return self.__logger_name

    def get_logger_file_path(self) -> Path:
        return self.__logger_file_path

    def remove_all_logging_handlers(self):
        """ Remove all existing log handlers """
        for handler in self.logger.handlers[:]:
            try:
                handler.acquire()
                handler.flush()
                handler.close()
            except (OSError, ValueError):
                pass
            finally:
                handler.release()
            self.logger.removeHandler(handler)

    @property
    def logger(self) -> logging.Logger:
        return self.__logger

    def log(self, message, *, level: int = logging.DEBUG, **kwargs):
        """ Log to the underlying logging.Logger.

            All other kwargs will be parsed as `extra` kwarg dict to the log method from logging.

            :param message: Message to log
            :param level: Message level, defaults to logging.DEBUG
        """
        if self.logger and callable(self.logger.log):

            # logging with python's logging package
            self.logger.log(level, message, extra=kwargs)

    def unload(self):
        """ Unloads the loaded logger and disables it (can not be restored) """

        # remove all loggers
        self.remove_all_logging_handlers()
        self.__logger = None

