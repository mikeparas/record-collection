import os

import structlog


def init_logger():
    structlog.contextvars.bind_contextvars(pid=os.getpid())
    structlog.configure(
        processors=[
            # order appears to matter
            structlog.contextvars.merge_contextvars,
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
