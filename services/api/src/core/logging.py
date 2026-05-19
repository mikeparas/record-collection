import os

import structlog
from structlog.types import EventDict, WrappedLogger


def inject_pid(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """
    Custom processor to inject the process ID into the log event.
    """
    event_dict["pid"] = os.getpid()
    return event_dict


def init_logger():
    structlog.configure(
        processors=[
            # order appears to matter
            structlog.contextvars.merge_contextvars,
            inject_pid,
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.JSONRenderer(),
        ]
    )
