import logging

from pathlib import Path

import pkg_resources


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "[%(name)s] (PID %(process)d) %(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# FORMAT = "%(asctime)s - %(levelname)s - (PID %(process)d) [%(name)s] - %(message)s"


logger = logging.getLogger("commitexplorer")
logger.setLevel("DEBUG")

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)


commit_explorer_root = Path(__file__).parent
project_root = commit_explorer_root.parent


def version() -> str:
    return pkg_resources.get_distribution('commit-explorer').version


__version__ = version()