import logging

from pathlib import Path

import pkg_resources
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
    return pkg_resources.get_distribution('commit-explorer').version


__version__ = version()