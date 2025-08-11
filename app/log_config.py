# app/log_config.py
import os
import logging.config
from typing import Final


def configure_logging() -> None:
    """
    Configure a container-friendly logger.

    * All logs go to stdout via StreamHandler
    * Log level comes from $LOG_LEVEL (default INFO)
    * A dedicated “ratelimit” logger is pre-declared
    """
    level: Final[str] = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "plain",
                },
            },
            "root": {"level": level, "handlers": ["console"]},
            # child logger for rate-limit events
            "loggers": {
                "ratelimit": {
                    "level": "WARNING",
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }
    )
