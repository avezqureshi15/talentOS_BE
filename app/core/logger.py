import logging
import sys
from typing import Union

from .config import settings

_RESET = "\033[0m"
_COLORS = {
    logging.DEBUG: "\033[34m",      # blue
    logging.INFO: "\033[32m",       # green
    logging.WARNING: "\033[33m",    # orange/yellow
    logging.ERROR: "\033[31m",      # red
    logging.CRITICAL: "\033[35m",   # magenta
}
_LEVEL_COLOR = {
    logging.DEBUG: "\033[34m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;35m",
}


class _ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_color = _LEVEL_COLOR.get(record.levelno, _RESET)
        original_levelname = record.levelname
        record.levelname = f"{level_color}{original_levelname:<8}{_RESET}"
        message_color = _COLORS.get(record.levelno, _RESET)
        record.msg = f"{message_color}{record.msg}{_RESET}"
        return super().format(record)


def setup_logging() -> None:
    log_format: str = "%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    log_level: Union[str, int] = settings.LOG_LEVEL.upper() if hasattr(settings, "LOG_LEVEL") else "INFO"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColoredFormatter(fmt=log_format, datefmt=date_format))

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
