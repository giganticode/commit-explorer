import logging
import os

from pathlib import Path

from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level="WARN", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)


logger = logging.getLogger("commitexplorer")
logger.setLevel("INFO")


commit_explorer_root = Path(__file__).parent
project_root = commit_explorer_root.parent


def version() -> str:
    with open(os.path.join(commit_explorer_root, "VERSION")) as version_file:
        return version_file.read().strip()


def appauthor() -> str:
    return "giganticode"


def appname() -> str:
    return "commit-explorer"


__version__ = version()