import logging
import sys
from typing import Union

from .config import settings


def setup_logging() -> None:
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    log_level: Union[str, int] = settings.LOG_LEVEL.upper() if hasattr(settings, "LOG_LEVEL") else "INFO"

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
